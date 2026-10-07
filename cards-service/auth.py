from typing import Any

import time
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import get_settings, get_supabase

_bearer = HTTPBearer()

# ── Revalidação da conta a cada request ─────────────────────────────────────
# O JWT vale 8h: sem isto, usuário desativado (ou com perfil alterado) seguia usando o token
# até expirar. Conta inexistente/inativa/desativada ou token_version diferente da claim "tv"
# (sessões invalidadas na desativação/reativação) => 401. Cache por processo de _CONTA_TTL_S.
# Código compartilhado: replicado em todos os serviços (CLAUDE.md).
_CONTA_TTL_S = 30
_conta_cache: dict[str, tuple[float, dict | None]] = {}


def _conta_atual(user_id: str) -> dict | None:
    agora = time.monotonic()
    hit = _conta_cache.get(user_id)
    if hit and agora - hit[0] < _CONTA_TTL_S:
        return hit[1]
    from db import get_supabase

    rows = (
        get_supabase().table("profiles")
        .select("active,role,allowed_modules,token_version,deactivated_at")
        .eq("id", user_id).limit(1).execute().data
    )
    conta = rows[0] if rows else None
    _conta_cache[user_id] = (agora, conta)
    return conta


def _validar_conta(data: dict[str, Any]) -> dict[str, Any]:
    try:
        user_id = str(uuid.UUID(str(data.get("id"))))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    try:
        conta = _conta_atual(user_id)
    except Exception:
        # falha fechada: sem conseguir validar a conta, não autentica
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Não foi possível validar a sessão")
    if (
        not conta or not conta.get("active") or conta.get("deactivated_at")
        or int(data.get("tv") or 0) != int(conta.get("token_version") or 0)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    data.update(active=True, role=conta["role"], allowed_modules=conta.get("allowed_modules") or [])
    return data


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict[str, Any]:
    settings = get_settings()
    try:
        data = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=["HS256"], options={"require": ["exp"]}
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    data.pop("exp", None)
    return _validar_conta(data)


def get_cards_perfil(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Enriquece o user dict com 'cards_perfil' a partir de cards_permissoes.
    Admins do Jarvis têm acesso total sem precisar de entrada em cards_permissoes."""
    if user.get("role") == "admin":
        user["cards_perfil"] = "supervisor"
        return user
    sb = get_supabase()
    user_id = user.get("user_id") or user.get("id") or user.get("sub") or ""
    try:
        row = (
            sb.table("cards_permissoes")
            .select("perfil,ativo")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        data = row.data if row else None
    except Exception:
        # PostgREST retorna 406 em vez de vazio pra 0 linhas com maybe_single()
        # em algumas versoes — trata como "sem permissao cadastrada".
        data = None
    if not data or not data.get("ativo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso ao módulo de cartões",
        )
    user["cards_perfil"] = data["perfil"]
    return user


def require_supervisor(
    user: dict[str, Any] = Depends(get_cards_perfil),
) -> dict[str, Any]:
    if user.get("cards_perfil") != "supervisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a supervisores",
        )
    return user

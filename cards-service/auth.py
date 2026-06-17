from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import get_settings, get_supabase

_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict[str, Any]:
    settings = get_settings()
    try:
        data = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        data.pop("exp", None)
        return data
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


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
    row = (
        sb.table("cards_permissoes")
        .select("perfil,ativo")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row.data or not row.data.get("ativo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso ao módulo de cartões",
        )
    user["cards_perfil"] = row.data["perfil"]
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

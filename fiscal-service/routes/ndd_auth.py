import base64
import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth import require_role, get_current_user
from db import get_supabase, get_settings

router = APIRouter(prefix="/api/fiscal")
_logger = logging.getLogger(__name__)

NDD_BASE = "https://spaceportalprod.e-datacenter.nddigital.com.br"
NDD_IDENTITY = "https://spacenddidentityprod.e-datacenter.nddigital.com.br"
NDD_CLIENT_ID = "ndd-identity-space-gateway"
# redirect_uri precisa ser acessível pelo browser do usuário — usar URL pública do Jarvis
# Fallback para localhost em desenvolvimento
NDD_CALLBACK_PATH = "/api/fiscal/ndd/callback"

# Estado PKCE temporário em memória (válido por 5 min)
_pkce_state: dict[str, dict] = {}


def _generate_pkce() -> tuple[str, str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    return verifier, challenge, state


class TokenInput(BaseModel):
    access_token: str
    refresh_token: str = ""
    expires_in: int = 1800


@router.post("/{company_id}/ndd/token")
def store_ndd_token(
    company_id: str,
    body: TokenInput,
    _user: dict = Depends(require_role("admin")),
):
    """Armazena access_token (e refresh_token se disponível) capturado do DevTools."""
    sb = get_supabase()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=body.expires_in)
    ).isoformat()

    sb.table("fiscal_companies").update({
        "ndd_access_token": body.access_token,
        "ndd_refresh_token": body.refresh_token or None,
        "ndd_token_expires_at": expires_at,
    }).eq("id", company_id).execute()

    return {
        "ok": True,
        "expires_at": expires_at,
        "has_refresh_token": bool(body.refresh_token),
    }


@router.get("/{company_id}/ndd/authorize")
def ndd_authorize(
    company_id: str,
    redirect_base: str = "",
    _user: dict = Depends(require_role("admin")),
):
    """
    Inicia fluxo PKCE com offline_access para obter refresh_token automático.
    O refresh_token permite renovação sem interação do usuário.
    """
    settings = get_settings()
    base = redirect_base or NDD_BASE
    redirect_uri = f"{base}{NDD_CALLBACK_PATH}"

    verifier, challenge, state = _generate_pkce()
    _pkce_state[state] = {
        "verifier": verifier,
        "company_id": company_id,
        "redirect_uri": redirect_uri,
        "created_at": datetime.now(timezone.utc).timestamp(),
    }

    params = "&".join([
        f"client_id={NDD_CLIENT_ID}",
        "response_type=code",
        "scope=openid+profile+email+nfse-api+nfe-api+cte-api+offline_access",
        f"redirect_uri={redirect_uri}",
        f"code_challenge={challenge}",
        "code_challenge_method=S256",
        f"state={state}",
    ])
    url = f"{NDD_IDENTITY}/connect/authorize?{params}"
    return RedirectResponse(url=url)


@router.get("/ndd/callback")
def ndd_callback(code: str = "", state: str = "", error: str = ""):
    """Recebe o código de autorização e troca por access_token + refresh_token."""
    import requests as req

    if error:
        raise HTTPException(status_code=400, detail=f"NDD auth error: {error}")

    pkce = _pkce_state.pop(state, None)
    if not pkce:
        raise HTTPException(status_code=400, detail="State inválido ou expirado")

    # Verificar expiração do state (5 min)
    if datetime.now(timezone.utc).timestamp() - pkce["created_at"] > 300:
        raise HTTPException(status_code=400, detail="State expirado — tente novamente")

    resp = req.post(
        f"{NDD_IDENTITY}/connect/token",
        data={
            "grant_type": "authorization_code",
            "client_id": NDD_CLIENT_ID,
            "code": code,
            "redirect_uri": pkce["redirect_uri"],
            "code_verifier": pkce["verifier"],
        },
        timeout=15,
    )

    if not resp.ok:
        _logger.error("NDD callback token exchange failed: %s", resp.text)
        raise HTTPException(status_code=502, detail=f"Falha ao trocar código: {resp.text}")

    data = resp.json()
    access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")
    expires_in = int(data.get("expires_in", 1800))

    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()

    sb = get_supabase()
    sb.table("fiscal_companies").update({
        "ndd_access_token": access_token,
        "ndd_refresh_token": refresh_token or None,
        "ndd_token_expires_at": expires_at,
    }).eq("id", pkce["company_id"]).execute()

    has_refresh = bool(refresh_token)
    msg = (
        "Conectado com sucesso! Renovação automática ativada."
        if has_refresh else
        "Conectado. Token válido por 30 min — reconecte periodicamente."
    )
    return {"ok": True, "message": msg, "has_refresh_token": has_refresh, "expires_at": expires_at}


@router.get("/{company_id}/ndd/status")
def ndd_status(
    company_id: str,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    row = sb.table("fiscal_companies").select(
        "ndd_token_expires_at,ndd_refresh_token,ndd_access_token"
    ).eq("id", company_id).execute()

    if not row.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    r = row.data[0]
    expires_at = r.get("ndd_token_expires_at")
    has_token = bool(r.get("ndd_access_token"))
    has_refresh = bool(r.get("ndd_refresh_token"))

    minutos = None
    expirado = True
    if expires_at and has_token:
        delta = datetime.fromisoformat(expires_at) - datetime.now(timezone.utc)
        minutos = int(delta.total_seconds() / 60)
        expirado = minutos <= 0

    return {
        "has_token": has_token,
        "has_refresh_token": has_refresh,
        "expires_at": expires_at,
        "minutos_para_expirar": minutos,
        "expirado": expirado,
        "status": (
            "ok" if not expirado and has_refresh else
            "ok_sem_renovacao" if not expirado else
            "expirado"
        ),
    }

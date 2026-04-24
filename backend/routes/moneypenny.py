import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth import get_current_user
from db import get_settings, get_supabase
from services.microsoft_graph import GraphClient, build_auth_url, exchange_code_for_tokens

router = APIRouter(prefix="/moneypenny", tags=["moneypenny"])

_pending_states: dict[str, str] = {}  # state -> user_id (in-memory, single instance)


class PrefsIn(BaseModel):
    send_hour_utc: int
    active: bool


def _resolve_user_id(current_user: dict) -> str:
    if uid := current_user.get("id"):
        return uid
    db = get_supabase()
    result = db.table("profiles").select("id").eq("username", current_user["username"]).execute()
    if not result.data:
        raise HTTPException(404, "Perfil não encontrado")
    return result.data[0]["id"]


@router.get("/auth/microsoft/url")
def get_microsoft_auth_url(current_user: dict = Depends(get_current_user)):
    state = secrets.token_urlsafe(24)
    _pending_states[state] = _resolve_user_id(current_user)
    return {"url": build_auth_url(state)}


@router.get("/auth/microsoft/callback")
def microsoft_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    user_id = _pending_states.pop(state, None)
    if not user_id:
        raise HTTPException(400, "Estado OAuth inválido ou expirado")

    try:
        tokens = exchange_code_for_tokens(code)
    except ValueError as e:
        raise HTTPException(400, str(e))

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    graph = GraphClient(access_token)
    me = graph.get_me()
    email = me.get("mail") or me.get("userPrincipalName", "")

    db = get_supabase()
    db.table("connected_accounts").upsert(
        {
            "user_id": user_id,
            "provider": "microsoft",
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": expiry.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id,provider",
    ).execute()

    s = get_settings()
    return RedirectResponse(url=f"{s.frontend_url}/moneypenny?connected=1", status_code=302)


@router.get("/account")
def get_account(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = (
        db.table("connected_accounts")
        .select("email,token_expiry,updated_at")
        .eq("user_id", _resolve_user_id(current_user))
        .eq("provider", "microsoft")
        .execute()
    )
    if not result.data:
        return {"connected": False}
    acc = result.data[0]
    return {"connected": True, "email": acc["email"], "updated_at": acc["updated_at"]}


@router.delete("/account")
def disconnect_account(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    db.table("connected_accounts").delete().eq("user_id", _resolve_user_id(current_user)).eq("provider", "microsoft").execute()
    return {"ok": True}


@router.get("/prefs")
def get_prefs(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("notification_prefs").select("*").eq("user_id", _resolve_user_id(current_user)).execute()
    if not result.data:
        return {"send_hour_utc": 10, "active": True}
    return result.data[0]


@router.put("/prefs")
def save_prefs(body: PrefsIn, current_user: dict = Depends(get_current_user)):
    if not (0 <= body.send_hour_utc <= 23):
        raise HTTPException(400, "send_hour_utc deve ser entre 0 e 23")
    db = get_supabase()
    db.table("notification_prefs").upsert(
        {
            "user_id": _resolve_user_id(current_user),
            "send_hour_utc": body.send_hour_utc,
            "active": body.active,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
    return {"ok": True}


@router.post("/test")
async def send_test_summary(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = (
        db.table("connected_accounts")
        .select("*")
        .eq("user_id", _resolve_user_id(current_user))
        .eq("provider", "microsoft")
        .execute()
    )
    if not result.data:
        raise HTTPException(400, "Conta Microsoft não conectada")

    account = result.data[0]
    try:
        graph = GraphClient(account["access_token"])
        emails = graph.get_unread_emails_yesterday()
        events = graph.get_today_events()

        from services.summary import _build_html
        html = _build_html(current_user["display_name"], emails, events)
        graph.send_mail(
            to_address=account["email"],
            subject=f"[TESTE] Resumo Moneypenny — {datetime.now(timezone.utc).strftime('%d/%m/%Y')}",
            html_body=html,
        )
    except Exception as e:
        raise HTTPException(500, f"Erro ao enviar: {e}")

    return {"ok": True}

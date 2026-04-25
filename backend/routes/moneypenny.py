import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth import get_current_user
from db import get_settings, get_supabase
from services.microsoft_graph import GraphClient, build_auth_url, exchange_code_for_tokens

router = APIRouter(prefix="/moneypenny", tags=["moneypenny"])
logger = logging.getLogger(__name__)

_pending_states: dict[str, str] = {}


class PrefsIn(BaseModel):
    send_hour_utc: int
    active: bool
    delivery_channel: str = "email"
    teams_webhook_url: str = ""
    whatsapp_phone: str = ""


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
    user_id = _resolve_user_id(current_user)

    profile_result = db.table("profiles").select("whatsapp_phone").eq("id", user_id).execute()
    profile_phone = (profile_result.data[0].get("whatsapp_phone") or "") if profile_result.data else ""

    result = db.table("notification_prefs").select("*").eq("user_id", user_id).execute()
    if not result.data:
        return {"send_hour_utc": 10, "active": True, "delivery_channel": "email", "teams_webhook_url": "", "whatsapp_phone": profile_phone}
    row = result.data[0]
    return {
        "send_hour_utc": row.get("send_hour_utc", 10),
        "active": row.get("active", True),
        "delivery_channel": row.get("delivery_channel") or "email",
        "teams_webhook_url": row.get("teams_webhook_url") or "",
        "whatsapp_phone": row.get("whatsapp_phone") or profile_phone,
    }


@router.put("/prefs")
def save_prefs(body: PrefsIn, current_user: dict = Depends(get_current_user)):
    if not (0 <= body.send_hour_utc <= 23):
        raise HTTPException(400, "send_hour_utc deve ser entre 0 e 23")
    if body.delivery_channel not in ("email", "teams", "whatsapp"):
        raise HTTPException(400, "Canal inválido. Use email, teams ou whatsapp.")
    db = get_supabase()
    user_id = _resolve_user_id(current_user)
    db.table("notification_prefs").upsert(
        {
            "user_id": user_id,
            "send_hour_utc": body.send_hour_utc,
            "active": body.active,
            "delivery_channel": body.delivery_channel,
            "teams_webhook_url": body.teams_webhook_url,
            "whatsapp_phone": body.whatsapp_phone,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
    if body.whatsapp_phone:
        db.table("profiles").update({"whatsapp_phone": body.whatsapp_phone}).eq("id", user_id).execute()
    return {"ok": True}


@router.post("/test")
async def send_test_summary(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    user_id = _resolve_user_id(current_user)

    account_result = (
        db.table("connected_accounts")
        .select("*")
        .eq("user_id", user_id)
        .eq("provider", "microsoft")
        .execute()
    )
    if not account_result.data:
        raise HTTPException(400, "Conta Microsoft não conectada")

    account = account_result.data[0]

    prefs_result = db.table("notification_prefs").select("*").eq("user_id", user_id).execute()
    prefs = prefs_result.data[0] if prefs_result.data else {}
    channel = prefs.get("delivery_channel") or "email"

    try:
        from services.microsoft_graph import refresh_access_token

        token_expiry = datetime.fromisoformat(account["token_expiry"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) >= token_expiry:
            refreshed = refresh_access_token(account["refresh_token"])
            new_expiry = datetime.now(timezone.utc) + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
            db.table("connected_accounts").update({
                "access_token": refreshed["access_token"],
                "refresh_token": refreshed.get("refresh_token") or account["refresh_token"],
                "token_expiry": new_expiry.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", account["id"]).execute()
            access_token = refreshed["access_token"]
        else:
            access_token = account["access_token"]

        graph = GraphClient(access_token)
        emails = graph.get_unread_emails_yesterday()
        events = graph.get_today_events()
        date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")

        if channel == "teams":
            webhook_url = prefs.get("teams_webhook_url") or ""
            if not webhook_url:
                raise HTTPException(400, "URL do webhook do Teams não configurada.")
            from services.summary import send_teams
            await send_teams(webhook_url, current_user["display_name"], emails, events)

        elif channel == "whatsapp":
            phone = prefs.get("whatsapp_phone") or ""
            if not phone:
                profile_result = db.table("profiles").select("whatsapp_phone").eq("id", user_id).execute()
                if profile_result.data:
                    phone = profile_result.data[0].get("whatsapp_phone") or ""
            if not phone:
                raise HTTPException(400, "Número de WhatsApp não configurado.")
            from services.summary import send_whatsapp
            await send_whatsapp(phone, current_user["display_name"], emails, events)

        else:
            from services.summary import _build_html
            html = _build_html(current_user["display_name"], emails, events)
            graph.send_mail(
                to_address=account["email"],
                subject=f"[TESTE] Resumo Moneypenny — {date_str}",
                html_body=html,
            )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Erro ao enviar resumo de teste para user %s", user_id)
        raise HTTPException(500, "Erro ao enviar resumo. Tente novamente.")

    return {"ok": True, "channel": channel}

import asyncio
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth import get_current_user
from db import get_settings, get_supabase
from services.app_logger import log_event
from services.microsoft_graph import (
    GraphClient,
    build_auth_url,
    exchange_code_for_tokens,
    get_valid_access_token,
)

router = APIRouter(prefix="/moneypenny", tags=["moneypenny"])
logger = logging.getLogger(__name__)

# state → (user_id, expires_at)
_pending_states: dict[str, tuple[str, float]] = {}
_STATE_TTL = 600  # 10 minutos

DEFAULT_CHANNELS: dict = {
    "email":    {"enabled": False, "content": ["emails", "calendar"]},
    "teams":    {"enabled": False, "content": ["emails", "calendar"]},
    "whatsapp": {"enabled": False, "content": ["calendar"]},
}


class PrefsIn(BaseModel):
    send_hour_utc: int
    active: bool
    channels: dict = {}
    teams_webhook_url: str = ""
    whatsapp_phone: str = ""


def _clean_expired_states() -> None:
    now = time.monotonic()
    expired = [k for k, (_, exp) in _pending_states.items() if now > exp]
    for k in expired:
        _pending_states.pop(k, None)


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
    _clean_expired_states()
    state = secrets.token_urlsafe(24)
    _pending_states[state] = (_resolve_user_id(current_user), time.monotonic() + _STATE_TTL)
    return {"url": build_auth_url(state)}


@router.get("/auth/microsoft/callback")
async def microsoft_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    entry = _pending_states.pop(state, None)
    if not entry:
        raise HTTPException(400, "Estado OAuth inválido ou expirado")

    user_id, expires_at = entry
    if time.monotonic() > expires_at:
        raise HTTPException(400, "Estado OAuth expirado")

    try:
        loop = asyncio.get_running_loop()
        tokens = await loop.run_in_executor(None, exchange_code_for_tokens, code)
    except ValueError as e:
        raise HTTPException(400, str(e))

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    graph = GraphClient(access_token)
    me = await graph.get_me()
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
        return {
            "send_hour_utc": 10,
            "active": True,
            "channels": DEFAULT_CHANNELS,
            "teams_webhook_url": "",
            "whatsapp_phone": profile_phone,
        }
    row = result.data[0]
    channels = row.get("channels_config") or DEFAULT_CHANNELS
    return {
        "send_hour_utc": row.get("send_hour_utc", 10),
        "active": row.get("active", True),
        "channels": channels,
        "teams_webhook_url": row.get("teams_webhook_url") or "",
        "whatsapp_phone": row.get("whatsapp_phone") or profile_phone,
    }


@router.put("/prefs")
def save_prefs(body: PrefsIn, current_user: dict = Depends(get_current_user)):
    if not (0 <= body.send_hour_utc <= 23):
        raise HTTPException(400, "send_hour_utc deve ser entre 0 e 23")
    db = get_supabase()
    user_id = _resolve_user_id(current_user)
    db.table("notification_prefs").upsert(
        {
            "user_id": user_id,
            "send_hour_utc": body.send_hour_utc,
            "active": body.active,
            "channels_config": body.channels,
            "teams_webhook_url": body.teams_webhook_url,
            "whatsapp_phone": body.whatsapp_phone,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
    if body.whatsapp_phone:
        db.table("profiles").update({"whatsapp_phone": body.whatsapp_phone}).eq("id", user_id).execute()
    return {"ok": True}


async def _send_whatsapp_bg(phone: str, display_name: str, events: list[dict], user_id: str) -> None:
    from services.summary import _build_calendar_text
    import httpx as _httpx
    try:
        text = _build_calendar_text(display_name, events)
        s = get_settings()
        url = f"{s.whatsapp_api_url.rstrip('/')}/message/sendText/{s.whatsapp_instance}"
        timeout = _httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
        async with _httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json={"number": phone, "text": text}, headers={"apikey": s.whatsapp_api_key})
            resp.raise_for_status()
        log_event("info", "moneypenny", "WhatsApp: mensagem enviada com confirmação", user_id=user_id)
    except _httpx.ReadTimeout:
        log_event("warning", "moneypenny", "WhatsApp: enviado (sem confirmação — Evolution API lenta)", user_id=user_id)
    except _httpx.ConnectError as exc:
        log_event("error", "moneypenny", "WhatsApp: servidor inacessível", user_id=user_id, detail=str(exc))
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc!r}"
        logger.exception("Erro ao enviar WhatsApp em background para user %s", user_id)
        log_event("error", "moneypenny", "WhatsApp: erro ao enviar", user_id=user_id, detail=detail)


@router.post("/test")
async def send_test_summary(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
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
    channels: dict = prefs.get("channels_config") or {}
    enabled = {k: v for k, v in channels.items() if v.get("enabled")}

    if not enabled:
        raise HTTPException(400, "Nenhum canal de entrega habilitado. Configure e salve primeiro.")

    try:
        access_token = await get_valid_access_token(account, db)
        graph = GraphClient(access_token)
        date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        display_name = current_user["display_name"]
        sent: list[str] = []
        has_background = False

        emails_data: list[dict] | None = None
        events_data: list[dict] | None = None

        for ch_name, ch_cfg in enabled.items():
            content = ch_cfg.get("content", [])
            needs_emails = "emails" in content
            needs_events = "calendar" in content

            if needs_emails and emails_data is None:
                emails_data = await graph.get_unread_emails_yesterday()
            if needs_events and events_data is None:
                events_data = await graph.get_today_events()

            emails_out = emails_data if needs_emails else []
            events_out = events_data if needs_events else []

            if ch_name == "email":
                from services.summary import _build_html
                html = _build_html(display_name, emails_out, events_out)
                await graph.send_mail(
                    to_address=account["email"],
                    subject=f"[TESTE] Resumo Moneypenny — {date_str}",
                    html_body=html,
                )
                sent.append("email")

            elif ch_name == "teams":
                webhook_url = prefs.get("teams_webhook_url") or ""
                if not webhook_url:
                    raise HTTPException(400, "URL do webhook do Teams não configurada.")
                from services.summary import send_teams
                await send_teams(webhook_url, display_name, emails_out, events_out)
                sent.append("teams")

            elif ch_name == "whatsapp":
                phone = prefs.get("whatsapp_phone") or ""
                if not phone:
                    pr = db.table("profiles").select("whatsapp_phone").eq("id", user_id).execute()
                    if pr.data:
                        phone = pr.data[0].get("whatsapp_phone") or ""
                if not phone:
                    raise HTTPException(400, "Número de WhatsApp não configurado.")
                background_tasks.add_task(_send_whatsapp_bg, phone, display_name, events_out, user_id)
                log_event("info", "moneypenny", "Envio WhatsApp agendado em background", user_id=user_id)
                sent.append("whatsapp")
                has_background = True

    except HTTPException:
        raise
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc!r}"
        logger.exception("Erro ao enviar resumo de teste para user %s", user_id)
        log_event("error", "moneypenny", "Erro ao enviar resumo de teste", user_id=user_id, detail=detail)
        raise HTTPException(500, f"Erro ao enviar resumo: {detail}")

    log_event("info", "moneypenny", f"Resumo de teste enviado via {sent}", user_id=user_id)
    return {"ok": True, "sent": sent, "background": has_background}

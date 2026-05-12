import asyncio
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from db import get_settings
from services.conversation import ConversationFSM
from services.notification_worker import process_freshservice_event

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

_fsm = ConversationFSM()


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    try:
        event = payload.get("event", "")
        data = payload.get("data", {})

        if event != "messages.upsert":
            return JSONResponse({"ok": True})

        key = data.get("key", {})
        if key.get("fromMe", True):
            return JSONResponse({"ok": True})

        remote_jid = key.get("remoteJid", "")
        # Ignore group messages
        if "@g.us" in remote_jid:
            return JSONResponse({"ok": True})

        # Use only the numeric part as DB key; keep full JID for sending
        # (@lid contacts need the full JID, @s.whatsapp.net works with number only)
        phone = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
        send_to = remote_jid  # pass full JID to Evolution API
        if not phone:
            return JSONResponse({"ok": True})

        message = data.get("message", {})
        text = (
            message.get("conversation")
            or message.get("extendedTextMessage", {}).get("text")
            or ""
        ).strip()

        if not text:
            return JSONResponse({"ok": True})

        reply = await asyncio.to_thread(_fsm.process, phone, text)

        if reply:
            s = get_settings()
            import httpx
            url = f"{s.whatsapp_api_url.rstrip('/')}/message/sendText/{s.whatsapp_instance}"
            timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    await client.post(
                        url,
                        json={"number": send_to, "text": reply, "linkPreview": False},
                        headers={"apikey": s.whatsapp_api_key},
                    )
            except httpx.ReadTimeout:
                pass
            except Exception as exc:
                logger.error("WhatsApp send error for %s: %s", phone, exc)

    except Exception:
        logger.exception("Error processing WhatsApp webhook")

    return JSONResponse({"ok": True})


@router.post("/webhooks/freshservice")
async def freshservice_webhook(
    request: Request,
    secret: str = Query(default=""),
) -> JSONResponse:
    s = get_settings()

    if s.freshservice_webhook_secret and secret != s.freshservice_webhook_secret:
        logger.warning("Freshservice webhook: invalid secret")
        return JSONResponse({"ok": True})

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    try:
        await asyncio.to_thread(process_freshservice_event, payload)
    except Exception:
        logger.exception("Error processing Freshservice webhook event")

    return JSONResponse({"ok": True})

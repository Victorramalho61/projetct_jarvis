import asyncio
import logging
import time
from collections import OrderedDict

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import get_settings
from services.conversation import ConversationFSM
from services.notification_worker import process_freshservice_event

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)
_limiter = Limiter(key_func=get_remote_address)

# Limite máximo de texto aceito (evita payloads gigantes)
_MAX_TEXT_LEN = 2000

_fsm = ConversationFSM()

# Deduplication cache: message_id -> expiry timestamp (TTL 60s, max 1000 entries)
_seen_msg_ids: OrderedDict[str, float] = OrderedDict()
_DEDUP_TTL = 60.0
_DEDUP_MAX = 1000


def _is_duplicate(msg_id: str) -> bool:
    now = time.monotonic()
    # Evict expired entries
    while _seen_msg_ids:
        oldest_id, expiry = next(iter(_seen_msg_ids.items()))
        if expiry <= now:
            _seen_msg_ids.popitem(last=False)
        else:
            break
    if len(_seen_msg_ids) >= _DEDUP_MAX:
        _seen_msg_ids.popitem(last=False)
    if msg_id in _seen_msg_ids:
        return True
    _seen_msg_ids[msg_id] = now + _DEDUP_TTL
    return False


@router.post("/webhooks/whatsapp")
@_limiter.limit("30/minute")
async def whatsapp_webhook(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    try:
        event = payload.get("event", "")
        # WAHA: evento "message"; ignorar outros (connection_update, etc.)
        if event != "message":
            return JSONResponse({"ok": True})

        waha = payload.get("payload", {})

        if waha.get("fromMe", True):
            return JSONResponse({"ok": True})

        msg_id = waha.get("id", "")
        if msg_id and _is_duplicate(msg_id):
            return JSONResponse({"ok": True})

        remote_jid = waha.get("from", "")
        # Ignorar mensagens de grupo
        if "@g.us" in remote_jid:
            return JSONResponse({"ok": True})

        phone = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
        send_to = remote_jid  # WAHA usa @c.us — mantém JID completo para resposta
        if not phone:
            return JSONResponse({"ok": True})

        text = (waha.get("body") or "").strip()

        if not text:
            return JSONResponse({"ok": True})

        # Rejeita mensagens excessivamente longas (DoS / injeção)
        if len(text) > _MAX_TEXT_LEN:
            logger.warning("Oversized message from %s (%d chars) — truncated", phone[-4:], len(text))
            text = text[:_MAX_TEXT_LEN]

        reply = await asyncio.to_thread(_fsm.process, phone, text, send_to)

        if reply:
            s = get_settings()
            import httpx
            from services.whatsapp import _to_chat_id
            url = f"{s.whatsapp_api_url.rstrip('/')}/api/sendText"
            timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    await client.post(
                        url,
                        json={"session": s.whatsapp_instance, "chatId": _to_chat_id(send_to), "text": reply},
                        headers={"X-Api-Key": s.whatsapp_api_key},
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

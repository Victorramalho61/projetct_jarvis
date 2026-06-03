import logging

import httpx

from db import get_settings

_logger = logging.getLogger(__name__)


def _to_chat_id(phone: str) -> str:
    """Normaliza número/JID para formato chatId do WAHA.
    Preserva @lid (WhatsApp multi-device) e @g.us (grupos).
    Converte @s.whatsapp.net para @c.us.
    """
    if "@" in phone:
        num, suffix = phone.split("@", 1)
        if suffix in ("lid", "g.us"):
            return phone  # preserva JID original
        return f"{num}@c.us"
    return f"{phone}@c.us"


async def send_text(phone: str, text: str) -> bool:
    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_instance:
        _logger.warning("WhatsApp not configured, skipping send to %s", phone)
        return False
    url = f"{s.whatsapp_api_url}/api/sendText"
    payload = {"session": s.whatsapp_instance, "chatId": _to_chat_id(phone), "text": text}
    headers = {"X-Api-Key": s.whatsapp_api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                _logger.error("WhatsApp send failed: %s %s", r.status_code, r.text[:200])
                return False
        return True
    except Exception as exc:
        _logger.error("WhatsApp send error to %s: %s", phone, exc)
        return False

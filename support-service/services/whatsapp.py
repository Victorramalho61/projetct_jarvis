import logging

import httpx

from db import get_settings

_logger = logging.getLogger(__name__)


async def send_text(phone: str, text: str) -> bool:
    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_instance:
        _logger.warning("WhatsApp not configured, skipping send to %s", phone)
        return False
    url = f"{s.whatsapp_api_url}/message/sendText/{s.whatsapp_instance}"
    payload = {"number": phone, "text": text}
    headers = {"apikey": s.whatsapp_api_key}
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

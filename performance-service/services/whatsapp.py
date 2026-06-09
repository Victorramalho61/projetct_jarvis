import logging

import httpx

from db import get_settings

_logger = logging.getLogger(__name__)


def _to_chat_id(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if "@" in phone:
        num, suffix = phone.split("@", 1)
        if suffix in ("lid", "g.us"):
            return phone
        return f"{num}@c.us"
    return f"{digits}@c.us"


def send_text(phone: str, text: str) -> bool:
    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_instance:
        _logger.warning("WhatsApp not configured, skipping send to %s", phone)
        return False
    url = f"{s.whatsapp_api_url}/api/sendText"
    payload = {"session": s.whatsapp_instance, "chatId": _to_chat_id(phone), "text": text}
    headers = {"X-Api-Key": s.whatsapp_api_key}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                _logger.error("WhatsApp send failed: %s %s", r.status_code, r.text[:200])
                return False
        return True
    except Exception as exc:
        _logger.error("WhatsApp send error to %s: %s", phone, exc)
        return False


def send_self_evaluation_whatsapp(
    employee_name: str, phone: str,
    token: str, cycle_name: str, frontend_url: str,
) -> bool:
    link = f"{frontend_url}/auto-avaliar/{token}"
    text = (
        f"Olá, {employee_name}! 👋\n\n"
        f"*Auto-Avaliação de Desempenho — {cycle_name}*\n\n"
        "Chegou o momento da sua auto-avaliação. Reserve alguns minutos para "
        "refletir sobre seu desempenho neste período e responda com honestidade.\n\n"
        f"🔗 Acesse aqui: {link}\n\n"
        "_Link individual e intransferível. Dúvidas: rh@voetur.com.br_"
    )
    return send_text(phone, text)

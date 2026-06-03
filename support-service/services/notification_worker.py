import logging
import re
from datetime import datetime, timezone

import httpx
import pytz

from db import get_settings, get_supabase
from services.freshservice_connector import FreshserviceConnector

logger = logging.getLogger(__name__)

TZ_BR = pytz.timezone("America/Sao_Paulo")

EVENT_MESSAGES: dict[str, str] = {
    "agent_assigned":   "👤 Chamado *#{id}* atribuído a *{agent}*",
    "priority_changed": "⚡ Prioridade do chamado *#{id}* alterada para *{value}*",
}

_CLOSED_STATUSES = {"ticket_resolved", "ticket_closed"}


def _strip_html(html: str) -> str:
    """Remove tags HTML e decodifica entidades básicas."""
    text = re.sub(r"<[^>]+>", "", html)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return text.strip()


def _format_br_datetime(iso_str: str) -> str:
    """Converte ISO UTC para horário de Brasília formatado."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_br = dt.astimezone(TZ_BR)
        return dt_br.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return ""


def process_freshservice_event(payload: dict) -> None:
    db = get_supabase()
    s = get_settings()
    fs = FreshserviceConnector()

    ticket_id = payload.get("ticket_id") or payload.get("id")
    event_type = payload.get("event") or payload.get("event_type") or "status_changed"

    if not ticket_id:
        logger.warning("Freshservice event missing ticket_id: %s", payload)
        return

    # Idempotency check (exceto note_added — pode ter múltiplas notas)
    if event_type not in ("note_added",):
        existing = (
            db.table("support_notifications")
            .select("id, sent")
            .eq("freshservice_ticket_id", int(ticket_id))
            .eq("event_type", event_type)
            .execute()
        )
        if existing.data and existing.data[0].get("sent"):
            logger.info("Duplicate event %s for ticket %s — skipping", event_type, ticket_id)
            return

    # Look up phone from support_tickets
    ticket_row = (
        db.table("support_tickets")
        .select("phone")
        .eq("freshservice_ticket_id", int(ticket_id))
        .execute()
    )
    if not ticket_row.data:
        logger.info("No support_ticket record for freshservice_ticket_id %s — discarding", ticket_id)
        return

    phone = ticket_row.data[0]["phone"]

    # Build message based on event type
    text = _build_message(event_type, ticket_id, payload, fs)
    if not text:
        logger.info("No message built for event %s — skipping", event_type)
        return

    # Send via WAHA
    sent = False
    if s.whatsapp_api_url and phone:
        from services.whatsapp import _to_chat_id
        url = f"{s.whatsapp_api_url.rstrip('/')}/api/sendText"
        timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(
                    url,
                    json={"session": s.whatsapp_instance, "chatId": _to_chat_id(phone), "text": text},
                    headers={"X-Api-Key": s.whatsapp_api_key},
                )
                r.raise_for_status()
            sent = True
        except httpx.ReadTimeout:
            sent = True
        except Exception as exc:
            logger.error("WhatsApp send error for ticket %s: %s", ticket_id, exc)

    # Se ticket resolvido: atualiza estado da conversa para aguardar satisfação
    if event_type in _CLOSED_STATUSES and sent:
        try:
            db.table("support_conversations").update({
                "state": "awaiting_satisfaction",
                "context": {"resolved_ticket_id": str(ticket_id)},
            }).eq("phone", phone).execute()
        except Exception as exc:
            logger.error("Failed to update conversation state to awaiting_satisfaction: %s", exc)

    # Persist notification
    try:
        db.table("support_notifications").upsert(
            {
                "freshservice_ticket_id": int(ticket_id),
                "event_type": event_type,
                "phone": phone,
                "sent": sent,
                "payload": payload,
            },
            on_conflict="freshservice_ticket_id,event_type",
        ).execute()
    except Exception as exc:
        logger.error("Failed to persist notification: %s", exc)

    # Update ticket status on resolve/close
    if event_type in _CLOSED_STATUSES:
        try:
            db.table("support_tickets").update({"status": 5}).eq(
                "freshservice_ticket_id", int(ticket_id)
            ).execute()
        except Exception as exc:
            logger.error("Failed to update ticket status: %s", exc)


def _build_message(event_type: str, ticket_id, payload: dict, fs: FreshserviceConnector) -> str:
    """Monta a mensagem WhatsApp de acordo com o tipo de evento."""

    if event_type == "note_added":
        note = payload.get("note", {})
        note_body = note.get("body_text") or _strip_html(note.get("body") or "")
        if not note_body:
            # Tenta campos alternativos do payload
            note_body = payload.get("body_text") or _strip_html(payload.get("body") or "")
        preview = (note_body[:400] + "...") if len(note_body) > 400 else note_body
        if preview:
            return (
                f"💬 *Nova mensagem no chamado #{ticket_id}*\n\n"
                f"{preview}"
            )
        return f"💬 Nova atualização no chamado *#{ticket_id}*"

    if event_type in _CLOSED_STATUSES:
        ticket = fs.get_ticket(int(ticket_id))
        resolution_html = ticket.get("resolution_notes") or ticket.get("resolution_note") or ""
        resolution_text = _strip_html(resolution_html)

        resolved_at = ticket.get("resolved_at") or ticket.get("updated_at") or ""
        data_hora = _format_br_datetime(resolved_at) if resolved_at else ""

        msg = f"✅ *Sua solicitação foi atendida!*\n\n"
        msg += f"Chamado *#{ticket_id}* resolvido"
        if data_hora:
            msg += f" em {data_hora}"
        msg += ".\n\n"

        if resolution_text:
            preview = (resolution_text[:500] + "...") if len(resolution_text) > 500 else resolution_text
            msg += f"📋 *Retorno da equipe:*\n{preview}\n\n"

        msg += "Ficou satisfeito com o atendimento?\n1 - 👍 Sim\n2 - 🔄 Não, quero reabrir"
        return msg

    if event_type == "status_changed":
        value = payload.get("status") or payload.get("value") or ""
        return f"🔔 Status do chamado *#{ticket_id}* atualizado: *{value}*"

    # Eventos genéricos
    template = EVENT_MESSAGES.get(event_type)
    if template:
        value = payload.get("status") or payload.get("value") or ""
        agent = payload.get("agent") or payload.get("agent_name") or ""
        return template.format(id=ticket_id, value=value, agent=agent)

    return ""

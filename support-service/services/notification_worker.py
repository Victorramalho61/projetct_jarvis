import logging

import httpx

from db import get_settings, get_supabase

logger = logging.getLogger(__name__)

EVENT_MESSAGES: dict[str, str] = {
    "status_changed":   "\U0001f514 Status do chamado #{id} atualizado: *{value}*",
    "note_added":       "\U0001f4ac Nova mensagem no chamado #{id}",
    "ticket_resolved":  "✅ Chamado #{id} resolvido! Ficou satisfeito com o atendimento?\n1 - Sim ✅\n2 - Reabrir \U0001f504",
    "agent_assigned":   "\U0001f464 Chamado #{id} atribuído a *{agent}*",
    "priority_changed": "⚡ Prioridade do chamado #{id} alterada para *{value}*",
}

# Freshservice status IDs that mean resolved/closed
_CLOSED_STATUSES = {"ticket_resolved", "ticket_closed"}


def process_freshservice_event(payload: dict) -> None:
    db = get_supabase()
    s = get_settings()

    ticket_id = payload.get("ticket_id") or payload.get("id")
    event_type = payload.get("event") or payload.get("event_type") or "status_changed"

    if not ticket_id:
        logger.warning("Freshservice event missing ticket_id: %s", payload)
        return

    # Idempotency check
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

    # Build message
    template = EVENT_MESSAGES.get(event_type, "\U0001f514 Atualização no chamado #{id}")
    value = payload.get("status") or payload.get("value") or ""
    agent = payload.get("agent") or payload.get("agent_name") or ""
    text = template.format(id=ticket_id, value=value, agent=agent)

    # Send via Evolution API
    sent = False
    if s.whatsapp_api_url and phone:
        url = f"{s.whatsapp_api_url.rstrip('/')}/message/sendText/{s.whatsapp_instance}"
        timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(
                    url,
                    json={"number": phone, "text": text},
                    headers={"apikey": s.whatsapp_api_key},
                )
                r.raise_for_status()
            sent = True
        except httpx.ReadTimeout:
            sent = True  # Server received it
        except Exception as exc:
            logger.error("WhatsApp send error for ticket %s: %s", ticket_id, exc)

    # Persist notification (upsert for idempotency)
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

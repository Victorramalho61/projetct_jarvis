import logging
from typing import Any

from db import get_supabase

_logger = logging.getLogger(__name__)

_EVENT_MESSAGES = {
    "goal_proposed": ("Nova meta atribuída", "Uma nova meta foi proposta para você. Acesse Desempenho para revisar e assinar."),
    "goal_pending_ack": ("Meta aguardando assinatura", "Você possui uma meta pendente de assinatura. Acesse Desempenho para assinar."),
    "review_pending": ("Avaliação pendente", "Você tem uma avaliação de liderado aguardando preenchimento."),
    "review_result_available": ("Resultado de avaliação disponível", "O resultado da sua avaliação está disponível. Acesse Desempenho para tomar ciência."),
    "review_disputed": ("Avaliação contestada", "Uma avaliação foi contestada pelo colaborador e requer atenção do RH."),
}


def notify(event: str, recipient_username: str, extra: dict[str, Any] | None = None) -> None:
    """Persiste notificação em app_notifications para o usuário destinatário."""
    try:
        title, body = _EVENT_MESSAGES.get(event, (event, ""))
        if extra:
            body = body + " " + " | ".join(f"{k}: {v}" for k, v in extra.items())
        db = get_supabase()
        db.table("app_notifications").insert({
            "type": "performance",
            "title": title,
            "body": body[:500],
            "recipient": recipient_username,
            "event": event,
            "read": False,
        }).execute()
    except Exception as exc:
        _logger.warning("Failed to send notification (event=%s, recipient=%s): %s", event, recipient_username, exc)

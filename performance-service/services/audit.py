import logging
from typing import Any

from db import get_supabase

_logger = logging.getLogger(__name__)


def log_action(
    entity_type: str,
    entity_id: str,
    action: str,
    old_data: Any,
    new_data: Any,
    actor: str,
    request=None,
) -> None:
    """Grava em performance_audit_logs. Chamado em todo write de review, goal, etc."""
    try:
        db = get_supabase()
        db.table("performance_audit_logs").insert({
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "action": action,
            "old_data": old_data,
            "new_data": new_data,
            "actor": actor,
            "ip_address": request.client.host if request and request.client else None,
            "user_agent": request.headers.get("user-agent") if request else None,
        }).execute()
    except Exception as exc:
        _logger.error("Failed to write audit log: %s", exc)

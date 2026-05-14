import logging
from db import get_supabase

_logger = logging.getLogger(__name__)


def log_event(
    level: str,
    module: str,
    message: str,
    user_id: str | None = None,
    detail: str | None = None,
    trace_id: str | None = None,
) -> None:
    try:
        db = get_supabase()
        db.table("app_logs").insert({
            "level": level,
            "module": module,
            "message": message,
            "user_id": user_id,
            "detail": detail,
            "trace_id": trace_id,
        }).execute()
    except Exception as exc:
        _logger.error("Failed to write app log: %s", exc)

"""
app_logger — logging centralizado no Supabase.

O SupabaseHandler captura automaticamente qualquer logger.error() / logger.exception()
de qualquer módulo do serviço e persiste em app_logs.
"""
import logging
import threading
import traceback

_logger = logging.getLogger(__name__)

_in_emit = threading.local()


class SupabaseHandler(logging.Handler):
    def __init__(self, service_name: str):
        super().__init__(level=logging.ERROR)
        self._service = service_name

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_in_emit, "active", False):
            return
        _in_emit.active = True
        try:
            from db import get_supabase
            detail: str | None = None
            if record.exc_info:
                detail = "".join(traceback.format_exception(*record.exc_info))[:4000]
            get_supabase().table("app_logs").insert({
                "level":   "error",
                "module":  self._service,
                "message": record.getMessage()[:500],
                "detail":  detail,
            }).execute()
        except Exception:
            pass
        finally:
            _in_emit.active = False


def setup_log_forwarding(service_name: str) -> None:
    root = logging.getLogger()
    if any(isinstance(h, SupabaseHandler) for h in root.handlers):
        return
    root.addHandler(SupabaseHandler(service_name))
    _logger.info("app_logger: SupabaseHandler registrado para '%s'", service_name)


def log_event(
    level: str,
    module: str,
    message: str,
    user_id: str | None = None,
    detail: str | None = None,
    trace_id: str | None = None,
) -> None:
    try:
        from db import get_supabase
        get_supabase().table("app_logs").insert({
            "level":    level,
            "module":   module,
            "message":  message,
            "user_id":  user_id,
            "detail":   detail,
            "trace_id": trace_id,
        }).execute()
    except Exception as exc:
        _logger.error("Failed to write app log: %s", exc)

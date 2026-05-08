import time

from fastapi import APIRouter

router = APIRouter()
_START = time.monotonic()
_SERVICE = "expenses-service"
_VERSION = "1.0.0"


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": _SERVICE,
        "version": _VERSION,
        "uptime_seconds": round(time.monotonic() - _START),
    }


@router.get("/ready")
def ready():
    import time as _time
    from db import get_supabase, get_settings

    components: dict = {}
    overall = "ok"

    # Supabase
    t0 = _time.monotonic()
    try:
        s = get_settings()
        import httpx
        r = httpx.get(f"{s.supabase_url}/rest/v1/", timeout=3)
        latency = round((_time.monotonic() - t0) * 1000)
        components["database"] = {"status": "ok" if r.status_code < 500 else "degraded", "latency_ms": latency}
    except Exception:
        components["database"] = {"status": "down", "latency_ms": None}
        overall = "degraded"

    # Benner SQL
    t0 = _time.monotonic()
    try:
        from services.resilience import get_benner_circuit_breaker, CircuitOpenError
        cb = get_benner_circuit_breaker()
        if cb.is_open():
            components["benner"] = {"status": "down", "latency_ms": None, "detail": "circuit open"}
            overall = "degraded"
        else:
            from db import get_sql_connection
            conn = get_sql_connection()
            conn.close()
            latency = round((_time.monotonic() - t0) * 1000)
            components["benner"] = {"status": "ok", "latency_ms": latency}
    except Exception as exc:
        components["benner"] = {"status": "down", "latency_ms": None, "detail": str(exc)[:80]}
        overall = "degraded"

    return {
        "status": overall,
        "service": _SERVICE,
        "uptime_seconds": round(time.monotonic() - _START),
        "components": components,
    }

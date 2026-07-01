import time

from fastapi import APIRouter, Request
from limiter import limiter

router = APIRouter()
_START = time.monotonic()


@router.get("/health")
@limiter.limit("60/minute")
def health(request: Request):
    return {"status": "ok", "service": "experiencia-service"}


@router.get("/ready")
@limiter.limit("30/minute")
def ready(request: Request):
    import time as _time
    from db import get_settings
    components: dict = {}
    overall = "ok"

    t0 = _time.monotonic()
    try:
        s = get_settings()
        import httpx
        r = httpx.get(f"{s.supabase_url}/rest/v1/", headers={"apikey": s.supabase_key}, timeout=3)
        latency = round((_time.monotonic() - t0) * 1000)
        components["database"] = {"status": "ok" if r.status_code < 500 else "degraded", "latency_ms": latency}
    except Exception:
        components["database"] = {"status": "down", "latency_ms": None}
        overall = "degraded"

    t0 = _time.monotonic()
    try:
        from services.resilience import get_benner_circuit_breaker
        cb = get_benner_circuit_breaker()
        if cb.is_open():
            components["benner"] = {"status": "down", "detail": "circuit open"}
            overall = "degraded"
        else:
            from db import get_sql_connection
            conn = get_sql_connection()
            conn.close()
            components["benner"] = {"status": "ok", "latency_ms": round((_time.monotonic() - t0) * 1000)}
    except Exception as exc:
        components["benner"] = {"status": "down", "detail": str(exc)[:80]}
        overall = "degraded"

    return {
        "status": overall,
        "service": "experiencia-service",
        "uptime_seconds": round(time.monotonic() - _START),
        "components": components,
    }

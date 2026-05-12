import time

import httpx
from fastapi import APIRouter

from db import get_settings

router = APIRouter()
_START = time.monotonic()
_SERVICE = "support-service"
_VERSION = "1.0.0"


@router.get("/health")
def health():
    return {"status": "ok", "service": _SERVICE, "version": _VERSION,
            "uptime_seconds": round(time.monotonic() - _START)}


@router.get("/ready")
async def ready():
    checks: dict = {}
    s = get_settings()

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.supabase_url}/rest/v1/",
                            headers={"apikey": s.supabase_key})
        checks["database"] = {"status": "ok" if r.status_code < 500 else "degraded",
                               "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception:
        checks["database"] = {"status": "down", "latency_ms": None}

    if s.whatsapp_api_url:
        t1 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(
                    f"{s.whatsapp_api_url.rstrip('/')}/instance/fetchInstances",
                    headers={"apikey": s.whatsapp_api_key},
                )
            checks["whatsapp"] = {
                "status": "ok" if r.status_code < 500 else "degraded",
                "latency_ms": int((time.monotonic() - t1) * 1000),
            }
        except Exception:
            checks["whatsapp"] = {"status": "down", "latency_ms": None}

    overall = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "service": _SERVICE,
            "uptime_seconds": round(time.monotonic() - _START), "components": checks}

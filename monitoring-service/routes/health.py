import time

import httpx
from fastapi import APIRouter

from db import get_settings

router = APIRouter()
_START = time.monotonic()
_SERVICE = "monitoring-service"
_VERSION = "1.0.0"


@router.get("/health")
def health():
    return {"status": "ok", "service": _SERVICE, "version": _VERSION,
            "uptime_seconds": round(time.monotonic() - _START)}


@router.get("/ready")
async def ready():
    components: dict = {}
    s = get_settings()

    # Supabase
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.supabase_url}/rest/v1/", headers={"apikey": s.supabase_key})
        components["database"] = {"status": "ok" if r.status_code < 500 else "degraded",
                                   "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception:
        components["database"] = {"status": "down", "latency_ms": None}

    # Monitor Agent
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.monitor_agent_url}/metrics")
        components["monitor_agent"] = {"status": "ok" if r.status_code == 200 else "degraded",
                                        "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception:
        components["monitor_agent"] = {"status": "down", "latency_ms": None}

    overall = "ok" if all(v.get("status") == "ok" for v in components.values()) else "degraded"
    return {"status": overall, "service": _SERVICE,
            "uptime_seconds": round(time.monotonic() - _START), "components": components}

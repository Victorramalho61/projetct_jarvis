import time

import httpx
from fastapi import APIRouter

from db import get_settings

router = APIRouter()
_START = time.monotonic()
_SERVICE = "agents-service"
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
        checks["db"] = {"status": "ok" if r.status_code < 500 else "error",
                        "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        checks["db"] = {"status": "error", "detail": str(e)}

    overall = "ok" if all(v["status"] == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "service": _SERVICE, "checks": checks}

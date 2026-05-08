import time

import httpx
from fastapi import APIRouter

from db import get_settings

router = APIRouter()
_START = time.monotonic()
_SERVICE = "moneypenny-service"
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
    except Exception as e:
        checks["database"] = {"status": "down", "latency_ms": None}

    if s.microsoft_tenant_id:
        t1 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(
                    f"https://login.microsoftonline.com/{s.microsoft_tenant_id}/v2.0/.well-known/openid-configuration"
                )
            checks["microsoft_365"] = {
                "status": "ok" if r.status_code == 200 else "degraded",
                "latency_ms": int((time.monotonic() - t1) * 1000)
            }
        except Exception as e:
            checks["microsoft_365"] = {"status": "down", "latency_ms": None}

    overall = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "service": _SERVICE,
            "uptime_seconds": round(time.monotonic() - _START), "components": checks}

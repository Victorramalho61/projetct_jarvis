import time

from fastapi import APIRouter

router = APIRouter()
_start = time.time()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "fiscal-service",
        "uptime_seconds": int(time.time() - _start),
    }


@router.get("/ready")
def ready():
    from db import get_supabase
    try:
        get_supabase().table("fiscal_companies").select("id").limit(1).execute()
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "service": "fiscal-service",
        "uptime_seconds": int(time.time() - _start),
        "components": {"database": "ok" if db_ok else "error"},
    }

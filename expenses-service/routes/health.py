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

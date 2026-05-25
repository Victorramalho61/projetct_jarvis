import time

from fastapi import APIRouter

router = APIRouter(prefix="/api/hermes")
_start = time.time()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hermes-service",
        "uptime_seconds": int(time.time() - _start),
    }


@router.get("/ready")
def ready():
    from pathlib import Path
    config_ok = Path("/root/.hermes").exists()
    return {
        "status": "ok",
        "service": "hermes-service",
        "uptime_seconds": int(time.time() - _start),
        "components": {"hermes_home": "ok" if config_ok else "error"},
    }

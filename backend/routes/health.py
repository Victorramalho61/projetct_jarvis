import httpx
from fastapi import APIRouter

from db import get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    db_status = "ok"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{settings.supabase_url}/rest/v1/",
                headers={"apikey": settings.supabase_key},
            )
            if r.status_code >= 500:
                db_status = "degraded"
    except Exception:
        db_status = "unreachable"
    return {"api": "ok", "db": db_status}

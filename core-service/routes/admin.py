import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/logs")
def get_logs(
    _: Annotated[dict, Depends(require_role("admin"))],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    try:
        db = get_supabase()
        result = (
            db.table("app_logs")
            .select("id,created_at,level,module,message,detail,user_id", count="exact")
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
            .execute()
        )
        return {"data": result.data, "total": result.count or 0, "limit": limit, "offset": offset}
    except Exception as exc:
        logger.exception("Erro ao buscar logs")
        raise HTTPException(500, f"Erro ao buscar logs: {exc}")

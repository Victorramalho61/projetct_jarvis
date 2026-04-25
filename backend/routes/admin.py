import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/logs")
def get_logs(_: Annotated[dict, Depends(require_role("admin"))]) -> list[dict]:
    try:
        db = get_supabase()
        result = (
            db.table("app_logs")
            .select("id,created_at,level,module,message,detail,user_id")
            .order("created_at", desc=True)
            .limit(300)
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.exception("Erro ao buscar logs")
        raise HTTPException(500, f"Erro ao buscar logs: {exc}")

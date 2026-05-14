import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import require_role
from db import get_supabase
from services.audit import log_action

router = APIRouter(prefix="/api/performance/competencies")
_logger = logging.getLogger(__name__)

_PERF_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor", "colaborador")
_RH_ADMIN = ("admin", "rh")


class CompetencyScoreCreate(BaseModel):
    competency_id: str
    score: float
    justification: str | None = None


@router.get("")
def list_competencies(
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
    category: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_competencies").select("*").order("category").order("name")
    if category:
        query = query.eq("category", category)
    return query.execute().data


@router.post("/reviews/{review_id}/scores", status_code=status.HTTP_201_CREATED)
def upsert_competency_scores(
    review_id: str,
    scores: list[CompetencyScoreCreate],
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    db = get_supabase()
    rev = db.table("performance_reviews").select("id").eq("id", review_id).execute()
    if not rev.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    rows = [
        {
            "review_id": review_id,
            "competency_id": s.competency_id,
            "score": s.score,
            "justification": s.justification,
        }
        for s in scores
    ]
    db.table("performance_competency_scores").upsert(rows, on_conflict="review_id,competency_id").execute()
    log_action("review", review_id, "competency_scores_upsert", None, {"count": len(rows)}, current_user["username"], request)
    return {"ok": True, "saved": len(rows)}


@router.get("/reviews/{review_id}/scores")
def get_competency_scores(
    review_id: str,
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> list[dict]:
    db = get_supabase()
    return db.table("performance_competency_scores").select("*, performance_competencies(*)").eq("review_id", review_id).execute().data

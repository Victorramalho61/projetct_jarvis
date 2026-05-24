import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import require_role
from db import get_supabase
from services.audit import log_action

router = APIRouter(prefix="/api/performance/admin")
_logger = logging.getLogger(__name__)

_RH_ADMIN = ("admin", "rh")


class CalibrationCreate(BaseModel):
    review_id: str
    calibrated_score: float
    justification: str


@router.get("/dashboard")
def dashboard(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str | None = None,
) -> dict:
    db = get_supabase()
    query = db.table("performance_reviews").select("status, final_score")
    if cycle_id:
        query = query.eq("cycle_id", cycle_id)
    reviews = query.execute().data

    total = len(reviews)
    by_status: dict[str, int] = {}
    score_distribution: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}

    for r in reviews:
        s = r.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        if r.get("final_score") is not None:
            bucket = str(min(5, max(1, round(r["final_score"]))))
            score_distribution[bucket] = score_distribution.get(bucket, 0) + 1

    completed = by_status.get("completed", 0)
    completude_pct = round((completed / total * 100), 1) if total else 0

    pending_ack = db.table("performance_review_acknowledgments").select("id").is_("acknowledged_at", "null").execute().data

    return {
        "total_reviews": total,
        "by_status": by_status,
        "score_distribution": score_distribution,
        "completude_pct": completude_pct,
        "pending_acknowledgments": len(pending_ack),
    }


@router.get("/audit-log")
def audit_log(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    entity_type: str | None = None,
    actor: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_audit_logs").select("*")
    if entity_type:
        query = query.eq("entity_type", entity_type)
    if actor:
        query = query.eq("actor", actor)
    if from_ts:
        query = query.gte("ts", from_ts)
    if to_ts:
        query = query.lte("ts", to_ts)
    return query.order("ts", desc=True).range(offset, offset + limit - 1).execute().data


@router.post("/calibrations", status_code=status.HTTP_201_CREATED)
def create_calibration(
    body: CalibrationCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    rev = db.table("performance_reviews").select("final_score,cycle_id").eq("id", body.review_id).execute()
    if not rev.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    original_score = rev.data[0].get("final_score")
    cycle_id = rev.data[0].get("cycle_id")

    calib = db.table("performance_calibrations").insert({
        "cycle_id": cycle_id,
        "review_id": body.review_id,
        "original_score": original_score,
        "calibrated_score": body.calibrated_score,
        "justification": body.justification,
        "calibrated_by": current_user["username"],
    }).execute()

    if not calib.data:
        raise HTTPException(status_code=500, detail="Erro ao registrar calibração")

    db.table("performance_reviews").update({
        "final_score": body.calibrated_score,
        "updated_at": "now()",
    }).eq("id", body.review_id).execute()

    log_action(
        "review", body.review_id, "calibrate",
        {"final_score": original_score},
        {"final_score": body.calibrated_score, "calibrated_by": current_user["username"]},
        current_user["username"], request,
    )
    return calib.data[0]

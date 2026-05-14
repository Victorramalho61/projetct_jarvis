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


@router.get("/employees")
def list_employees(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    active: bool = True,
    department_id: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_employees").select("*, performance_departments(name)").eq("active", active)
    if department_id:
        query = query.eq("department_id", department_id)
    return query.order("name").execute().data


@router.post("/sync-benner")
def sync_benner(
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    from services.benner_sync import sync_benner as _sync
    result = _sync()
    log_action("system", "benner_sync", "sync", None, result, current_user["username"], request)
    return result


@router.get("/dashboard")
def dashboard(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str | None = None,
) -> dict:
    db = get_supabase()
    query = db.table("performance_reviews").select("status, final_score, blocked_by")
    if cycle_id:
        query = query.eq("cycle_id", cycle_id)
    reviews = query.execute().data

    total = len(reviews)
    by_status: dict[str, int] = {}
    score_distribution: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    blocked_count = 0

    for r in reviews:
        s = r.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        if r.get("final_score") is not None:
            bucket = str(min(5, max(1, round(r["final_score"]))))
            score_distribution[bucket] = score_distribution.get(bucket, 0) + 1
        if r.get("blocked_by"):
            blocked_count += 1

    completed = by_status.get("completed", 0)
    completude_pct = round((completed / total * 100), 1) if total else 0

    pending_ack = db.table("performance_reviews").select("id,employee_id").eq("status", "pending_ack").execute().data
    pending_goals = db.table("performance_goals").select("id,owner_id,title").eq("status", "draft").execute().data

    return {
        "total_reviews": total,
        "by_status": by_status,
        "score_distribution": score_distribution,
        "blocked_by_compliance": blocked_count,
        "completude_pct": completude_pct,
        "pending_acknowledgments": len(pending_ack),
        "pending_goal_acknowledgments": len(pending_goals),
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


@router.get("/pending-acknowledgments")
def pending_acknowledgments(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    reviews = db.table("performance_reviews").select("id,employee_id,cycle_id,status").eq("status", "pending_ack").execute().data
    goals = db.table("performance_goals").select("id,owner_id,title,status").eq("status", "draft").execute().data
    return {
        "pending_review_acknowledgments": reviews,
        "pending_goal_acknowledgments": goals,
    }


@router.post("/calibrations", status_code=status.HTTP_201_CREATED)
def create_calibration(
    body: CalibrationCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    rev = db.table("performance_reviews").select("final_score").eq("id", body.review_id).execute()
    if not rev.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    original_score = rev.data[0].get("final_score")
    cycle_result = db.table("performance_reviews").select("cycle_id").eq("id", body.review_id).execute()
    cycle_id = cycle_result.data[0]["cycle_id"] if cycle_result.data else None

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

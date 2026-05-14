import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import get_current_user, require_role
from db import get_supabase
from services.audit import log_action
from services.notification_worker import notify
from services.score_engine import calculate_scores

router = APIRouter(prefix="/api/performance/evaluations")
_logger = logging.getLogger(__name__)

_PERF_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor", "colaborador")
_MANAGER_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor")
_RH_ADMIN = ("admin", "rh")


class CycleCreate(BaseModel):
    name: str
    period_start: date
    period_end: date


class ReviewUpdate(BaseModel):
    goals_score: float | None = None
    competencies_score: float | None = None
    behavior_score: float | None = None
    compliance_score: float | None = None
    comments: str | None = None


class SignRequest(BaseModel):
    signature_text: str | None = None


class AcknowledgeRequest(BaseModel):
    action: str  # acknowledged | disputed
    comments: str | None = None


# ── Cycles ───────────────────────────────────────────────────────────────────

@router.get("/cycles")
def list_cycles(
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> list[dict]:
    db = get_supabase()
    return db.table("performance_cycles").select("*").order("created_at", desc=True).execute().data


@router.post("/cycles", status_code=status.HTTP_201_CREATED)
def create_cycle(
    body: CycleCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    payload = {
        "name": body.name,
        "period_start": body.period_start.isoformat(),
        "period_end": body.period_end.isoformat(),
        "status": "draft",
        "created_by": current_user["username"],
    }
    result = db.table("performance_cycles").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar ciclo")
    cycle = result.data[0]
    log_action("cycle", cycle["id"], "create", None, cycle, current_user["username"], request)
    return cycle


@router.post("/cycles/{cycle_id}/open")
def open_cycle(
    cycle_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    """Abre o ciclo e cria reviews pending_self para todos os employees ativos."""
    db = get_supabase()
    cycle = db.table("performance_cycles").select("*").eq("id", cycle_id).execute()
    if not cycle.data:
        raise HTTPException(status_code=404, detail="Ciclo não encontrado")
    if cycle.data[0]["status"] != "draft":
        raise HTTPException(status_code=400, detail="Ciclo já foi aberto")

    employees = db.table("performance_employees").select("id,manager_id").eq("active", True).execute()
    reviews = []
    for emp in employees.data:
        reviews.append({
            "cycle_id": cycle_id,
            "employee_id": emp["id"],
            "reviewer_id": emp.get("manager_id"),
            "step": "self",
            "status": "pending_self",
        })

    if reviews:
        db.table("performance_reviews").insert(reviews).execute()

    db.table("performance_cycles").update({"status": "open"}).eq("id", cycle_id).execute()
    log_action("cycle", cycle_id, "open", {"status": "draft"}, {"status": "open"}, current_user["username"], request)
    return {"ok": True, "reviews_created": len(reviews)}


# ── Reviews ───────────────────────────────────────────────────────────────────

@router.get("/reviews")
def list_reviews(
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
    cycle_id: str | None = None,
    employee_id: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_reviews").select("*")

    role = current_user.get("role")
    if role == "colaborador":
        emp = db.table("performance_employees").select("id").eq("email", current_user.get("email", "")).execute()
        if emp.data:
            query = query.eq("employee_id", emp.data[0]["id"])
        else:
            return []
    elif employee_id:
        query = query.eq("employee_id", employee_id)

    if cycle_id:
        query = query.eq("cycle_id", cycle_id)

    return query.order("created_at", desc=True).execute().data


@router.get("/reviews/{review_id}")
def get_review(
    review_id: str,
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    db = get_supabase()
    result = db.table("performance_reviews").select("*").eq("id", review_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return result.data[0]


@router.put("/reviews/{review_id}")
def update_review(
    review_id: str,
    body: ReviewUpdate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    db = get_supabase()
    existing = db.table("performance_reviews").select("*").eq("id", review_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    old = existing.data[0]
    updates = body.model_dump(exclude_none=True)

    # Recalcular scores se houver notas
    goals = updates.get("goals_score", old.get("goals_score"))
    comps = updates.get("competencies_score", old.get("competencies_score"))
    behav = updates.get("behavior_score", old.get("behavior_score"))
    comp_score = updates.get("compliance_score", old.get("compliance_score"))

    if any(v is not None for v in [goals, comps, behav, comp_score]):
        scores = calculate_scores(goals, comps, behav, comp_score)
        updates.update(scores)

    updates["updated_at"] = "now()"

    # Versionar antes de atualizar
    _save_version(db, review_id, old, current_user["username"])

    result = db.table("performance_reviews").update(updates).eq("id", review_id).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao atualizar avaliação")

    new = result.data[0]
    log_action("review", review_id, "update", old, new, current_user["username"], request)
    return new


@router.post("/reviews/{review_id}/submit")
def submit_review(
    review_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    """Avança o step da avaliação e notifica o próximo responsável."""
    db = get_supabase()
    rev = db.table("performance_reviews").select("*").eq("id", review_id).execute()
    if not rev.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    review = rev.data[0]
    old_status = review["status"]

    next_status = {
        "pending_self": "pending_manager",
        "pending_manager": "pending_hr",
    }.get(old_status)

    if not next_status:
        raise HTTPException(status_code=400, detail=f"Não é possível submeter avaliação com status '{old_status}'")

    updates = {
        "status": next_status,
        "submitted_at": "now()",
        "updated_at": "now()",
    }
    if old_status == "pending_self":
        updates["step"] = "manager"

    _save_version(db, review_id, review, current_user["username"])
    result = db.table("performance_reviews").update(updates).eq("id", review_id).execute()
    log_action("review", review_id, "submit", {"status": old_status}, {"status": next_status}, current_user["username"], request)

    # Notificar gestor quando autoavaliação submetida
    if next_status == "pending_manager" and review.get("reviewer_id"):
        reviewer = db.table("performance_employees").select("email").eq("id", review["reviewer_id"]).execute()
        if reviewer.data and reviewer.data[0].get("email"):
            prof = db.table("profiles").select("username").eq("email", reviewer.data[0]["email"]).execute()
            if prof.data:
                notify("review_pending", prof.data[0]["username"])

    return result.data[0]


@router.post("/reviews/{review_id}/sign")
def sign_review(
    review_id: str,
    body: SignRequest,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> dict:
    """Gestor assina o resultado — Momento 2."""
    db = get_supabase()
    rev = db.table("performance_reviews").select("*").eq("id", review_id).execute()
    if not rev.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    review = rev.data[0]
    if review["status"] not in ("pending_manager", "pending_hr"):
        raise HTTPException(status_code=400, detail="Avaliação não está em estado de assinatura")

    _save_version(db, review_id, review, current_user["username"])
    updates = {
        "status": "pending_ack",
        "manager_signed_at": "now()",
        "manager_signature": body.signature_text or current_user["username"],
        "updated_at": "now()",
    }
    result = db.table("performance_reviews").update(updates).eq("id", review_id).execute()
    log_action("review", review_id, "sign", {"status": review["status"]}, {"status": "pending_ack"}, current_user["username"], request)

    # Notificar colaborador
    employee = db.table("performance_employees").select("email").eq("id", review["employee_id"]).execute()
    if employee.data and employee.data[0].get("email"):
        prof = db.table("profiles").select("username").eq("email", employee.data[0]["email"]).execute()
        if prof.data:
            notify("review_result_available", prof.data[0]["username"])

    return result.data[0]


@router.post("/reviews/{review_id}/acknowledge")
def acknowledge_review(
    review_id: str,
    body: AcknowledgeRequest,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    """Colaborador toma ciência ou contesta — Momento 2."""
    if body.action not in ("acknowledged", "disputed"):
        raise HTTPException(status_code=400, detail="action deve ser 'acknowledged' ou 'disputed'")
    if body.action == "disputed" and not body.comments:
        raise HTTPException(status_code=400, detail="Comentário obrigatório ao contestar")

    db = get_supabase()
    rev = db.table("performance_reviews").select("*").eq("id", review_id).execute()
    if not rev.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    review = rev.data[0]
    if review["status"] != "pending_ack":
        raise HTTPException(status_code=400, detail="Avaliação não está aguardando ciência")

    emp = db.table("performance_employees").select("id").eq("email", current_user.get("email", "")).execute()
    if not emp.data:
        raise HTTPException(status_code=400, detail="Funcionário não encontrado para este usuário")
    employee_id = emp.data[0]["id"]

    existing = db.table("performance_review_acknowledgments").select("id").eq("review_id", review_id).eq("employee_id", employee_id).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Avaliação já respondida por este colaborador")

    db.table("performance_review_acknowledgments").insert({
        "review_id": review_id,
        "employee_id": employee_id,
        "action": body.action,
        "comments": body.comments,
    }).execute()

    new_status = "disputed" if body.action == "disputed" else "completed"
    _save_version(db, review_id, review, current_user["username"])
    db.table("performance_reviews").update({"status": new_status, "updated_at": "now()"}).eq("id", review_id).execute()
    log_action("review", review_id, f"acknowledge_{body.action}", {"status": "pending_ack"}, {"status": new_status}, current_user["username"], request)

    # Notificar RH se contestado
    if body.action == "disputed":
        rh_profiles = db.table("profiles").select("username").eq("role", "rh").execute()
        for p in (rh_profiles.data or []):
            notify("review_disputed", p["username"], {"review_id": review_id})

    return {"ok": True, "review_id": review_id, "status": new_status}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_version(db, review_id: str, snapshot: dict, changed_by: str) -> None:
    existing_versions = db.table("performance_review_versions").select("version").eq("review_id", review_id).order("version", desc=True).limit(1).execute()
    next_version = (existing_versions.data[0]["version"] + 1) if existing_versions.data else 1
    db.table("performance_review_versions").insert({
        "review_id": review_id,
        "version": next_version,
        "snapshot": snapshot,
        "changed_by": changed_by,
    }).execute()

import logging
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import get_current_user, require_role
from db import get_supabase
from services.audit import log_action
from services.notification_worker import notify

router = APIRouter(prefix="/api/performance/goals")
_logger = logging.getLogger(__name__)

_PERF_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor", "colaborador")
_MANAGER_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor")


class GoalCreate(BaseModel):
    title: str
    type: str
    description: str | None = None
    kpi_name: str | None = None
    formula: str | None = None
    target_value: float | None = None
    unit: str | None = None
    weight: float = 1.0
    period_start: date
    period_end: date
    owner_id: str | None = None
    department_id: str | None = None
    parent_goal_id: str | None = None


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    kpi_name: str | None = None
    formula: str | None = None
    target_value: float | None = None
    unit: str | None = None
    weight: float | None = None
    period_start: date | None = None
    period_end: date | None = None
    status: str | None = None


class ProgressUpdate(BaseModel):
    current_value: float


class AcknowledgeRequest(BaseModel):
    signature_text: str | None = None


@router.get("")
def list_goals(
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
    cycle_id: str | None = None,
    owner_id: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_goals").select("*")

    role = current_user.get("role")
    if role == "colaborador":
        # Busca employee pelo email do usuário
        emp = db.table("performance_employees").select("id").eq("email", current_user.get("email", "")).execute()
        if emp.data:
            query = query.eq("owner_id", emp.data[0]["id"])
        else:
            return []
    elif owner_id:
        query = query.eq("owner_id", owner_id)

    if cycle_id:
        query = query.eq("cycle_id", cycle_id)

    result = query.order("created_at", desc=True).execute()
    return result.data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_goal(
    body: GoalCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> dict:
    db = get_supabase()
    payload = body.model_dump(exclude_none=True)
    payload["created_by"] = current_user["username"]
    payload["status"] = "draft"

    # Convert dates to strings for Supabase
    if isinstance(payload.get("period_start"), date):
        payload["period_start"] = payload["period_start"].isoformat()
    if isinstance(payload.get("period_end"), date):
        payload["period_end"] = payload["period_end"].isoformat()

    result = db.table("performance_goals").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar meta")

    goal = result.data[0]
    log_action("goal", goal["id"], "create", None, goal, current_user["username"], request)

    # Notificar owner se definido
    if body.owner_id:
        emp = db.table("performance_employees").select("email").eq("id", body.owner_id).execute()
        if emp.data and emp.data[0].get("email"):
            owner_email = emp.data[0]["email"]
            prof = db.table("profiles").select("username").eq("email", owner_email).execute()
            if prof.data:
                notify("goal_proposed", prof.data[0]["username"], {"meta": body.title})

    return goal


@router.put("/{goal_id}")
def update_goal(
    goal_id: str,
    body: GoalUpdate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> dict:
    db = get_supabase()
    existing = db.table("performance_goals").select("*").eq("id", goal_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Meta não encontrada")

    old = existing.data[0]
    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        if isinstance(v, date):
            updates[k] = v.isoformat()
    updates["updated_at"] = "now()"

    result = db.table("performance_goals").update(updates).eq("id", goal_id).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao atualizar meta")

    new = result.data[0]
    log_action("goal", goal_id, "update", old, new, current_user["username"], request)
    return new


@router.patch("/{goal_id}/progress")
def update_progress(
    goal_id: str,
    body: ProgressUpdate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    db = get_supabase()
    result = db.table("performance_goals").update({
        "current_value": body.current_value,
        "updated_at": "now()",
    }).eq("id", goal_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    log_action("goal", goal_id, "progress_update", None, {"current_value": body.current_value}, current_user["username"], request)
    return result.data[0]


@router.get("/templates")
def list_templates(
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> list[dict]:
    db = get_supabase()
    result = db.table("performance_goal_templates").select("*").order("title").execute()
    return result.data


@router.post("/from-template/{template_id}", status_code=status.HTTP_201_CREATED)
def create_from_template(
    template_id: str,
    body: dict,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> dict:
    db = get_supabase()
    tmpl = db.table("performance_goal_templates").select("*").eq("id", template_id).execute()
    if not tmpl.data:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    t = tmpl.data[0]

    payload = {
        "title": body.get("title", t["title"]),
        "type": t["type"],
        "kpi_name": t.get("kpi_name"),
        "formula": t.get("formula"),
        "target_value": body.get("target_value", t.get("default_target")),
        "unit": t.get("unit"),
        "weight": body.get("weight", t.get("weight_suggestion", 1.0)),
        "description": t.get("description"),
        "period_start": body.get("period_start"),
        "period_end": body.get("period_end"),
        "owner_id": body.get("owner_id"),
        "department_id": body.get("department_id"),
        "status": "draft",
        "created_by": current_user["username"],
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    result = db.table("performance_goals").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar meta")
    goal = result.data[0]
    log_action("goal", goal["id"], "create_from_template", None, goal, current_user["username"], request)
    return goal


@router.post("/{goal_id}/acknowledge", status_code=status.HTTP_200_OK)
def acknowledge_goal(
    goal_id: str,
    body: AcknowledgeRequest,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    db = get_supabase()
    goal = db.table("performance_goals").select("*").eq("id", goal_id).execute()
    if not goal.data:
        raise HTTPException(status_code=404, detail="Meta não encontrada")

    # Localizar employee pelo email do usuário autenticado
    emp = db.table("performance_employees").select("id").eq("email", current_user.get("email", "")).execute()
    if not emp.data:
        raise HTTPException(status_code=400, detail="Funcionário não encontrado para este usuário")
    employee_id = emp.data[0]["id"]

    # Verificar se já assinou
    existing = db.table("performance_goal_acknowledgments").select("id").eq("goal_id", goal_id).eq("employee_id", employee_id).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Meta já assinada por este colaborador")

    db.table("performance_goal_acknowledgments").insert({
        "goal_id": goal_id,
        "employee_id": employee_id,
        "ip_address": request.client.host if request.client else None,
        "signature_text": body.signature_text,
    }).execute()

    db.table("performance_goals").update({"status": "active", "updated_at": "now()"}).eq("id", goal_id).execute()
    log_action("goal", goal_id, "acknowledge", {"status": "draft"}, {"status": "active"}, current_user["username"], request)

    return {"ok": True, "goal_id": goal_id, "status": "active"}

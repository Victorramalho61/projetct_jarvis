import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import require_role
from db import get_supabase
from services.audit import log_action

router = APIRouter(prefix="/api/performance/evidences")
_logger = logging.getLogger(__name__)

_PERF_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor", "colaborador")


class EvidenceCreate(BaseModel):
    goal_id: str | None = None
    type: str
    source: str | None = None
    value: float | None = None
    unit: str | None = None
    description: str | None = None
    evidence_date: date


@router.get("")
def list_evidences(
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
    goal_id: str | None = None,
    employee_id: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_evidences").select("*")
    if goal_id:
        query = query.eq("goal_id", goal_id)
    if employee_id:
        query = query.eq("employee_id", employee_id)
    return query.order("evidence_date", desc=True).execute().data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_evidence(
    body: EvidenceCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    db = get_supabase()

    emp = db.table("performance_employees").select("id").eq("email", current_user.get("email", "")).execute()
    if not emp.data:
        raise HTTPException(status_code=400, detail="Funcionário não encontrado para este usuário")
    employee_id = emp.data[0]["id"]

    payload = body.model_dump(exclude_none=True)
    payload["employee_id"] = employee_id
    payload["created_by"] = current_user["username"]
    if isinstance(payload.get("evidence_date"), date):
        payload["evidence_date"] = payload["evidence_date"].isoformat()

    result = db.table("performance_evidences").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao registrar evidência")

    evidence = result.data[0]
    log_action("evidence", evidence["id"], "create", None, evidence, current_user["username"], request)
    return evidence

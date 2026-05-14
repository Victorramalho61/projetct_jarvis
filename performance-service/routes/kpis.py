import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import require_role
from db import get_supabase
from services.audit import log_action

router = APIRouter(prefix="/api/performance/kpis")
_logger = logging.getLogger(__name__)

_PERF_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor", "colaborador")
_MANAGER_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor")


class KpiCreate(BaseModel):
    name: str
    department_type: str | None = None
    formula: str | None = None
    source: str | None = None
    unit: str | None = None


class KpiSnapshotCreate(BaseModel):
    employee_id: str | None = None
    value: float
    period: str


@router.get("")
def list_kpis(
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
    department_type: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_kpis").select("*").order("name")
    if department_type:
        query = query.eq("department_type", department_type)
    return query.execute().data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_kpi(
    body: KpiCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> dict:
    db = get_supabase()
    payload = body.model_dump(exclude_none=True)
    result = db.table("performance_kpis").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar KPI")
    kpi = result.data[0]
    log_action("kpi", kpi["id"], "create", None, kpi, current_user["username"], request)
    return kpi


@router.post("/{kpi_id}/snapshots", status_code=status.HTTP_201_CREATED)
def create_snapshot(
    kpi_id: str,
    body: KpiSnapshotCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> dict:
    db = get_supabase()
    kpi = db.table("performance_kpis").select("id").eq("id", kpi_id).execute()
    if not kpi.data:
        raise HTTPException(status_code=404, detail="KPI não encontrado")

    payload = {
        "kpi_id": kpi_id,
        "value": body.value,
        "period": body.period,
    }
    if body.employee_id:
        payload["employee_id"] = body.employee_id

    result = db.table("performance_kpi_snapshots").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao registrar snapshot")
    snap = result.data[0]
    log_action("kpi", kpi_id, "snapshot", None, snap, current_user["username"], request)
    return snap


@router.get("/{kpi_id}/snapshots")
def list_snapshots(
    kpi_id: str,
    _: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
    employee_id: str | None = None,
    period: str | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_kpi_snapshots").select("*").eq("kpi_id", kpi_id)
    if employee_id:
        query = query.eq("employee_id", employee_id)
    if period:
        query = query.eq("period", period)
    return query.order("captured_at", desc=True).execute().data

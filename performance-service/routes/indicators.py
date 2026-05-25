import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from auth import require_role
from db import get_supabase
from services.audit import log_action

router = APIRouter(prefix="/api/performance/indicators")
_logger = logging.getLogger(__name__)
_RH_ADMIN = ("admin", "rh")

class IndicatorCreate(BaseModel):
    name: str
    description: str | None = None
    hierarchy_level: int | None = None  # 1=Gerente, 2=Coord/Sup, 3=Operacional/Admin; None=todos

class IndicatorUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None
    hierarchy_level: int | None = None

@router.get("/")
def list_indicators(
    _: Annotated[dict, Depends(require_role("admin", "rh", "gerente", "coordenador_supervisor"))],
    active_only: bool = True,
    hierarchy_level: int | None = None,
) -> list[dict]:
    db = get_supabase()
    query = db.table("performance_indicators").select("*")
    if active_only:
        query = query.eq("active", True)
    if hierarchy_level is not None:
        query = query.eq("hierarchy_level", hierarchy_level)
    return query.order("hierarchy_level").order("created_at").execute().data

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_indicator(
    body: IndicatorCreate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    if not body.name.strip():
        raise HTTPException(400, detail="Nome do indicador não pode ser vazio")
    db = get_supabase()
    result = db.table("performance_indicators").insert({
        "name": body.name.strip(),
        "description": body.description,
        "hierarchy_level": body.hierarchy_level,
        "active": True,
        "created_by": current_user["username"],
    }).execute()
    if not result.data:
        raise HTTPException(500, detail="Erro ao criar indicador")
    indicator = result.data[0]
    log_action("indicator", indicator["id"], "create", None, indicator, current_user["username"], request)
    return indicator

@router.put("/{indicator_id}")
def update_indicator(
    indicator_id: str,
    body: IndicatorUpdate,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    existing = db.table("performance_indicators").select("*").eq("id", indicator_id).execute()
    if not existing.data:
        raise HTTPException(404, detail="Indicador não encontrado")
    old = existing.data[0]
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, detail="Nenhum campo para atualizar")
    if "name" in updates and not updates["name"].strip():
        raise HTTPException(400, detail="Nome não pode ser vazio")
    updates["updated_at"] = "now()"
    result = db.table("performance_indicators").update(updates).eq("id", indicator_id).execute()
    new = result.data[0]
    log_action("indicator", indicator_id, "update", old, new, current_user["username"], request)
    return new

@router.delete("/{indicator_id}")
def deactivate_indicator(
    indicator_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    existing = db.table("performance_indicators").select("*").eq("id", indicator_id).execute()
    if not existing.data:
        raise HTTPException(404, detail="Indicador não encontrado")
    result = db.table("performance_indicators").update({"active": False, "updated_at": "now()"}).eq("id", indicator_id).execute()
    log_action("indicator", indicator_id, "deactivate", existing.data[0], result.data[0], current_user["username"], request)
    return result.data[0]

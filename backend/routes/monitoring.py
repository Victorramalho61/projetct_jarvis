import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from auth import get_current_user, require_role
from db import get_settings, get_supabase
from limiter import limiter
from services.app_logger import log_event
from services.monitor import run_check

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
logger = logging.getLogger(__name__)


class SystemIn(BaseModel):
    name: str
    description: str = ""
    url: str = ""
    system_type: Literal["http", "evolution", "metrics", "tcp", "custom"]
    config: dict = {}
    check_interval_minutes: int = 5
    enabled: bool = True


class SystemPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    system_type: Literal["http", "evolution", "metrics", "tcp", "custom"] | None = None
    config: dict | None = None
    check_interval_minutes: int | None = None
    enabled: bool | None = None


def _uptime_24h(system_id: str, db) -> float | None:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    checks = db.table("system_checks") \
        .select("status") \
        .eq("system_id", system_id) \
        .gte("checked_at", since) \
        .execute().data
    if not checks:
        return None
    up = sum(1 for c in checks if c["status"] == "up")
    return round(up / len(checks) * 100, 1)


def _last_check(system_id: str, db) -> dict | None:
    rows = db.table("system_checks") \
        .select("*") \
        .eq("system_id", system_id) \
        .order("checked_at", desc=True) \
        .limit(1) \
        .execute().data
    return rows[0] if rows else None


def _enrich(system: dict, db) -> dict:
    system["last_check"] = _last_check(system["id"], db)
    system["uptime_24h"] = _uptime_24h(system["id"], db)
    return system


def _bulk_enrich(systems: list[dict], db) -> list[dict]:
    if not systems:
        return systems
    ids = [s["id"] for s in systems]
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    recent = (
        db.table("system_checks").select("*")
        .in_("system_id", ids)
        .order("checked_at", desc=True)
        .limit(max(50, len(ids) * 5))
        .execute().data
    )
    hourly = (
        db.table("system_checks").select("system_id,status")
        .in_("system_id", ids)
        .gte("checked_at", since_24h)
        .limit(len(ids) * 300)
        .execute().data
    )

    last_check_map: dict[str, dict] = {}
    for r in recent:
        last_check_map.setdefault(r["system_id"], r)

    uptime_data: dict[str, list[str]] = {}
    for r in hourly:
        uptime_data.setdefault(r["system_id"], []).append(r["status"])

    for s in systems:
        sid = s["id"]
        s["last_check"] = last_check_map.get(sid)
        statuses = uptime_data.get(sid)
        s["uptime_24h"] = round(sum(1 for st in statuses if st == "up") / len(statuses) * 100, 1) if statuses else None
    return systems


@router.post("/systems", status_code=201)
def create_system(
    body: SystemIn,
    current_user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    row = db.table("monitored_systems").insert({
        "name": body.name,
        "description": body.description,
        "url": body.url,
        "system_type": body.system_type,
        "config": body.config,
        "check_interval_minutes": body.check_interval_minutes,
        "enabled": body.enabled,
        "created_by": current_user.get("id"),
    }).execute().data[0]
    log_event("info", "monitoring", f"Sistema cadastrado: {body.name}")
    return _enrich(row, db)


@router.get("/systems")
def list_systems(
    enabled: bool | None = Query(None),
    current_user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    q = db.table("monitored_systems").select("*").order("created_at")
    if enabled is not None:
        q = q.eq("enabled", enabled)
    systems = q.execute().data
    return _bulk_enrich(systems, db)


@router.get("/systems/{system_id}")
def get_system(
    system_id: str,
    current_user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    rows = db.table("monitored_systems").select("*").eq("id", system_id).execute().data
    if not rows:
        raise HTTPException(404, "Sistema não encontrado")
    return _enrich(rows[0], db)


@router.patch("/systems/{system_id}")
def update_system(
    system_id: str,
    body: SystemPatch,
    current_user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nenhum campo para atualizar")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    row = db.table("monitored_systems").update(updates).eq("id", system_id).execute().data
    if not row:
        raise HTTPException(404, "Sistema não encontrado")
    log_event("info", "monitoring", f"Sistema atualizado: {system_id}")
    return _enrich(row[0], db)


@router.delete("/systems/{system_id}")
def delete_system(
    system_id: str,
    current_user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    rows = db.table("monitored_systems").select("name").eq("id", system_id).execute().data
    if not rows:
        raise HTTPException(404, "Sistema não encontrado")
    db.table("monitored_systems").delete().eq("id", system_id).execute()
    log_event("warning", "monitoring", f"Sistema removido: {rows[0]['name']}")
    return {"ok": True}


@router.get("/dashboard")
def get_dashboard(current_user: dict = Depends(require_role("admin"))):
    db = get_supabase()
    systems = db.table("monitored_systems").select("*").order("created_at").execute().data
    enriched = _bulk_enrich(systems, db)

    summary = {"up": 0, "down": 0, "degraded": 0, "unknown": 0}
    for s in enriched:
        lc = s.get("last_check")
        status = lc["status"] if lc else "unknown"
        summary[status] = summary.get(status, 0) + 1

    return {"systems": enriched, "summary": summary}


@router.get("/systems/{system_id}/checks")
def get_checks(
    system_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    status: str | None = Query(None),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
    current_user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    q = db.table("system_checks") \
        .select("*", count="exact") \
        .eq("system_id", system_id) \
        .order("checked_at", desc=True) \
        .limit(limit) \
        .offset(offset)
    if status:
        q = q.eq("status", status)
    if from_dt:
        q = q.gte("checked_at", from_dt)
    if to_dt:
        q = q.lte("checked_at", to_dt)
    result = q.execute()
    return {"data": result.data, "total": result.count, "limit": limit, "offset": offset}


@router.post("/systems/{system_id}/check")
async def manual_check(
    system_id: str,
    current_user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    rows = db.table("monitored_systems").select("*").eq("id", system_id).execute().data
    if not rows:
        raise HTTPException(404, "Sistema não encontrado")
    result = await run_check(rows[0], checked_by="manual")
    return result


@router.post("/agent/push")
@limiter.limit("60/minute")
async def agent_push(request: Request, body: dict):
    s = get_settings()
    allowed = [t.strip() for t in s.monitor_agent_tokens.split(",") if t.strip()]
    token = body.get("agent_token", "")
    if not allowed or token not in allowed:
        raise HTTPException(401, "Token inválido")

    system_id = body.get("system_id")
    status = body.get("status", "unknown")
    if not system_id:
        raise HTTPException(400, "system_id obrigatório")

    db = get_supabase()
    db.table("system_checks").insert({
        "system_id":  system_id,
        "status":     status,
        "latency_ms": body.get("latency_ms"),
        "detail":     body.get("detail"),
        "metrics":    body.get("metrics"),
        "checked_by": "agent",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    if status == "down":
        rows = db.table("monitored_systems").select("name").eq("id", system_id).execute().data
        name = rows[0]["name"] if rows else system_id
        log_event("error", "monitoring", f"Sistema DOWN (agente): {name}",
                  detail=body.get("detail"))

    return {"ok": True, "received_at": datetime.now(timezone.utc).isoformat()}

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from auth import get_current_user, require_role
from db import get_supabase
from services.freshservice import get_live_metrics, run_backfill, run_daily_sync

router = APIRouter(prefix="/freshservice", tags=["freshservice"])
logger = logging.getLogger(__name__)

_BRT = timezone(timedelta(hours=-3))


def _default_period() -> tuple[str, str]:
    today = datetime.now(_BRT).replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = today - timedelta(days=30)
    return (
        thirty_days_ago.astimezone(timezone.utc).isoformat(),
        today.astimezone(timezone.utc).isoformat(),
    )


@router.get("/dashboard/summary")
async def dashboard_summary(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(get_current_user),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    db = get_supabase()
    result = db.rpc("freshservice_summary", {"p_from": p_from, "p_to": p_to}).execute()
    return result.data or {}


@router.get("/dashboard/sla-by-group")
async def dashboard_sla_by_group(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(get_current_user),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    db = get_supabase()
    result = db.rpc("freshservice_sla_by_group", {"p_from": p_from, "p_to": p_to}).execute()
    return result.data or []


@router.get("/dashboard/agents")
async def dashboard_agents(
    month: str | None = Query(None, description="YYYY-MM"),
    _: dict = Depends(get_current_user),
):
    now_brt = datetime.now(_BRT)
    if month:
        try:
            dt = datetime.strptime(month, "%Y-%m")
            year, m = dt.year, dt.month
        except ValueError:
            raise HTTPException(status_code=422, detail="month deve ser YYYY-MM")
    else:
        year, m = now_brt.year, now_brt.month

    db = get_supabase()
    result = db.rpc("freshservice_agents_monthly", {"p_year": year, "p_month": m}).execute()
    return result.data or []


@router.get("/dashboard/top-requesters")
async def dashboard_top_requesters(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int = Query(5, ge=1, le=20),
    _: dict = Depends(get_current_user),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    db = get_supabase()
    result = db.rpc("freshservice_top_requesters", {
        "p_from":  p_from,
        "p_to":    p_to,
        "p_limit": limit,
    }).execute()
    return result.data or []


@router.get("/dashboard/csat")
async def dashboard_csat(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(get_current_user),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    db = get_supabase()
    result = db.rpc("freshservice_csat_summary", {"p_from": p_from, "p_to": p_to}).execute()
    return result.data or {}


@router.get("/dashboard/live")
async def dashboard_live(_: dict = Depends(get_current_user)):
    return await get_live_metrics()


@router.get("/tickets")
async def list_tickets(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    group_id: int | None = None,
    responder_id: int | None = None,
    company_id: int | None = None,
    priority: int | None = None,
    sla_breached: bool | None = None,
    csat_rating: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: dict = Depends(get_current_user),
):
    db = get_supabase()

    cols = (
        "id, subject, status, priority, type, group_id, responder_id, "
        "requester_id, company_id, created_at, updated_at, resolved_at, closed_at, "
        "sla_breached, resolution_time_min, fr_time_min, csat_rating, csat_comment"
    )

    query = (
        db.table("freshservice_tickets")
        .select(cols, count="exact")
        .in_("status", [4, 5])
    )

    if from_date:
        query = query.gte("updated_at", from_date)
    if to_date:
        query = query.lt("updated_at", to_date)
    if group_id is not None:
        query = query.eq("group_id", group_id)
    if responder_id is not None:
        query = query.eq("responder_id", responder_id)
    if company_id is not None:
        query = query.eq("company_id", company_id)
    if priority is not None:
        query = query.eq("priority", priority)
    if sla_breached is not None:
        query = query.eq("sla_breached", sla_breached)
    if csat_rating is not None:
        query = query.eq("csat_rating", csat_rating)

    offset = (page - 1) * page_size
    result = (
        query
        .order("updated_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )

    # Enrich with agent/group/company names
    rows = result.data or []
    if rows:
        rows = _enrich_ticket_names(db, rows)

    return {
        "data":      rows,
        "total":     result.count or 0,
        "page":      page,
        "page_size": page_size,
    }


def _enrich_ticket_names(db, rows: list[dict]) -> list[dict]:
    agent_ids = {r["responder_id"] for r in rows if r.get("responder_id")}
    group_ids  = {r["group_id"]    for r in rows if r.get("group_id")}
    company_ids = {r["company_id"] for r in rows if r.get("company_id")}

    agents:    dict[int, str] = {}
    groups:    dict[int, str] = {}
    companies: dict[int, str] = {}

    if agent_ids:
        for row in db.table("freshservice_agents").select("id,name").in_("id", list(agent_ids)).execute().data or []:
            agents[row["id"]] = row["name"]
    if group_ids:
        for row in db.table("freshservice_groups").select("id,name").in_("id", list(group_ids)).execute().data or []:
            groups[row["id"]] = row["name"]
    if company_ids:
        for row in db.table("freshservice_companies").select("id,name").in_("id", list(company_ids)).execute().data or []:
            companies[row["id"]] = row["name"]

    for r in rows:
        r["agent_name"]   = agents.get(r.get("responder_id"))
        r["group_name"]   = groups.get(r.get("group_id"))
        r["company_name"] = companies.get(r.get("company_id"))

    return rows


@router.get("/sync/status")
async def sync_status(_: dict = Depends(get_current_user)):
    db = get_supabase()
    result = (
        db.table("freshservice_sync_log")
        .select("*")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


@router.get("/agent/daily-summary")
async def agent_daily_summary(_: dict = Depends(get_current_user)):
    db = get_supabase()
    result = (
        db.table("freshservice_sync_log")
        .select("id, sync_type, started_at, completed_at, tickets_upserted, status, summary_json")
        .eq("sync_type", "daily")
        .not_.is_("summary_json", "null")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


@router.post("/sync/backfill")
async def trigger_backfill(
    background_tasks: BackgroundTasks,
    _: dict = Depends(require_role("admin")),
):
    background_tasks.add_task(run_backfill)
    return {"status": "started", "message": "Backfill iniciado em background"}


@router.post("/sync/daily")
async def trigger_daily_sync(
    background_tasks: BackgroundTasks,
    _: dict = Depends(require_role("admin")),
):
    background_tasks.add_task(run_daily_sync)
    return {"status": "started", "message": "Sync diário iniciado em background"}

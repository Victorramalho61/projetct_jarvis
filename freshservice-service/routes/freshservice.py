import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user, require_role
from db import get_supabase
from services.freshservice import get_live_metrics, run_backfill, run_daily_sync

router = APIRouter(prefix="/freshservice", tags=["freshservice"])
logger = logging.getLogger(__name__)

_BRT = timezone(timedelta(hours=-3))

# In-memory cache for dashboard RPC calls — same pattern as _live_cache in freshservice.py
# Keyed by "endpoint:param_hash", TTL of 5 minutes.
_dashboard_cache: dict[str, tuple[object, float]] = {}
_DASHBOARD_TTL = 300


def _cache_get(key: str) -> object | None:
    entry = _dashboard_cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _cache_set(key: str, data: object) -> None:
    _dashboard_cache[key] = (data, time.monotonic() + _DASHBOARD_TTL)


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
    _: dict = Depends(require_role("admin")),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    cache_key = f"summary:{p_from}:{p_to}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_supabase()
    data = db.rpc("freshservice_summary", {"p_from": p_from, "p_to": p_to}).execute().data or {}
    _cache_set(cache_key, data)
    return data


@router.get("/dashboard/sla-by-group")
async def dashboard_sla_by_group(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(require_role("admin")),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    cache_key = f"sla_by_group:{p_from}:{p_to}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_supabase()
    data = db.rpc("freshservice_sla_by_group", {"p_from": p_from, "p_to": p_to}).execute().data or []
    _cache_set(cache_key, data)
    return data


@router.get("/dashboard/agents")
async def dashboard_agents(
    month: str | None = Query(None, description="YYYY-MM"),
    _: dict = Depends(require_role("admin")),
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

    cache_key = f"agents:{year}:{m}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_supabase()
    data = db.rpc("freshservice_agents_monthly", {"p_year": year, "p_month": m}).execute().data or []
    _cache_set(cache_key, data)
    return data


@router.get("/dashboard/top-requesters")
async def dashboard_top_requesters(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int = Query(5, ge=1, le=20),
    _: dict = Depends(require_role("admin")),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    cache_key = f"top_requesters:{p_from}:{p_to}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_supabase()
    data = db.rpc("freshservice_top_requesters", {
        "p_from":  p_from,
        "p_to":    p_to,
        "p_limit": limit,
    }).execute().data or []
    _cache_set(cache_key, data)
    return data


@router.get("/dashboard/csat")
async def dashboard_csat(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(require_role("admin")),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    cache_key = f"csat:{p_from}:{p_to}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_supabase()
    data = db.rpc("freshservice_csat_summary", {"p_from": p_from, "p_to": p_to}).execute().data or {}
    _cache_set(cache_key, data)
    return data


@router.get("/dashboard/live")
async def dashboard_live(_: dict = Depends(require_role("admin"))):
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
    _: dict = Depends(require_role("admin")),
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
async def sync_status(_: dict = Depends(require_role("admin"))):
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
async def agent_daily_summary(_: dict = Depends(require_role("admin"))):
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
async def trigger_backfill(_: dict = Depends(require_role("admin"))):
    import time
    t0 = time.monotonic()
    count = await run_backfill()
    duration = round(time.monotonic() - t0)
    return {"status": "completed", "tickets_upserted": count, "duration_seconds": duration}


@router.post("/sync/daily")
async def trigger_daily_sync(_: dict = Depends(require_role("admin"))):
    import time
    t0 = time.monotonic()
    count = await run_daily_sync()
    duration = round(time.monotonic() - t0)
    return {"status": "completed", "tickets_upserted": count, "duration_seconds": duration}


# ── PayFly ────────────────────────────────────────────────────────────────────

def _get_payfly_group_id(db) -> int | None:
    """Descobre o group_id do grupo PayFly pela tabela freshservice_groups."""
    import os
    env_id = os.getenv("FRESHSERVICE_PAYFLY_GROUP_ID")
    if env_id:
        try:
            return int(env_id)
        except ValueError:
            pass
    rows = db.table("freshservice_groups").select("id,name").execute().data or []
    # Busca por qualquer variação: "payfly", "pay fly", "sistema payfly", etc.
    _payfly_terms = {"payfly", "pay fly", "payfly sistema", "sistema payfly"}
    for row in rows:
        name_lower = (row.get("name") or "").lower()
        if any(term in name_lower for term in _payfly_terms):
            return int(row["id"])
    # Fallback: qualquer grupo com "payfly" no nome (match parcial)
    for row in rows:
        if "payfly" in (row.get("name") or "").lower().replace(" ", ""):
            return int(row["id"])
    return None


@router.get("/payfly/groups")
async def payfly_list_groups(_: dict = Depends(require_role("admin"))):
    """Lista todos os grupos do Freshservice para identificar o grupo PayFly."""
    db = get_supabase()
    rows = db.table("freshservice_groups").select("id,name").order("name").execute().data or []
    return rows


@router.get("/payfly/dashboard")
async def payfly_dashboard(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(require_role("admin")),
):
    """Dashboard de chamados PayFly: contagens por status, SLA, tendência vs mês anterior."""
    db = get_supabase()
    group_id = _get_payfly_group_id(db)
    if group_id is None:
        return {
            "group_id": None, "group_name": None,
            "total": 0, "abertos": 0, "pendentes": 0, "resolvidos": 0,
            "fechados": 0, "aguardando_fornecedor": 0,
            "pct_abertos": 0, "pct_fechados": 0, "pct_aguardando": 0,
            "sla_compliance_pct": 0, "avg_resolution_time_hours": None,
            "by_priority": {}, "trend_total": 0, "trend_fechados": 0,
            "error": "Grupo PayFly não encontrado. Configure FRESHSERVICE_PAYFLY_GROUP_ID ou verifique o nome do grupo.",
        }

    group_row = db.table("freshservice_groups").select("name").eq("id", group_id).maybe_single().execute()
    group_name = group_row.data.get("name") if group_row.data else None

    cols = "id,status,priority,sla_breached,resolution_time_min,created_at,resolved_at,closed_at"

    def _tickets_in_range(q_from: str | None, q_to: str | None):
        q = db.table("freshservice_tickets").select(cols).eq("group_id", group_id)
        if q_from:
            q = q.gte("created_at", q_from)
        if q_to:
            q = q.lt("created_at", q_to)
        return q.execute().data or []

    if from_date or to_date:
        tickets = _tickets_in_range(from_date, to_date)
    else:
        # últimos 30 dias + todos em aberto
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        since_30d = (now - timedelta(days=30)).isoformat()
        # abertos/pendentes sem filtro de data para não perder tickets antigos
        open_tickets = (
            db.table("freshservice_tickets").select(cols)
            .eq("group_id", group_id)
            .in_("status", [2, 3, 6])
            .execute().data or []
        )
        closed_tickets = (
            db.table("freshservice_tickets").select(cols)
            .eq("group_id", group_id)
            .in_("status", [4, 5])
            .gte("updated_at", since_30d)
            .execute().data or []
        )
        seen = {t["id"] for t in open_tickets}
        tickets = open_tickets + [t for t in closed_tickets if t["id"] not in seen]

    total = len(tickets)
    abertos           = sum(1 for t in tickets if t["status"] == 2)
    pendentes         = sum(1 for t in tickets if t["status"] == 3)
    resolvidos        = sum(1 for t in tickets if t["status"] == 4)
    fechados          = sum(1 for t in tickets if t["status"] == 5)
    aguardando        = sum(1 for t in tickets if t["status"] == 6)

    sla_total     = sum(1 for t in tickets if t.get("sla_breached") is not None)
    sla_ok        = sum(1 for t in tickets if t.get("sla_breached") is False)
    sla_pct       = round(sla_ok / sla_total * 100, 1) if sla_total else 0.0

    res_times = [t["resolution_time_min"] for t in tickets if t.get("resolution_time_min")]
    avg_res_h = round(sum(res_times) / len(res_times) / 60, 1) if res_times else None

    by_priority: dict[str, int] = {}
    for t in tickets:
        p = str(t.get("priority") or "")
        by_priority[p] = by_priority.get(p, 0) + 1

    # Tendência vs mês anterior
    from datetime import datetime, timedelta, timezone as _tz
    now2 = datetime.now(_tz.utc)
    first_this  = now2.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_prev  = (first_this - timedelta(days=1)).replace(day=1)

    def _count_in(dt_from, dt_to):
        r = (
            db.table("freshservice_tickets").select("id,status", count="exact")
            .eq("group_id", group_id)
            .gte("created_at", dt_from.isoformat())
            .lt("created_at", dt_to.isoformat())
            .execute()
        )
        rows_m = r.data or []
        return len(rows_m), sum(1 for t in rows_m if t["status"] in (4, 5))

    cur_total, cur_closed = _count_in(first_this, now2)
    prev_total, prev_closed = _count_in(first_prev, first_this)
    trend_total   = cur_total  - prev_total
    trend_fechados = cur_closed - prev_closed

    return {
        "group_id":               group_id,
        "group_name":             group_name,
        "total":                  total,
        "abertos":                abertos,
        "pendentes":              pendentes,
        "resolvidos":             resolvidos,
        "fechados":               fechados,
        "aguardando_fornecedor":  aguardando,
        "pct_abertos":  round(abertos  / total * 100, 1) if total else 0.0,
        "pct_fechados": round((resolvidos + fechados) / total * 100, 1) if total else 0.0,
        "pct_aguardando": round(aguardando / total * 100, 1) if total else 0.0,
        "sla_compliance_pct":     sla_pct,
        "avg_resolution_time_hours": avg_res_h,
        "by_priority":            by_priority,
        "trend_total":            trend_total,
        "trend_fechados":         trend_fechados,
    }


@router.get("/payfly/tickets")
async def payfly_tickets(
    status_filter: str | None = Query(None, description="abertos|fechados|todos"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: dict = Depends(require_role("admin")),
):
    """Lista chamados do grupo PayFly com enriquecimento de nomes."""
    db = get_supabase()
    group_id = _get_payfly_group_id(db)
    if group_id is None:
        return {"data": [], "total": 0, "page": page, "page_size": page_size,
                "error": "Grupo PayFly não encontrado."}

    cols = (
        "id, subject, status, priority, type, group_id, responder_id, "
        "requester_id, company_id, created_at, updated_at, resolved_at, closed_at, "
        "due_by, sla_breached, resolution_time_min, fr_time_min, csat_rating"
    )

    query = (
        db.table("freshservice_tickets")
        .select(cols, count="exact")
        .eq("group_id", group_id)
    )

    if status_filter == "abertos":
        query = query.in_("status", [2, 3, 6])
    elif status_filter == "fechados":
        query = query.in_("status", [4, 5])

    offset = (page - 1) * page_size
    result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
    rows = result.data or []
    if rows:
        rows = _enrich_ticket_names(db, rows)
    return {"data": rows, "total": result.count or 0, "page": page, "page_size": page_size}

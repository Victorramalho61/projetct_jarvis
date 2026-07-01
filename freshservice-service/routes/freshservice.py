import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from pydantic import BaseModel

from auth import get_current_user, require_role
from db import get_supabase
from services.freshservice import get_live_metrics, run_backfill, run_daily_sync, run_projects_sync

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
    try:
        data = db.rpc("freshservice_csat_summary", {"p_from": p_from, "p_to": p_to}).execute().data or {}
    except Exception as e:
        msg = str(e)
        if "57014" in msg or "statement timeout" in msg.lower():
            raise HTTPException(status_code=503, detail="Consulta CSAT excedeu o tempo limite do banco. Tente um período menor.")
        raise
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


# ── Projects ─────────────────────────────────────────────────────────────────

# Ocultos da listagem a pedido — não fazem parte do escopo de acompanhamento atual.
_HIDDEN_PROJECT_IDS = {
    1000525626,  # VOESYNC VIP MARINA
    1000502844,  # VOE+ INTEGRADO COM BENNER RH
    1000485525,  # Implementação IBM MaaS360 (1100 licenças)
    1000491516,  # WOLI - INTEGRAÇÃO COM BENNER RH
    1000485873,  # Implantação de Cabeamento e Infraestrutura – Galpão 37 (Guarulhos)
    1000485975,  # Revisão dos Equipamentos de Rede Lógica
    1000485395,  # VOESYNC LOGISTICA
    1000485980,  # Projeto de Revisão dos Wifi
    1000484766,  # DIALOG - Plataforma de Comunicação
    1000485987,  # Implantação Novo Backup
    1000485984,  # Implantação do Novo Antivírus
    1000485966,  # Migração Servidores pra Hybrid Cloud
    1000485739,  # Implantação de Infraestrutura de TI e CFTV – CD Campinas
    1000485969,  # Ambiente de DR Equinix
    1000486066,  # Instalação das Câmeras CD - VTC / Otimização da rede Wi-Fi Carlos Alberto
}


def _status_maps(db) -> tuple[dict[int, dict], dict[int, dict]]:
    rows = db.table("freshservice_project_statuses").select("*").execute().data or []
    project_statuses = {r["status_id"]: r for r in rows if r["kind"] == "project"}
    task_statuses = {r["status_id"]: r for r in rows if r["kind"] == "task"}
    return project_statuses, task_statuses


def _agent_names(db, agent_ids: set[int]) -> dict[int, str]:
    if not agent_ids:
        return {}
    rows = db.table("freshservice_agents").select("id,name").in_("id", list(agent_ids)).execute().data or []
    return {r["id"]: r["name"] for r in rows}


@router.get("/projects")
async def list_projects(_: dict = Depends(require_role("admin"))):
    db = get_supabase()
    projects = db.table("freshservice_projects").select("*").order("start_date", desc=True).execute().data or []
    projects = [p for p in projects if p["id"] not in _HIDDEN_PROJECT_IDS]
    tasks = (
        db.table("freshservice_project_tasks")
        .select("id,project_id,title,status_id,assignee_id,planned_start_date")
        .execute().data or []
    )

    project_statuses, task_statuses = _status_maps(db)
    agent_ids = {p["manager_id"] for p in projects if p.get("manager_id")}
    agent_ids |= {t["assignee_id"] for t in tasks if t.get("assignee_id")}
    agent_names = _agent_names(db, agent_ids)

    tasks_by_project: dict[int, list[dict]] = {}
    for t in tasks:
        tasks_by_project.setdefault(t["project_id"], []).append(t)

    result = []
    for p in projects:
        proj_tasks = tasks_by_project.get(p["id"], [])
        total = len(proj_tasks)
        is_done = {t["id"]: bool(task_statuses.get(t["status_id"], {}).get("is_done")) for t in proj_tasks}
        done = sum(1 for v in is_done.values() if v)

        pending = [t for t in proj_tasks if not is_done[t["id"]]]
        pending.sort(key=lambda t: (t["planned_start_date"] is None, t["planned_start_date"] or "", t["id"]))
        current_task = pending[0] if pending else None

        status_row = project_statuses.get(p.get("status_id"))
        result.append({
            **p,
            "status_label":          status_row["label"] if status_row else None,
            "manager_name":          agent_names.get(p.get("manager_id")),
            "total_tasks":           total,
            "done_tasks":            done,
            "pending_tasks":         total - done,
            "percent_complete":      round(done / total * 100, 1) if total else None,
            "current_task_title":    current_task["title"] if current_task else None,
            "current_task_assignee": agent_names.get(current_task["assignee_id"]) if current_task else None,
        })
    return result


@router.get("/projects/statuses")
async def list_project_statuses(_: dict = Depends(require_role("admin"))):
    db = get_supabase()
    return db.table("freshservice_project_statuses").select("*").order("kind").order("status_id").execute().data or []


class ProjectStatusUpdate(BaseModel):
    label: str | None = None
    is_done: bool | None = None


@router.patch("/projects/statuses/{status_id}")
async def update_project_status(
    status_id: int,
    body: ProjectStatusUpdate,
    _: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=422, detail="Nada para atualizar.")
    result = db.table("freshservice_project_statuses").update(patch).eq("status_id", status_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Status não encontrado.")
    return result.data[0]


@router.get("/projects/{project_id}")
async def get_project(project_id: int, _: dict = Depends(require_role("admin"))):
    if project_id in _HIDDEN_PROJECT_IDS:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    db = get_supabase()
    project_row = db.table("freshservice_projects").select("*").eq("id", project_id).maybe_single().execute()
    if not project_row.data:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    project = project_row.data

    tasks = (
        db.table("freshservice_project_tasks")
        .select("*")
        .eq("project_id", project_id)
        .order("planned_end_date")
        .execute()
        .data or []
    )

    project_statuses, task_statuses = _status_maps(db)
    agent_names = _agent_names(db, {
        t["assignee_id"] for t in tasks if t.get("assignee_id")
    } | ({project["manager_id"]} if project.get("manager_id") else set()))

    enriched_tasks = []
    for t in tasks:
        status_row = task_statuses.get(t["status_id"])
        enriched_tasks.append({
            **t,
            "status_label":  status_row["label"] if status_row else None,
            "is_done":       bool(status_row and status_row["is_done"]),
            "assignee_name": agent_names.get(t.get("assignee_id")),
        })

    pending_by_assignee: dict[str, list[dict]] = {}
    for t in enriched_tasks:
        if t["is_done"]:
            continue
        key = t["assignee_name"] or "Sem responsável"
        pending_by_assignee.setdefault(key, []).append(t)

    status_row = project_statuses.get(project.get("status_id"))
    total = len(enriched_tasks)
    done = sum(1 for t in enriched_tasks if t["is_done"])

    return {
        "project": {
            **project,
            "status_label":     status_row["label"] if status_row else None,
            "manager_name":     agent_names.get(project.get("manager_id")),
            "total_tasks":      total,
            "done_tasks":       done,
            "pending_tasks":    total - done,
            "percent_complete": round(done / total * 100, 1) if total else None,
        },
        "tasks": enriched_tasks,
        "pending_by_assignee": [
            {"assignee_name": k, "tasks": v} for k, v in sorted(pending_by_assignee.items(), key=lambda x: -len(x[1]))
        ],
    }


@router.post("/projects/sync")
async def trigger_projects_sync(_: dict = Depends(require_role("admin"))):
    import time
    t0 = time.monotonic()
    counts = await run_projects_sync()
    duration = round(time.monotonic() - t0)
    return {"status": "completed", **counts, "duration_seconds": duration}

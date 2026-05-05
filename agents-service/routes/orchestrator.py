"""
Rotas REST do ecossistema LangGraph:
- /api/agents/orchestrator/*  — execução e status do orquestrador
- /api/agents/proposals/*     — gestão de improvement proposals
- /api/agents/changes/*       — gestão de change requests (ITIL)
- /api/agents/windows/*       — deployment windows
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import require_role
from db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(tags=["orchestrator"])


# ── Models ──────────────────────────────────────────────────────────────────────

class RunPipelineIn(BaseModel):
    pipeline: str = "manual"
    agent_name: str = "cto"


class RejectIn(BaseModel):
    reason: str


class MarkFailedIn(BaseModel):
    error: str


class WindowOpenIn(BaseModel):
    reason: str
    duration_minutes: int = 60
    started_by: str = "admin"


# ── Orchestrator ─────────────────────────────────────────────────────────────────

@router.post("/agents/orchestrator/run")
async def run_orchestrator(
    body: RunPipelineIn,
    _user: dict = Depends(require_role("admin")),
):
    from services.agent_runner import run_langgraph_pipeline
    result = await run_langgraph_pipeline(body.pipeline)
    return result


@router.get("/agents/orchestrator/trace/{trace_id}")
async def get_trace(trace_id: str, _user: dict = Depends(require_role("admin"))):
    """Retorna todos os runs e logs de um trace_id — drill-down de um pipeline run."""
    db = get_supabase()
    try:
        runs = (
            db.table("agent_runs")
            .select("*")
            .like("output", f"%trace={trace_id}%")
            .order("started_at")
            .execute().data or []
        )
        logs = (
            db.table("app_logs")
            .select("*")
            .like("detail", f"%{trace_id}%")
            .order("created_at")
            .limit(200)
            .execute().data or []
        )
        return {"trace_id": trace_id, "runs": runs, "logs": logs}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/orchestrator/topology")
async def get_topology(_user: dict = Depends(require_role("admin"))):
    """
    Retorna a topologia do grafo de orquestração para visualização no frontend.
    Inclui nós (agentes), arestas (conexões CTO→agente) e agrupamento por pipeline.
    """
    from services.agent_runner import _PIPELINE_AGENTS

    nodes = [{"id": "cto", "type": "supervisor", "label": "CTO Agent", "pipelines": ["manual"]}]
    edges = []
    pipeline_map: dict[str, list[str]] = {}

    for pipeline, agents in _PIPELINE_AGENTS.items():
        pipeline_map[pipeline] = agents
        for agent in agents:
            if agent == "cto":
                continue
            if not any(n["id"] == agent for n in nodes):
                nodes.append({"id": agent, "type": "agent", "label": agent, "pipelines": [pipeline]})
            else:
                for n in nodes:
                    if n["id"] == agent and pipeline not in n["pipelines"]:
                        n["pipelines"].append(pipeline)
            edges.append({"from": "cto", "to": agent, "pipeline": pipeline})

    return {"nodes": nodes, "edges": edges, "pipelines": pipeline_map}


@router.get("/agents/orchestrator/stream")
async def stream_agent_activity(request: Request, _user: dict = Depends(require_role("admin"))):
    """
    Server-Sent Events — transmite atividade dos agentes em tempo real.

    Formato de cada evento SSE:
      data: {"type": "run"|"message"|"heartbeat", ...payload}

    Uso no frontend:
      const es = new EventSource('/api/agents/orchestrator/stream', {headers:{Authorization:'Bearer ...'}})
      es.onmessage = (e) => { const ev = JSON.parse(e.data); ... }
    """
    db = get_supabase()

    async def event_generator():
        # Snapshot inicial com os últimos 20 runs e mensagens
        try:
            runs = db.table("agent_runs").select(
                "id,pipeline_name,run_type,status,started_at,finished_at,output,error"
            ).order("started_at", desc=True).limit(20).execute().data or []

            messages = db.table("agent_messages").select(
                "id,from_agent,to_agent,message,status,created_at"
            ).order("created_at", desc=True).limit(20).execute().data or []

            payload = json.dumps({
                "type": "snapshot",
                "runs": list(reversed(runs)),
                "messages": list(reversed(messages)),
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            yield f"data: {payload}\n\n"
        except Exception as exc:
            logger.warning("stream: erro no snapshot inicial: %s", exc)

        # Última marca de tempo vista por tabela
        last_run_ts = datetime.now(timezone.utc).isoformat()
        last_msg_ts = datetime.now(timezone.utc).isoformat()
        heartbeat_counter = 0

        while True:
            if await request.is_disconnected():
                break

            await asyncio.sleep(2)
            heartbeat_counter += 1

            try:
                new_runs = (
                    db.table("agent_runs")
                    .select("id,pipeline_name,run_type,status,started_at,finished_at,output,error")
                    .gt("started_at", last_run_ts)
                    .order("started_at")
                    .execute().data or []
                )
                # Inclui runs que mudaram de status (finished_at atualizado)
                updated_runs = (
                    db.table("agent_runs")
                    .select("id,pipeline_name,run_type,status,started_at,finished_at,output,error")
                    .gt("finished_at", last_run_ts)
                    .not_.is_("finished_at", "null")
                    .order("finished_at")
                    .execute().data or []
                )

                new_msgs = (
                    db.table("agent_messages")
                    .select("id,from_agent,to_agent,message,status,created_at")
                    .gt("created_at", last_msg_ts)
                    .order("created_at")
                    .execute().data or []
                )

                all_runs = {r["id"]: r for r in (new_runs + updated_runs)}.values()

                if all_runs or new_msgs:
                    payload = json.dumps({
                        "type": "update",
                        "runs": list(all_runs),
                        "messages": new_msgs,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                    yield f"data: {payload}\n\n"

                    if new_runs:
                        last_run_ts = max(r["started_at"] for r in new_runs)
                    if new_msgs:
                        last_msg_ts = max(m["created_at"] for m in new_msgs)

                # Heartbeat a cada 15s para manter a conexão viva
                if heartbeat_counter % 7 == 0:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.now(timezone.utc).isoformat()})}\n\n"

            except Exception as exc:
                logger.warning("stream: erro no poll: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/agents/orchestrator/agent-health")
async def get_agent_health(_user: dict = Depends(require_role("admin"))):
    """Retorna saúde detalhada dos agentes a partir do último relatório do supervisor."""
    db = get_supabase()
    try:
        # Tenta usar o último relatório do agent_health_supervisor (mais rico e nomeado)
        msg = (
            db.table("agent_messages")
            .select("context,created_at")
            .eq("from_agent", "agent_health_supervisor")
            .eq("to_agent", "cto")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if msg:
            ctx = msg[0].get("context") or {}
            health_map = ctx.get("health_map", {})
            if health_map:
                # Retorna {nome: status} simplificado para o frontend atual + dados completos
                agent_health = {name: info.get("status", "unknown") for name, info in health_map.items()}
                return {
                    "agent_health": agent_health,
                    "health_detail": health_map,
                    "report_time": msg[0].get("created_at"),
                }

        # Fallback: usa agent_runs com join na tabela agents para obter nomes
        runs = (
            db.table("agent_runs")
            .select("agent_id,status,finished_at,pipeline_name,run_type")
            .order("finished_at", desc=True)
            .limit(200)
            .execute()
            .data
        )
        health: dict = {}
        for run in runs:
            name = run.get("pipeline_name") or str(run.get("agent_id", ""))
            if name and name not in health:
                health[name] = run.get("status", "unknown")
        return {"agent_health": health}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/orchestrator/findings")
async def get_findings(limit: int = 50, _user: dict = Depends(require_role("admin"))):
    db = get_supabase()
    try:
        events = (
            db.table("agent_events")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return {"findings": events}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/orchestrator/pipelines")
async def get_pipeline_status(_user: dict = Depends(require_role("admin"))):
    db = get_supabase()
    try:
        runs = (
            db.table("agent_runs")
            .select("pipeline_name,status,started_at,finished_at,output,error")
            .eq("run_type", "pipeline")
            .order("started_at", desc=True)
            .limit(100)
            .execute()
            .data
        )
        # Última run por pipeline
        seen: dict = {}
        for r in runs:
            name = r.get("pipeline_name")
            if name and name not in seen:
                seen[name] = r
        return {"pipeline_runs": list(seen.values())}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/orchestrator/all-agents")
async def get_all_agents_status(_user: dict = Depends(require_role("admin"))):
    """Retorna status unificado: DB agents + LangGraph agents + pipelines + rodando agora."""
    db = get_supabase()
    try:
        # DB agents
        db_agents = db.table("agents").select("id,name,description,agent_type,enabled,schedule_type,schedule_config").order("created_at").execute().data or []

        # Última run de cada DB agent
        if db_agents:
            agent_ids = [a["id"] for a in db_agents]
            all_runs = (
                db.table("agent_runs")
                .select("agent_id,status,started_at,finished_at,error")
                .in_("agent_id", agent_ids)
                .order("started_at", desc=True)
                .limit(len(agent_ids) * 5)
                .execute()
                .data or []
            )
            last_run_per_agent: dict = {}
            for r in all_runs:
                aid = r.get("agent_id")
                if aid and aid not in last_run_per_agent:
                    last_run_per_agent[aid] = r
            for a in db_agents:
                a["last_run"] = last_run_per_agent.get(a["id"])

        # LangGraph health (do supervisor)
        langgraph_health: dict = {}
        report_time = None
        msg = (
            db.table("agent_messages")
            .select("context,created_at")
            .eq("from_agent", "agent_health_supervisor")
            .eq("to_agent", "cto")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if msg:
            ctx = msg[0].get("context") or {}
            langgraph_health = ctx.get("health_map", {})
            report_time = msg[0].get("created_at")

        # Rodando agora (todas as fontes)
        running_now = (
            db.table("agent_runs")
            .select("agent_id,pipeline_name,run_type,started_at")
            .eq("status", "running")
            .order("started_at", desc=True)
            .limit(50)
            .execute()
            .data or []
        )

        # Pipelines — última run por nome
        pipeline_runs_raw = (
            db.table("agent_runs")
            .select("pipeline_name,status,started_at,finished_at")
            .eq("run_type", "pipeline")
            .order("started_at", desc=True)
            .limit(100)
            .execute()
            .data or []
        )
        pipelines: dict = {}
        for r in pipeline_runs_raw:
            name = r.get("pipeline_name")
            if name and name not in pipelines:
                pipelines[name] = r

        return {
            "db_agents": db_agents,
            "langgraph_health": langgraph_health,
            "report_time": report_time,
            "running_now": running_now,
            "pipelines": pipelines,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Proposals ─────────────────────────────────────────────────────────────────────

@router.get("/agents/slas")
async def get_slas(
    agent: Optional[str] = None,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        q = db.table("agent_slas").select("*").order("agent_name").order("sla_name")
        if agent:
            q = q.eq("agent_name", agent)
        rows = q.execute().data or []
        from graph_engine.tools.sla_tracker import get_system_sla_overview
        overview = get_system_sla_overview()
        return {"slas": rows, "overview": overview}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agents/slas/seed")
async def seed_slas(
    _user: dict = Depends(require_role("admin")),
):
    """Popula SLAs pré-definidos para todos os agentes existentes."""
    try:
        from graph_engine.tools.sla_tracker import seed_predefined_slas
        count = seed_predefined_slas()
        return {"ok": True, "slas_created": count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/proposals/process-inbox")
async def process_proposals_inbox_stream(
    _user: dict = Depends(require_role("admin")),
):
    """
    SSE stream: processa todos os agentes com proposals pendentes na inbox.
    Emite eventos de progresso conforme cada agente termina.
    """
    from graph_engine.tools.proposal_executor import process_inbox_proposals

    # Agentes que recebem proposals via inbox, na ordem de prioridade
    _AGENTS = [
        ("docker_intel",   "graph_engine.agents.docker_intel"),
        ("fix_validator",  "graph_engine.agents.fix_validator"),
        ("evolution_agent","graph_engine.agents.evolution_agent"),
        ("db_dba_agent",   "graph_engine.agents.db_dba_agent"),
        ("infrastructure", "graph_engine.agents.infrastructure"),
        ("automation",     "graph_engine.agents.automation"),
        ("uptime",         "graph_engine.agents.uptime"),
        ("change_mgmt",    "graph_engine.agents.change_mgmt"),
    ]

    db = get_supabase()

    def _count_inbox(agent_name: str) -> int:
        from graph_engine.tools.supabase_tools import get_pending_messages
        msgs = get_pending_messages(agent_name)
        return sum(1 for m in msgs if m.get("context", {}).get("proposal_id"))

    def _count_db_status(status: str) -> int:
        return db.table("improvement_proposals").select("id", count="exact").eq("validation_status", status).execute().count or 0

    async def _generate():
        import importlib, json as _json

        total_in_progress = _count_db_status("auto_implementing")
        yield f"data: {_json.dumps({'type': 'start', 'total': total_in_progress})}\n\n"

        grand_applied = 0
        grand_failed  = 0
        grand_skipped = 0

        for agent_name, module_path in _AGENTS:
            inbox_count = _count_inbox(agent_name)
            if inbox_count == 0:
                yield f"data: {_json.dumps({'type': 'agent_skip', 'agent': agent_name, 'reason': 'inbox vazia'})}\n\n"
                grand_skipped += 1
                await asyncio.sleep(0)
                continue

            yield f"data: {_json.dumps({'type': 'agent_start', 'agent': agent_name, 'inbox': inbox_count})}\n\n"

            try:
                mod = importlib.import_module(module_path)
                handler = getattr(mod, "_handle_proposal", None)
                if handler is None:
                    yield f"data: {_json.dumps({'type': 'agent_error', 'agent': agent_name, 'error': 'sem _handle_proposal'})}\n\n"
                    continue

                decisions: list = []
                processed = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda an=agent_name, h=handler, d=decisions: process_inbox_proposals(an, db, h, d),
                )
                applied = sum(1 for d in decisions if "aplicada:" in str(d))
                failed  = processed - applied
                grand_applied += applied
                grand_failed  += failed

                yield f"data: {_json.dumps({'type': 'agent_done', 'agent': agent_name, 'processed': processed, 'applied': applied, 'failed': failed})}\n\n"
            except Exception as exc:
                yield f"data: {_json.dumps({'type': 'agent_error', 'agent': agent_name, 'error': str(exc)[:200]})}\n\n"

            await asyncio.sleep(0)

        remaining = _count_db_status("auto_implementing")
        yield f"data: {_json.dumps({'type': 'done', 'applied': grand_applied, 'failed': grand_failed, 'remaining': remaining})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/agents/proposals/metrics")
async def proposals_metrics(
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        def _count(status: str) -> int:
            return db.table("improvement_proposals").select("id", count="exact").eq("validation_status", status).execute().count or 0

        pending       = _count("pending") + _count("pending_cto")
        approved      = _count("approved")
        in_progress   = _count("auto_implementing")
        applied       = _count("applied")
        rejected      = _count("rejected")
        failed        = _count("implementation_failed")
        total_decided = approved + in_progress + applied + rejected + failed
        execution_rate = round(100 * applied / max(approved + in_progress + applied + failed, 1), 1)
        failure_rate   = round(100 * failed  / max(approved + in_progress + applied + failed, 1), 1)
        return {
            "pending": pending,
            "approved_waiting": approved,
            "in_progress": in_progress,
            "applied_success": applied,
            "rejected": rejected,
            "implementation_failed": failed,
            "total_decided": total_decided,
            "execution_rate_pct": execution_rate,
            "failure_rate_pct": failure_rate,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/proposals")
async def list_proposals(
    status: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = 50,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        q = db.table("improvement_proposals").select("*").order("created_at", desc=True).limit(limit)
        if status:
            q = q.eq("validation_status", status)
        if agent:
            q = q.eq("source_agent", agent)
        return {"proposals": q.execute().data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        db.table("improvement_proposals").update({
            "validation_status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", proposal_id).execute()
        return {"ok": True, "proposal_id": proposal_id, "status": "approved"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/proposals/{proposal_id}/mark-applied")
async def mark_proposal_applied(
    proposal_id: str,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        db.table("improvement_proposals").update({
            "validation_status": "applied",
            "applied": True,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "implementation_error": None,
        }).eq("id", proposal_id).execute()
        return {"ok": True, "proposal_id": proposal_id, "status": "applied"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/proposals/{proposal_id}/mark-failed")
async def mark_proposal_failed(
    proposal_id: str,
    body: MarkFailedIn,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        db.table("improvement_proposals").update({
            "validation_status": "implementation_failed",
            "applied": False,
            "implementation_error": body.error,
        }).eq("id", proposal_id).execute()
        return {"ok": True, "proposal_id": proposal_id, "status": "implementation_failed"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    body: RejectIn,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        db.table("improvement_proposals").update({
            "validation_status": "rejected",
            "rejection_reason": body.reason,
        }).eq("id", proposal_id).execute()
        return {"ok": True, "proposal_id": proposal_id, "status": "rejected"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Change Requests ───────────────────────────────────────────────────────────────

@router.get("/agents/changes")
async def list_changes(
    status: Optional[str] = None,
    limit: int = 50,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        q = db.table("change_requests").select("*").order("created_at", desc=True).limit(limit)
        if status:
            q = q.eq("status", status)
        return {"changes": q.execute().data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/changes/{change_id}/approve")
async def approve_change(
    change_id: str,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        db.table("change_requests").update({
            "status": "approved",
            "approved_by": _user.get("id", "admin"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", change_id).execute()
        return {"ok": True, "change_id": change_id, "status": "approved"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/changes/{change_id}/reject")
async def reject_change(
    change_id: str,
    body: RejectIn,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        db.table("change_requests").update({
            "status": "rejected",
            "rejection_reason": body.reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", change_id).execute()
        return {"ok": True, "change_id": change_id, "status": "rejected"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Deployment Windows ────────────────────────────────────────────────────────────

@router.get("/agents/windows/active")
async def get_active_window(_user: dict = Depends(require_role("admin"))):
    db = get_supabase()
    try:
        rows = db.table("deployment_windows").select("*").eq("active", True).order("started_at", desc=True).limit(1).execute().data
        return {"active_window": rows[0] if rows else None}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agents/windows/open")
async def open_window(
    body: WindowOpenIn,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        from datetime import timedelta
        expected_end = (datetime.now(timezone.utc) + timedelta(minutes=body.duration_minutes)).isoformat()
        row = db.table("deployment_windows").insert({
            "active": True,
            "reason": body.reason,
            "started_by": body.started_by or _user.get("id", "admin"),
            "expected_end": expected_end,
        }).execute().data[0]
        return {"ok": True, "window": row}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agents/windows/close")
async def close_window(_user: dict = Depends(require_role("admin"))):
    db = get_supabase()
    try:
        db.table("deployment_windows").update({
            "active": False,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }).eq("active", True).execute()
        return {"ok": True, "message": "Janela de deploy fechada"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Governance Reports ────────────────────────────────────────────────────────────

@router.get("/agents/governance/reports")
async def list_governance_reports(
    limit: int = 10,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        rows = (
            db.table("governance_reports")
            .select("*")
            .order("report_date", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return {"reports": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Inbox do Humano (mensagens dos agentes) ───────────────────────────────────────

@router.get("/agents/inbox")
async def get_inbox(
    unread_only: bool = False,
    limit: int = 50,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        q = (
            db.table("agent_messages")
            .select("*")
            .eq("to_agent", "human")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if unread_only:
            q = q.eq("status", "pending")
        rows = q.execute().data or []
        unread_count = sum(1 for r in rows if r.get("status") == "pending")
        return {"messages": rows, "unread_count": unread_count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/inbox/{message_id}/read")
async def mark_message_read(
    message_id: str,
    _user: dict = Depends(require_role("admin")),
):
    db = get_supabase()
    try:
        db.table("agent_messages").update({
            "status": "read",
            "read_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", message_id).execute()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agents/inbox/read-all")
async def mark_all_read(_user: dict = Depends(require_role("admin"))):
    db = get_supabase()
    try:
        db.table("agent_messages").update({
            "status": "read",
            "read_at": datetime.now(timezone.utc).isoformat(),
        }).eq("to_agent", "human").eq("status", "pending").execute()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

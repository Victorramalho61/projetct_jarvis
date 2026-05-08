import asyncio
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

import httpx
import jwt

from db import get_settings, get_supabase
from services.app_logger import log_event

logger = logging.getLogger(__name__)

# Apenas estas vars de ambiente chegam ao subprocess — SERVICE_ROLE_KEY e
# ANTHROPIC_API_KEY são explicitamente excluídos para evitar acesso indevido.
_SAFE_ENV_KEYS = {"PATH", "HOME", "LANG", "TZ", "PYTHONPATH", "GITHUB_TOKEN"}


def _get_service_token() -> str:
    s = get_settings()
    return jwt.encode(
        {
            "id": "agents-service",
            "role": "admin",
            "active": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        s.jwt_secret,
        algorithm="HS256",
    )


async def run_agent(agent: dict) -> dict:
    db = get_supabase()
    run = db.table("agent_runs").insert({
        "agent_id": agent["id"],
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).execute().data[0]
    run_id = run["id"]

    try:
        if agent["agent_type"] == "freshservice_sync":
            output = await _run_freshservice_sync(agent)
        elif agent["agent_type"] == "expenses_sync":
            output = await _run_expenses_sync(agent)
        elif agent["agent_type"] == "script":
            output = await asyncio.get_event_loop().run_in_executor(
                None, _run_script_sync, agent
            )
        elif agent["agent_type"] == "langgraph":
            output = await asyncio.get_event_loop().run_in_executor(
                None, _run_langgraph_sync, agent
            )
        else:
            raise ValueError(f"Tipo desconhecido: {agent['agent_type']}")

        db.table("agent_runs").update({
            "status": "success",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "output": output,
        }).eq("id", run_id).execute()
        log_event("info", "agents", f"Agente '{agent['name']}' concluído")
        return {"status": "success", "run_id": run_id}

    except Exception as exc:
        db.table("agent_runs").update({
            "status": "error",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        }).eq("id", run_id).execute()
        log_event("error", "agents", f"Erro no agente '{agent['name']}'", detail=str(exc))
        return {"status": "error", "run_id": run_id, "error": str(exc)}


def _service_headers(extra: dict | None = None) -> dict:
    """Headers padrão para chamadas inter-serviço: auth + trace propagation."""
    from main import current_trace_id
    headers = {"Authorization": f"Bearer {_get_service_token()}"}
    tid = current_trace_id.get(None)
    if tid:
        headers["X-Trace-ID"] = tid
    if extra:
        headers.update(extra)
    return headers


async def _run_expenses_sync(agent: dict) -> str:
    import time
    expenses_url = os.getenv("EXPENSES_SERVICE_URL", "http://expenses-service:8006")
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{expenses_url}/api/expenses/sync",
            headers=_service_headers(),
        )
        r.raise_for_status()
    elapsed = round(time.monotonic() - t0)
    data = r.json()
    msg = data.get("message", "sync iniciado")
    log_event("info", "expenses_sync", f"Sync Gastos TI: {msg} em {elapsed}s")
    return f"{msg} ({elapsed}s)"


async def _run_freshservice_sync(agent: dict) -> str:
    import time
    mode = (agent.get("config") or {}).get("mode", "daily")
    if mode not in ("daily", "backfill"):
        mode = "daily"
    freshservice_url = os.getenv("FRESHSERVICE_SERVICE_URL", "http://freshservice-service:8003")
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{freshservice_url}/api/freshservice/sync/{mode}",
            headers=_service_headers(),
        )
        r.raise_for_status()
    elapsed = round(time.monotonic() - t0)
    data = r.json()
    count = data.get("tickets_upserted", "?")
    return f"Sync Freshservice ({mode}) concluído: {count} tickets em {elapsed}s"


def _run_langgraph_sync(agent: dict) -> str:
    from graph_engine.graph import run_agent_by_name
    agent_name = (agent.get("config") or {}).get("agent_name", agent.get("name", "cto"))
    pipeline = (agent.get("config") or {}).get("pipeline", "manual")
    result = run_agent_by_name(agent_name, extra_state={"current_pipeline": pipeline})
    findings = result.get("findings", [])
    decisions = result.get("decisions", [])
    return f"findings={len(findings)} decisions={len(decisions)}"


# Agentes que cada pipeline executa diretamente.
# O CTO é reservado para o pipeline 'manual' (processa eventos gerados pelos outros).
_PIPELINE_AGENTS: dict[str, list[str]] = {
    "monitoring":  [
        "uptime", "quality", "docker_intel", "backend_agent",
        "infrastructure", "api_agent", "log_scanner",
        "agent_health_supervisor",
    ],
    "security":    ["security", "code_security"],
    "cicd":        ["cicd_monitor"],
    "dba":         ["db_dba_agent"],
    "governance":  [
        "opportunity_scout", "log_strategic_advisor", "change_mgmt",
        "itil_version", "quality_validator",
        "quality_code_backend", "quality_code_frontend",
        "integration_validator", "change_validator",
        "scheduling", "automation",
        "log_intelligence", "log_improver", "fix_validator",
        "proposal_analysis_agent",
        "proposal_prioritizer",
        "proposal_supervisor",
        "llm_manager_agent",
        "cto_assessor_agent",
    ],
    "documentation": ["docs"],
    "evolution":   ["evolution_agent", "frontend_agent"],
    "manual":      ["cto"],
}


_PIPELINE_TIMEOUT_S = 900  # 15 minutos por pipeline
_AGENT_TIMEOUT_S = 180     # 3 minutos por agente individual
_AGENT_MAX_RETRIES = 2
_AGENT_RETRY_BACKOFF_S = 3


async def _run_agent_with_retry(
    agent_name: str,
    pipeline: str,
    trace_id: str,
    run_agent_by_name,
) -> dict:
    """Executa um agente com até _AGENT_MAX_RETRIES tentativas e timeout por agente."""
    last_exc: Exception | None = None
    for attempt in range(1, _AGENT_MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda an=agent_name: run_agent_by_name(
                        an, extra_state={"current_pipeline": pipeline, "trace_id": trace_id}
                    ),
                ),
                timeout=_AGENT_TIMEOUT_S,
            )
            return result
        except asyncio.TimeoutError:
            last_exc = TimeoutError(f"{agent_name}: timeout após {_AGENT_TIMEOUT_S}s")
            if attempt < _AGENT_MAX_RETRIES:
                logger.warning(
                    "[%s][%s] %s timeout (tentativa %d/%d), retry em %ds",
                    trace_id, pipeline, agent_name, attempt, _AGENT_MAX_RETRIES,
                    _AGENT_RETRY_BACKOFF_S,
                )
                await asyncio.sleep(_AGENT_RETRY_BACKOFF_S)
        except Exception as exc:
            last_exc = exc
            if attempt < _AGENT_MAX_RETRIES:
                logger.warning(
                    "[%s][%s] %s falhou (tentativa %d/%d), retry em %ds: %s",
                    trace_id, pipeline, agent_name, attempt, _AGENT_MAX_RETRIES,
                    _AGENT_RETRY_BACKOFF_S, exc,
                )
                await asyncio.sleep(_AGENT_RETRY_BACKOFF_S)
    raise last_exc  # type: ignore[misc]


async def run_langgraph_pipeline(pipeline: str) -> dict:
    """Executa os agentes do pipeline com trace_id, retry por agente e timeout global."""
    import time
    from graph_engine.observability import pipeline_span, record_agent_run
    from graph_engine.graph import run_agent_by_name

    async def _execute() -> dict:
        db = get_supabase()
        agents_to_run = _PIPELINE_AGENTS.get(pipeline, ["cto"])

        with pipeline_span(pipeline) as span:
            trace_id = span["trace_id"]

            pipeline_rec = db.table("agent_runs").insert({
                "agent_id": None,
                "pipeline_name": pipeline,
                "run_type": "pipeline",
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }).execute().data[0]
            pipeline_run_id = pipeline_rec["id"]

            total_findings = 0
            total_decisions = 0
            errors: list[str] = []

            for agent_name in agents_to_run:
                agent_rec = db.table("agent_runs").insert({
                    "agent_id": None,
                    "pipeline_name": agent_name,
                    "run_type": "pipeline",
                    "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }).execute().data[0]
                agent_run_id = agent_rec["id"]

                t0 = time.monotonic()
                try:
                    result = await _run_agent_with_retry(agent_name, pipeline, trace_id, run_agent_by_name)
                    findings  = result.get("findings", [])
                    decisions = result.get("decisions", [])
                    total_findings  += len(findings)
                    total_decisions += len(decisions)
                    duration = time.monotonic() - t0
                    record_agent_run(agent_name, pipeline, duration, success=True, findings=len(findings))
                    db.table("agent_runs").update({
                        "status": "success",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "output": f"findings={len(findings)} decisions={len(decisions)} trace={trace_id}",
                    }).eq("id", agent_run_id).execute()
                    log_event("info", "agents", f"[{trace_id}][{pipeline}] {agent_name}: {len(findings)} findings ({duration:.1f}s)")
                except Exception as exc:
                    duration = time.monotonic() - t0
                    err_msg = str(exc)[:500]
                    errors.append(f"{agent_name}: {err_msg}")
                    record_agent_run(agent_name, pipeline, duration, success=False)
                    db.table("agent_runs").update({
                        "status": "error",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "error": err_msg,
                    }).eq("id", agent_run_id).execute()
                    log_event("error", "agents", f"[{trace_id}][{pipeline}] {agent_name} falhou após {_AGENT_MAX_RETRIES} tentativas", detail=err_msg)

            final_status = "error" if errors and total_findings == 0 else "success"
            summary = f"agents={len(agents_to_run)} findings={total_findings} decisions={total_decisions} trace={trace_id}"
            db.table("agent_runs").update({
                "status": final_status,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "output": summary,
                "error": "; ".join(errors) if errors else None,
            }).eq("id", pipeline_run_id).execute()

            log_event("info", "agents", f"Pipeline '{pipeline}' concluído: {summary}")
            return {
                "status": final_status,
                "run_id": pipeline_run_id,
                "pipeline": pipeline,
                "trace_id": span["trace_id"],
                "agents_run": len(agents_to_run),
                "findings": total_findings,
                "errors": errors,
            }

    try:
        return await asyncio.wait_for(_execute(), timeout=_PIPELINE_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.error("Pipeline '%s' excedeu timeout de %ds", pipeline, _PIPELINE_TIMEOUT_S)
        log_event("error", "agents", f"Pipeline '{pipeline}' timeout após {_PIPELINE_TIMEOUT_S}s")
        return {"status": "timeout", "pipeline": pipeline, "errors": [f"timeout {_PIPELINE_TIMEOUT_S}s"]}


def _run_script_sync(agent: dict) -> str:
    code = (agent.get("config") or {}).get("code", "")
    if not code.strip():
        raise ValueError("Nenhum código definido no agente")

    safe_env = {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}
    safe_env["SUPABASE_URL"] = os.environ.get("SUPABASE_URL", "")
    safe_env["SUPABASE_ANON_KEY"] = os.environ.get("SUPABASE_ANON_KEY", "")

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmppath = f.name
    try:
        result = subprocess.run(
            ["python3", tmppath],
            capture_output=True, text=True, timeout=300,
            env=safe_env,
        )
        output = (result.stdout or "")[-10_000:]
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "exit code não zero")[-2_000:])
        return output
    finally:
        os.unlink(tmppath)

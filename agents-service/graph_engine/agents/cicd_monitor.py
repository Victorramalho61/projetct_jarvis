"""
CI/CD Monitor — monitora a esteira GitHub Actions e aciona agentes de qualidade
em cascata conforme o evento: commit, merge, deploy_ok, deploy_fail.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_QUALITY_CASCADE = {
    "commit":     ["quality_code_backend", "quality_code_frontend"],
    "merge":      ["integration_validator", "change_validator", "quality_code_backend"],
    "deploy_ok":  ["itil_version", "docs"],
    "deploy_fail": [],  # tratado via agent_event → CTO
}


def _fetch_recent_workflow_runs(since_minutes: int = 30) -> list[dict]:
    try:
        from graph_engine.tools.github_tools import list_workflow_runs
        return list_workflow_runs(since_minutes=since_minutes) or []
    except Exception as exc:
        logger.warning("cicd_monitor: não foi possível buscar workflow runs: %s", exc)
        return []


def _classify_runs(runs: list[dict]) -> dict:
    events: dict = {"commit": [], "merge": [], "deploy_ok": [], "deploy_fail": []}
    for run in runs:
        conclusion = run.get("conclusion")
        event = run.get("event", "")
        name = run.get("name", "").lower()

        if conclusion == "failure":
            events["deploy_fail"].append(run)
        elif conclusion == "success":
            if "deploy" in name or event == "push":
                events["deploy_ok"].append(run)
            elif event in ("pull_request",) and run.get("head_branch", "").startswith("main"):
                events["merge"].append(run)
            else:
                events["commit"].append(run)

    return events


def run(state: dict) -> dict:
    from graph_engine.tools.supabase_tools import insert_agent_event, send_agent_message
    from graph_engine.tools.cto_tools import dispatch_agent

    findings = []
    decisions = []

    runs = _fetch_recent_workflow_runs(since_minutes=30)
    if not runs:
        findings.append({"agent": "cicd_monitor", "status": "sem_runs_recentes"})
        return {"findings": findings, "decisions": decisions, "next_agent": "END"}

    classified = _classify_runs(runs)

    for event_type, event_runs in classified.items():
        if not event_runs:
            continue

        findings.append({
            "agent": "cicd_monitor",
            "event_type": event_type,
            "count": len(event_runs),
            "runs": [{"id": r.get("id"), "name": r.get("name"), "conclusion": r.get("conclusion")} for r in event_runs[:3]],
        })

        if event_type == "deploy_fail":
            for run_data in event_runs:
                try:
                    insert_agent_event(
                        event_type="deploy_failed",
                        source="cicd_monitor",
                        payload={"run_id": run_data.get("id"), "name": run_data.get("name"), "url": run_data.get("html_url", "")},
                        priority="critical",
                    )
                    send_agent_message(
                        from_agent="cicd_monitor",
                        to_agent="cto",
                        message=f"Deploy falhou: {run_data.get('name')} — URL: {run_data.get('html_url', 'N/A')}",
                        context=run_data,
                    )
                    decisions.append(f"Alerta de deploy_fail enviado ao CTO: {run_data.get('name')}")
                except Exception as exc:
                    logger.error("cicd_monitor: erro ao alertar deploy_fail: %s", exc)
            continue

        agents_to_dispatch = _QUALITY_CASCADE.get(event_type, [])
        for agent_name in agents_to_dispatch:
            try:
                dispatch_agent(
                    agent_name=agent_name,
                    task_description=f"Validação {event_type}: {len(event_runs)} run(s) recente(s)",
                    priority="high",
                    context={"event_type": event_type, "runs": event_runs[:2]},
                )
                decisions.append(f"Despachado {agent_name} para evento {event_type}")
            except Exception as exc:
                logger.error("cicd_monitor: erro ao despachar %s: %s", agent_name, exc)

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {"cicd_monitor_run": datetime.now(timezone.utc).isoformat()},
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

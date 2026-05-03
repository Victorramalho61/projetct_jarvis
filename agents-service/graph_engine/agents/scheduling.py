"""Scheduling Agent — analisa e otimiza agendamentos. Motor: Python puro."""
from collections import defaultdict
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import log_event, query_agent_runs, query_agents, send_agent_message


def run(state: dict) -> dict:
    findings = []
    agents = query_agents(enabled=True)
    now = datetime.now(timezone.utc).isoformat()

    # Analisa agentes com alta taxa de falha
    for agent in agents:
        runs = query_agent_runs(agent_id=agent["id"], limit=20)
        if not runs:
            continue
        failed = [r for r in runs if r["status"] == "error"]
        fail_rate = len(failed) / len(runs)
        if fail_rate > 0.5:
            findings.append({
                "type": "high_failure_rate",
                "agent_name": agent["name"],
                "agent_id": agent["id"],
                "fail_rate": round(fail_rate * 100, 1),
                "total_runs": len(runs),
            })
            log_event("warning", "scheduling_agent", f"Agente '{agent['name']}' com {fail_rate*100:.0f}% de falhas")

    # Detecta agentes com schedule 'interval' muito curto (< 5min) que falham frequentemente
    for agent in agents:
        if agent.get("schedule_type") == "interval":
            minutes = agent.get("schedule_config", {}).get("minutes", 60)
            if minutes < 5:
                findings.append({
                    "type": "aggressive_schedule",
                    "agent_name": agent["name"],
                    "interval_minutes": minutes,
                    "suggestion": "Considere aumentar o intervalo para pelo menos 5 minutos",
                })

    if findings:
        send_agent_message(
            from_agent="scheduling_agent",
            to_agent="cto",
            content={"trigger": "scheduling_review", "findings": findings},
        )

    return {"findings": findings, "context": {"scheduling_ran_at": now, "agents_analyzed": len(agents)}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

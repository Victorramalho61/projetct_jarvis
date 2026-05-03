"""Automation Agent — identifica tarefas repetitivas e propõe automações. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event, query_agent_runs, query_agents


def run(state: dict) -> dict:
    findings = []
    agents = query_agents(enabled=True)

    # Detecta agentes manuais que são executados frequentemente (candidatos a automação)
    for agent in agents:
        if agent.get("schedule_type") != "manual":
            continue
        runs = query_agent_runs(agent_id=agent["id"], limit=30)
        if len(runs) >= 10:
            findings.append({"type": "frequent_manual_agent", "agent_name": agent["name"], "run_count": len(runs)})
            insert_improvement_proposal(
                source_agent="automation_agent",
                proposal_type="config_change",
                title=f"Agente '{agent['name']}' executado manualmente {len(runs)}x — candidato a agendamento",
                description=f"O agente '{agent['name']}' é do tipo manual mas foi executado {len(runs)} vezes. Considere adicionar um schedule.",
                proposed_action=f"Alterar schedule_type de 'manual' para 'interval' ou 'daily' com configuração adequada.",
                priority="low",
                estimated_effort="minutes",
                risk="low",
                auto_implementable=False,
                source_findings=[{"agent_id": agent["id"], "runs": len(runs)}],
            )
            log_event("info", "automation_agent", f"Agente '{agent['name']}' candidato a agendamento automático")

    return {"findings": findings, "context": {"automation_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

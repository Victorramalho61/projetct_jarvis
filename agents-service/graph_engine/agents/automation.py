"""Automation Agent — identifica tarefas repetitivas e propõe automações. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event, query_agent_runs, query_agents


def _handle_proposal(proposal: dict, _msg: dict) -> tuple[bool, str]:
    action = proposal.get("proposed_action", "") or proposal.get("title", "")
    return True, f"Automação registrada para implementação: {action[:200]}"


def run(state: dict) -> dict:
    from db import get_supabase
    from graph_engine.tools.proposal_executor import process_inbox_proposals

    db = get_supabase()
    decisions: list = []
    process_inbox_proposals("automation", db, _handle_proposal, decisions)

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

    return {"findings": findings, "decisions": decisions, "context": {"automation_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

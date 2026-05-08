"""Infrastructure Agent — analisa recursos Docker e configurações. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event
from graph_engine.tools.docker_tools import get_container_stats, inspect_container, list_containers


_MEM_HIGH = 80.0  # % de memória para recomendar aumento de limite
_MEM_LOW = 20.0   # % de memória para recomendar redução de limite (economia)


def _handle_proposal(proposal: dict, _msg: dict) -> tuple[bool, str]:
    """Proposals de infraestrutura: documenta e sinaliza para revisão manual do DevOps."""
    action = proposal.get("proposed_action", "") or ""
    title = proposal.get("title", "")[:80]
    return True, f"Recomendação de infra registrada — revisar docker-compose.yml manualmente: {action[:150] or title}"


def run(state: dict) -> dict:
    from db import get_supabase
    from graph_engine.tools.proposal_executor import process_inbox_proposals

    db = get_supabase()
    decisions: list = []
    process_inbox_proposals("infrastructure", db, _handle_proposal, decisions)

    findings = []
    containers = list_containers()

    for c in containers:
        if isinstance(c, dict) and "error" not in c:
            stats = get_container_stats(c["name"])
            details = inspect_container(c["name"])
            mem_pct = stats.get("memory_percent", 0)
            mem_limit_mb = stats.get("memory_limit_mb", 0)

            if mem_pct > _MEM_HIGH and mem_limit_mb > 0:
                new_limit = int(mem_limit_mb * 1.5)
                insert_improvement_proposal(
                    source_agent="infrastructure",
                    proposal_type="infrastructure",
                    title=f"Container {c['name']} com uso de memória alto ({mem_pct:.1f}%)",
                    description=f"Container usando {mem_pct:.1f}% do limite de {mem_limit_mb}MB. Risco de OOM.",
                    proposed_action=f"Aumentar mem_limit de {int(mem_limit_mb)}m para {new_limit}m em docker-compose.yml",
                    priority="high" if mem_pct > 90 else "medium",
                    estimated_effort="minutes",
                    risk="low",
                    auto_implementable=False,
                    affected_files=["docker-compose.yml"],
                    evidence=f"CPU: {stats.get('cpu_percent', 0):.1f}% | MEM: {mem_pct:.1f}% de {mem_limit_mb}MB",
                )
                findings.append({"type": "high_memory_container", "container": c["name"], "mem_pct": mem_pct})

            restart_count = details.get("restart_count", 0)
            if restart_count >= 5:
                findings.append({"type": "unstable_container", "container": c["name"], "restart_count": restart_count})
                log_event("warning", "infrastructure", f"Container {c['name']} reiniciou {restart_count}x")

    return {"findings": findings, "decisions": decisions, "context": {"infrastructure_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

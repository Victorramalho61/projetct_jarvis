"""
Opportunity Scout — radar data-driven de oportunidades.
Agrega sinais objetivos de todos os agentes e ranqueia as top 10 oportunidades
para alimentar o evolution_agent no pipeline de governance.
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_AGENT_REGISTRY = [
    "cto", "log_scanner", "log_improver", "log_strategic_advisor",
    "security", "code_security", "uptime", "docker_intel", "infrastructure",
    "quality", "quality_validator", "docs", "api_agent", "automation",
    "scheduling", "backend_agent", "frontend_agent", "fix_validator",
    "change_mgmt", "change_validator", "integration_validator", "itil_version",
    "log_intelligence", "cicd_monitor", "db_dba_agent", "quality_code_backend",
    "quality_code_frontend", "evolution_agent", "opportunity_scout",
]


def _aggregate_signals() -> list[dict]:
    from graph_engine.tools.supabase_tools import (
        query_improvement_proposals,
        query_app_logs,
        query_agent_runs,
        query_monitored_systems,
        query_quality_metrics,
    )

    opportunities = []

    proposals = query_improvement_proposals(status="pending", limit=100)
    stale_14d = []
    cutoff = datetime.now(timezone.utc).isoformat()[:10]
    for p in proposals:
        created = p.get("created_at", "")[:10]
        if created and created < cutoff and p.get("priority") in ("critical", "high"):
            stale_14d.append(p)

    if stale_14d:
        opportunities.append({
            "category": "blocked_proposals",
            "title": f"{len(stale_14d)} proposals críticas/altas sem aprovação",
            "description": "Proposals de alta prioridade estão pendentes por mais de 14 dias sem ação",
            "count": len(stale_14d),
            "score": len(stale_14d) * 3,
            "effort": "baixo",
        })

    logs = query_app_logs(level="error", limit=500, since_minutes=43200)  # 30 dias
    module_count: dict = {}
    for entry in logs:
        module = entry.get("source") or "unknown"
        module_count[module] = module_count.get(module, 0) + 1

    recurring = [(m, c) for m, c in module_count.items() if c > 50]
    if recurring:
        opportunities.append({
            "category": "recurring_errors",
            "title": f"{len(recurring)} módulos com erros recorrentes (30 dias)",
            "description": f"Módulos: {', '.join(m for m, _ in sorted(recurring, key=lambda x: -x[1])[:5])}",
            "count": len(recurring),
            "score": sum(c for _, c in recurring) // 10,
            "effort": "médio",
        })

    systems = query_monitored_systems(enabled=True)
    metrics = query_quality_metrics(since_hours=168)
    low_uptime = []
    for s in systems:
        sys_metrics = [m for m in metrics if m.get("service") == s.get("name") and m.get("metric_name") == "availability"]
        if sys_metrics:
            avg = sum(m.get("metric_value", 100) for m in sys_metrics) / len(sys_metrics)
            if avg < 99.0:
                low_uptime.append({"service": s.get("name"), "avg_uptime": round(avg, 2)})

    if low_uptime:
        opportunities.append({
            "category": "low_uptime",
            "title": f"{len(low_uptime)} serviços abaixo de 99% de uptime na semana",
            "description": json.dumps(low_uptime[:5], ensure_ascii=False),
            "count": len(low_uptime),
            "score": len(low_uptime) * 5,
            "effort": "alto",
        })

    runs = query_agent_runs(status="error", limit=50)
    agent_errors: dict = {}
    for run in runs:
        aid = run.get("agent_id") or "unknown"
        agent_errors[aid] = agent_errors.get(aid, 0) + 1

    failing_agents = [(a, c) for a, c in agent_errors.items() if c > 3 and a != "unknown"]
    if failing_agents:
        opportunities.append({
            "category": "failing_agents",
            "title": f"{len(failing_agents)} agentes com falhas repetidas",
            "description": f"Agentes: {', '.join(str(a) for a, _ in failing_agents[:5])}",
            "count": len(failing_agents),
            "score": len(failing_agents) * 4,
            "effort": "médio",
        })

    return sorted(opportunities, key=lambda x: x.get("score", 0), reverse=True)[:10]


def run(state: dict) -> dict:
    from graph_engine.tools.supabase_tools import insert_agent_event

    findings = []
    decisions = []

    opportunities = _aggregate_signals()

    findings.append({
        "agent": "opportunity_scout",
        "opportunities_found": len(opportunities),
        "top_opportunity": opportunities[0]["title"] if opportunities else "Nenhuma",
    })

    if opportunities:
        try:
            insert_agent_event(
                event_type="opportunities_mapped",
                source="opportunity_scout",
                payload={"opportunities": opportunities, "count": len(opportunities)},
                priority="medium",
            )
            decisions.append(f"{len(opportunities)} oportunidades mapeadas e enviadas ao evolution_agent")
        except Exception as exc:
            logger.error("opportunity_scout: erro ao inserir evento: %s", exc)

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "opportunities": opportunities,
            "opportunity_scout_run": datetime.now(timezone.utc).isoformat(),
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

"""Backend Agent — auditoria de microsserviços FastAPI. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event, query_app_logs
from graph_engine.tools.http_tools import check_all_services


_SLOW_THRESHOLD_MS = 1500


def run(state: dict) -> dict:
    findings = []
    services = check_all_services()

    for svc in services:
        latency = svc.get("latency_ms", 0)
        if latency > _SLOW_THRESHOLD_MS:
            insert_improvement_proposal(
                source_agent="backend_agent",
                proposal_type="code_fix",
                title=f"Serviço {svc['service']} com latência alta ({latency}ms)",
                description=f"O serviço {svc['service']} está respondendo em {latency}ms (threshold: {_SLOW_THRESHOLD_MS}ms).",
                proposed_action="Investigar queries lentas no banco, adicionar índices se necessário, ou verificar conexões externas.",
                priority="medium",
                estimated_effort="hours",
                risk="low",
                auto_implementable=False,
                source_findings=[svc],
            )
            findings.append({"type": "slow_service", "service": svc["service"], "latency_ms": latency})

    error_logs = query_app_logs(level="error", since_minutes=60, limit=100)
    by_module: dict[str, int] = {}
    for log_entry in error_logs:
        module = log_entry.get("module", "unknown")
        by_module[module] = by_module.get(module, 0) + 1

    for module, count in by_module.items():
        if count >= 10:
            findings.append({"type": "module_errors", "module": module, "count": count})
            log_event("warning", "backend_agent", f"Módulo {module} com {count} erros na última hora")

    return {"findings": findings, "context": {"backend_agent_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

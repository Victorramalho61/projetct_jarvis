"""API Agent — valida contratos e consistência das APIs. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event, query_app_logs
from graph_engine.tools.http_tools import call_internal_service, check_all_services


_EXPECTED_ENDPOINTS = {
    "core": ["/health", "/ready", "/api/auth/me"],
    "monitoring": ["/health", "/ready"],
    "freshservice": ["/health", "/ready"],
    "moneypenny": ["/health", "/ready"],
    "agents": ["/health", "/ready"],
    "expenses": ["/health", "/ready"],
}


def run(state: dict) -> dict:
    findings = []

    for service, endpoints in _EXPECTED_ENDPOINTS.items():
        for endpoint in endpoints:
            result = call_internal_service(service, endpoint, method="GET")
            if not result.get("ok") and result.get("status_code") not in [200, 401, 403]:
                findings.append({
                    "type": "endpoint_unavailable",
                    "service": service,
                    "endpoint": endpoint,
                    "status_code": result.get("status_code"),
                })
                log_event("warning", "api_agent", f"Endpoint {service}{endpoint} retornou {result.get('status_code')}")

    # Verifica erros 5xx nos logs (indica contrato quebrado)
    error_logs = query_app_logs(level="error", since_minutes=1440, limit=200)
    server_errors = [l for l in error_logs if "500" in ((l.get("message") or "") + (l.get("detail") or ""))]
    if len(server_errors) > 5:
        insert_improvement_proposal(
            source_agent="api_agent",
            proposal_type="code_fix",
            title=f"{len(server_errors)} erros 500 detectados nas APIs em 24h",
            description="Erros internos de servidor podem indicar exceções não tratadas ou regressões.",
            proposed_action="Revisar handlers de erro nos microsserviços e adicionar tratamento adequado de exceções.",
            priority="high",
            estimated_effort="hours",
            risk="medium",
            auto_implementable=False,
            source_findings=server_errors[:5],
        )
        findings.append({"type": "server_errors_5xx", "count": len(server_errors)})

    return {"findings": findings, "context": {"api_agent_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

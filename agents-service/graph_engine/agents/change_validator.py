"""Change Validator — valida mudanças implementadas. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import log_event, query_change_requests, update_change_request
from graph_engine.tools.http_tools import check_all_services


def run(state: dict) -> dict:
    findings = []
    decisions = []

    # Busca RFCs em estado 'implementing' para validar
    implementing = query_change_requests(status="implementing")
    services_status = check_all_services()
    all_up = all(s["status"] == "up" for s in services_status)
    down_services = [s["service"] for s in services_status if s["status"] != "up"]

    for cr in implementing:
        if all_up:
            update_change_request(cr["id"], "validated")
            log_event("info", "change_validator", f"RFC validada com sucesso: {cr['title']}")
            decisions.append({"action": "validate_change", "id": cr["id"], "status": "validated"})
        else:
            log_event("error", "change_validator", f"RFC '{cr['title']}' — validação falhou, serviços indisponíveis: {down_services}")
            findings.append({
                "type": "change_validation_failed",
                "change_request_id": cr["id"],
                "title": cr["title"],
                "down_services": down_services,
            })

    return {"findings": findings, "decisions": decisions, "context": {"change_validator_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

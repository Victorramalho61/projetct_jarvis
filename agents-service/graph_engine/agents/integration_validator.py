"""Integration Validator — valida integrações externas. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_quality_metric, log_event, query_app_logs
from graph_engine.tools.http_tools import check_health, call_internal_service


def run(state: dict) -> dict:
    findings = []
    now = datetime.now(timezone.utc).isoformat()

    # 1. Freshservice
    fs = check_health("freshservice")
    insert_quality_metric("integration_freshservice", 1.0 if fs["status"] == "up" else 0.0, "boolean", "freshservice")
    if fs["status"] != "up":
        findings.append({"type": "integration_down", "integration": "freshservice", "detail": fs})
        log_event("error", "integration_validator", "Freshservice indisponível", str(fs))

    # 2. Microsoft 365 / Moneypenny
    mp = check_health("moneypenny")
    insert_quality_metric("integration_moneypenny", 1.0 if mp["status"] == "up" else 0.0, "boolean", "moneypenny")
    if mp["status"] != "up":
        findings.append({"type": "integration_down", "integration": "moneypenny_microsoft365", "detail": mp})

    # 3. Expenses / SQL Server Benner (via expenses-service health)
    exp = check_health("expenses")
    insert_quality_metric("integration_expenses_erp", 1.0 if exp["status"] == "up" else 0.0, "boolean", "expenses")
    if exp["status"] != "up":
        findings.append({"type": "integration_down", "integration": "expenses_sql_server", "detail": exp})
        log_event("warning", "integration_validator", "Expenses service indisponível (possível falha SQL Server Benner)")

    # 4. Core / Auth
    core = check_health("core")
    insert_quality_metric("integration_core_auth", 1.0 if core["status"] == "up" else 0.0, "boolean", "core")
    if core["status"] != "up":
        findings.append({"type": "integration_down", "integration": "core_auth", "detail": core})
        log_event("error", "integration_validator", "Core service (auth) indisponível — impacto crítico")

    # 5. Verifica logs de erro de integração nos últimas 24h
    error_logs = query_app_logs(level="error", since_minutes=1440, limit=200)
    integration_errors = [l for l in error_logs if any(k in ((l.get("message") or "") + (l.get("detail") or "")).lower() for k in ["timeout", "connection", "refused", "ssl", "403", "401", "502"])]
    if len(integration_errors) > 10:
        findings.append({"type": "high_integration_errors", "count": len(integration_errors), "sample": integration_errors[:3]})

    return {"findings": findings, "context": {"integration_validator_ran_at": now}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

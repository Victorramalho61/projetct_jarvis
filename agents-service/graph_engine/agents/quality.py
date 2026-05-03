"""Quality Agent — mede métricas de qualidade do sistema. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_quality_metric, log_event, query_app_logs, query_system_checks, query_monitored_systems
from graph_engine.tools.http_tools import check_all_services, get_metrics


def run(state: dict) -> dict:
    findings = []
    services_status = check_all_services()

    # Métricas de disponibilidade por serviço
    for svc in services_status:
        status_val = 1.0 if svc["status"] == "up" else 0.0
        insert_quality_metric("availability", status_val, "boolean", svc["service"], {"http_status": svc.get("http_status")})
        if svc.get("latency_ms"):
            insert_quality_metric("latency_ms", svc["latency_ms"], "ms", svc["service"])
        if svc["status"] != "up":
            findings.append({"type": "service_down", "service": svc["service"], "status": svc["status"]})

    # Métricas de erro nos logs (últimas 24h)
    error_logs = query_app_logs(level="error", since_minutes=1440, limit=1000)
    warn_logs = query_app_logs(level="warning", since_minutes=1440, limit=1000)
    insert_quality_metric("error_rate_24h", len(error_logs), "count", "all")
    insert_quality_metric("warning_rate_24h", len(warn_logs), "count", "all")

    if len(error_logs) > 50:
        findings.append({"type": "high_error_rate", "count": len(error_logs), "period": "24h"})

    # Métricas do monitor-agent (CPU/RAM/disco)
    server_metrics = get_metrics()
    if "error" not in server_metrics:
        for key in ["cpu_percent", "memory_percent", "disk_percent"]:
            val = server_metrics.get(key)
            if val is not None:
                insert_quality_metric(key, float(val), "%", "server")
                if float(val) > 85:
                    findings.append({"type": f"high_{key}", "value": val, "threshold": 85})

    # Sistemas monitorados com consecutive_down_count > 0
    systems = query_monitored_systems()
    systems_down = [s for s in systems if s.get("consecutive_down_count", 0) > 0]
    insert_quality_metric("systems_degraded", len(systems_down), "count", "monitoring")
    if systems_down:
        findings.append({"type": "systems_degraded", "count": len(systems_down), "systems": [s["name"] for s in systems_down]})

    log_event("info", "quality_agent", f"Métricas coletadas — {len(findings)} anomalias detectadas")
    return {"findings": findings, "context": {"quality_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

"""Quality Validator — valida métricas contra SLOs definidos. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import log_event, query_quality_metrics

# SLOs (Service Level Objectives)
_SLOS = {
    "availability": {"min": 0.99, "unit": "boolean"},       # 99% uptime
    "latency_ms": {"max": 2000, "unit": "ms"},              # máx 2s
    "error_rate_24h": {"max": 100, "unit": "count"},        # máx 100 erros/dia
    "cpu_percent": {"max": 85, "unit": "%"},
    "memory_percent": {"max": 85, "unit": "%"},
    "disk_percent": {"max": 80, "unit": "%"},
}


def run(state: dict) -> dict:
    findings = []
    violations = []

    for metric_name, slo in _SLOS.items():
        metrics = query_quality_metrics(metric_name=metric_name, since_hours=24, limit=50)
        if not metrics:
            continue
        values = [float(m["metric_value"]) for m in metrics]
        avg_val = sum(values) / len(values)

        breached = False
        if "min" in slo and avg_val < slo["min"]:
            breached = True
            violations.append({"metric": metric_name, "slo": f">= {slo['min']}", "actual": round(avg_val, 4)})
        if "max" in slo and avg_val > slo["max"]:
            breached = True
            violations.append({"metric": metric_name, "slo": f"<= {slo['max']}", "actual": round(avg_val, 2)})

        if breached:
            log_event("warning", "quality_validator", f"SLO violado: {metric_name} = {avg_val:.2f} (SLO: {slo})")

    if violations:
        findings.append({"type": "slo_violations", "count": len(violations), "violations": violations})

    return {
        "findings": findings,
        "context": {"quality_validator_ran_at": datetime.now(timezone.utc).isoformat(), "slo_violations": len(violations)},
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

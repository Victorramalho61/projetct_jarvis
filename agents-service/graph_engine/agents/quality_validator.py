"""Quality Validator — valida SLOs e propostas pós-implementação."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import (
    log_event,
    query_quality_metrics,
    get_pending_messages,
    mark_message_processed,
    send_agent_message,
)

# SLOs (Service Level Objectives)
_SLOS = {
    "availability": {"min": 0.99, "unit": "boolean"},
    "latency_ms": {"max": 2000, "unit": "ms"},
    "error_rate_24h": {"max": 100, "unit": "count"},
    "cpu_percent": {"max": 85, "unit": "%"},
    "memory_percent": {"max": 85, "unit": "%"},
    "disk_percent": {"max": 80, "unit": "%"},
}


def _validate_slos() -> list[dict]:
    violations = []
    for metric_name, slo in _SLOS.items():
        metrics = query_quality_metrics(metric_name=metric_name, since_hours=24, limit=50)
        if not metrics:
            continue
        values = [float(m["metric_value"]) for m in metrics]
        avg_val = sum(values) / len(values)
        if "min" in slo and avg_val < slo["min"]:
            violations.append({"metric": metric_name, "slo": f">= {slo['min']}", "actual": round(avg_val, 4)})
            log_event("warning", "quality_validator", f"SLO violado: {metric_name} = {avg_val:.2f}")
        if "max" in slo and avg_val > slo["max"]:
            violations.append({"metric": metric_name, "slo": f"<= {slo['max']}", "actual": round(avg_val, 2)})
            log_event("warning", "quality_validator", f"SLO violado: {metric_name} = {avg_val:.2f}")
    return violations


def _process_qa_requests(findings: list) -> int:
    """Processa pedidos de QA pós-implementação vindos do proposal_supervisor."""
    try:
        from db import get_supabase
        db = get_supabase()
        messages = get_pending_messages("quality_validator")
        qa_msgs = [m for m in messages if m.get("context", {}).get("qa_required")]
        if not qa_msgs:
            return 0

        # Busca proposals recentemente aplicadas
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        applied = db.table("improvement_proposals").select(
            "id,title,proposal_type,applied_at,source_agent"
        ).eq("validation_status", "applied").gt("applied_at", cutoff).execute().data or []

        applied_map = {p["id"]: p for p in applied}

        for msg in qa_msgs:
            pid = msg.get("context", {}).get("proposal_id", "")
            target = msg.get("context", {}).get("target_agent", "")
            title = ""
            if pid in applied_map:
                title = applied_map[pid].get("title", "")
                status_ok = True
            else:
                # Ainda em auto_implementing — verifica se está executando
                row = db.table("improvement_proposals").select("validation_status,title").eq("id", pid).limit(1).execute().data
                current_status = row[0].get("validation_status", "unknown") if row else "unknown"
                title = row[0].get("title", "") if row else ""
                status_ok = current_status in ("applied", "auto_implementing")

            findings.append({
                "type": "post_implementation_qa",
                "proposal_id": pid,
                "proposal_title": title,
                "target_agent": target,
                "qa_status": "applied_ok" if (pid in applied_map) else "pending_implementation",
            })

            try:
                mark_message_processed(msg["id"])
            except Exception:
                pass

        # Reporta resultado ao CTO
        if qa_msgs:
            applied_count = sum(1 for f in findings if f.get("type") == "post_implementation_qa" and f.get("qa_status") == "applied_ok")
            pending_count = len(qa_msgs) - applied_count
            send_agent_message(
                from_agent="quality_validator",
                to_agent="cto",
                message=(
                    f"QA PÓS-IMPLEMENTAÇÃO: {len(qa_msgs)} propostas verificadas.\n"
                    f"✅ Aplicadas: {applied_count} | ⏳ Em implementação: {pending_count}\n"
                    "SLOs verificados na janela de 24h."
                ),
                context={"qa_results": findings, "slos_checked": list(_SLOS.keys())},
            )

        return len(qa_msgs)
    except Exception as exc:
        log_event("warning", "quality_validator", f"Erro ao processar QA requests: {exc}")
        return 0


def run(state: dict) -> dict:
    findings = []

    violations = _validate_slos()
    if violations:
        findings.append({"type": "slo_violations", "count": len(violations), "violations": violations})

    qa_count = _process_qa_requests(findings)

    return {
        "findings": findings,
        "context": {
            "quality_validator_ran_at": datetime.now(timezone.utc).isoformat(),
            "slo_violations": len(violations),
            "qa_requests_processed": qa_count,
        },
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

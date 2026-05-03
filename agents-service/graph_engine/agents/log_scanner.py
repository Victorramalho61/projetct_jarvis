"""Log Scanner — agrupa erros por padrão e detecta spikes. Motor: Python puro."""
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from graph_engine.tools.supabase_tools import log_event, query_app_logs, send_agent_message
from graph_engine.tools.docker_tools import get_container_logs, list_containers


_SPIKE_THRESHOLD = 5  # ocorrências do mesmo erro nas últimas 2h para acionar alerta


def _normalize(message: str) -> str:
    """Remove UUIDs, números e paths para agrupar mensagens similares."""
    msg = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", message, flags=re.I)
    msg = re.sub(r"\b\d+\b", "<n>", msg)
    msg = re.sub(r"/[^\s]+", "<path>", msg)
    return msg[:80]


def run(state: dict) -> dict:
    logs = query_app_logs(level="error", limit=500, since_minutes=120)
    warn_logs = query_app_logs(level="warning", limit=200, since_minutes=120)
    all_logs = logs + warn_logs

    # Agrupa por (module, normalized_message)
    groups: dict[tuple, list] = defaultdict(list)
    for entry in all_logs:
        key = (entry.get("module", "unknown"), _normalize(entry.get("message", "")))
        groups[key].append(entry)

    findings = []
    for (module, pattern), entries in groups.items():
        count = len(entries)
        severity = "error" if entries[0].get("level") == "error" else "warning"
        if count >= _SPIKE_THRESHOLD or severity == "error":
            findings.append({
                "pattern": pattern,
                "module": module,
                "count": count,
                "severity": severity,
                "sample_logs": entries[:3],
                "first_seen": entries[-1].get("created_at"),
                "last_seen": entries[0].get("created_at"),
            })

    # Varredura complementar: logs Docker dos containers principais
    containers = list_containers()
    docker_findings = []
    for c in containers:
        if isinstance(c, dict) and "error" not in c:
            docker_logs = get_container_logs(c["name"], lines=50, since_minutes=60)
            error_lines = [l for l in docker_logs.splitlines() if "error" in l.lower() or "fatal" in l.lower() or "exception" in l.lower()]
            if len(error_lines) >= 3:
                docker_findings.append({
                    "pattern": f"Erros no container {c['name']}",
                    "module": f"docker:{c['name']}",
                    "count": len(error_lines),
                    "severity": "error",
                    "sample_logs": [{"message": l} for l in error_lines[:3]],
                })

    all_findings = findings + docker_findings

    if all_findings:
        log_event("warning", "log_scanner", f"{len(all_findings)} padrões de erro detectados", f"Spike threshold: {_SPIKE_THRESHOLD}")
        # Notifica CTO para acionar log_improver
        send_agent_message(
            from_agent="log_scanner",
            to_agent="cto",
            content={"trigger": "log_findings", "findings": all_findings, "count": len(all_findings)},
        )

    return {"findings": all_findings, "context": {"log_scanner_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

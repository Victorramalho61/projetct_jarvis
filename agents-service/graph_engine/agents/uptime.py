"""Uptime Guardian — monitora containers e age em falhas (sem deploy). Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_change_request, log_event
from graph_engine.tools.docker_tools import get_container_stats, list_containers, restart_container
from graph_engine.tools.http_tools import check_all_services

# Containers que NUNCA devem ser reiniciados automaticamente (requerem rebuild)
_NO_AUTO_RESTART = {"jarvis-frontend-1", "jarvis-agents-service-1"}

# Limite de uso de memória para alertar
_MEM_ALERT_THRESHOLD = 90.0


def run(state: dict) -> dict:
    findings = []
    decisions = []

    # 1. Verifica serviços via HTTP
    services = check_all_services()
    for svc in services:
        if svc["status"] == "down":
            findings.append({"type": "service_down", "service": svc["service"]})

    # 2. Verifica containers Docker
    all_containers = list_containers(status="running")
    exited = list_containers(status="exited")

    for c in exited:
        if isinstance(c, dict) and "error" not in c:
            name = c["name"]
            if name not in _NO_AUTO_RESTART:
                result = restart_container(name)
                if result.get("success"):
                    log_event("warning", "uptime_guardian", f"Container {name} reiniciado automaticamente")
                    decisions.append({"action": "restart", "container": name, "success": True})
                else:
                    log_event("error", "uptime_guardian", f"Falha ao reiniciar {name}: {result.get('error')}")
                    # Cria RFC para intervenção humana
                    insert_change_request(
                        title=f"Container {name} parado — requer atenção",
                        description=f"Container {name} está parado e não foi possível reiniciar automaticamente: {result.get('error')}",
                        change_type="emergency",
                        priority="critical",
                        requested_by="uptime_guardian",
                    )
                    findings.append({"type": "container_down_manual_action", "container": name})
            else:
                log_event("warning", "uptime_guardian", f"Container {name} parado — requer rebuild (intervenção humana)")
                insert_change_request(
                    title=f"Container {name} parado — requer rebuild",
                    description=f"Container {name} está parado. Requer docker compose up --build (não foi reiniciado automaticamente).",
                    change_type="emergency",
                    priority="critical",
                    requested_by="uptime_guardian",
                )
                findings.append({"type": "container_needs_rebuild", "container": name})

    # 3. Verifica uso de memória
    for c in all_containers:
        if isinstance(c, dict) and "error" not in c:
            stats = get_container_stats(c["name"])
            if stats.get("memory_percent", 0) > _MEM_ALERT_THRESHOLD:
                log_event("warning", "uptime_guardian", f"Container {c['name']} com {stats['memory_percent']}% de memória")
                findings.append({"type": "high_memory", "container": c["name"], "memory_percent": stats["memory_percent"]})

    return {"findings": findings, "decisions": decisions, "context": {"uptime_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

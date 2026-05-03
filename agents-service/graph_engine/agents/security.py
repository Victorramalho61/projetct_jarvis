"""Security Agent — scans de vulnerabilidade e monitoramento de intrusão. Motor: Python puro."""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from graph_engine.tools.supabase_tools import insert_security_alert, log_event, query_app_logs
from graph_engine.tools.docker_tools import inspect_container, list_containers, list_networks


_BRUTE_FORCE_THRESHOLD = 10  # tentativas de login falhadas em 30min


def _check_brute_force(logs: list[dict]) -> list[dict]:
    alerts = []
    failed = [l for l in logs if "login" in l.get("message", "").lower() and l.get("level") == "error"]
    by_user: Counter = Counter(l.get("detail", "") for l in failed)
    for user, count in by_user.items():
        if count >= _BRUTE_FORCE_THRESHOLD:
            alert = insert_security_alert("high", "brute_force", f"Tentativas de login excessivas: {count}x", user)
            alerts.append(alert)
    return alerts


def _check_container_configs(containers: list[dict]) -> list[dict]:
    alerts = []
    for c in containers:
        if isinstance(c, dict) and "error" not in c:
            details = inspect_container(c["name"])
            restart_count = details.get("restart_count", 0)
            if restart_count >= 3:
                alert = insert_security_alert(
                    "medium", "stability",
                    f"Container {c['name']} reiniciou {restart_count}x — possível crash loop",
                    c["name"],
                )
                alerts.append(alert)
            # Verifica se container está rodando como root (mem_limit=0 indica sem limite)
            if details.get("mem_limit", -1) == 0:
                alert = insert_security_alert(
                    "low", "resource_limit",
                    f"Container {c['name']} sem limite de memória configurado",
                    c["name"],
                )
                alerts.append(alert)
    return alerts


def _check_network_isolation(networks: list[dict]) -> list[dict]:
    alerts = []
    for net in networks:
        # Alerta se rede interna tem muitos containers (pode indicar exposição indevida)
        if len(net.get("containers", [])) > 15:
            alert = insert_security_alert(
                "low", "network",
                f"Rede {net['name']} possui {len(net['containers'])} containers — verificar isolamento",
                net["name"],
            )
            alerts.append(alert)
    return alerts


def run(state: dict) -> dict:
    logs = query_app_logs(since_minutes=1440)  # últimas 24h
    containers = list_containers()
    networks = list_networks()

    all_alerts = []
    all_alerts.extend(_check_brute_force(logs))
    all_alerts.extend(_check_container_configs(containers))
    all_alerts.extend(_check_network_isolation(networks))

    # Verifica logs por padrões de SQL injection / path traversal
    suspicious_patterns = [r"\.\./", r"union\s+select", r"drop\s+table", r";\s*--"]
    suspicious_logs = []
    for log_entry in logs:
        detail = (log_entry.get("detail") or "") + (log_entry.get("message") or "")
        for pattern in suspicious_patterns:
            if re.search(pattern, detail, re.I):
                suspicious_logs.append(log_entry)
                break

    if suspicious_logs:
        alert = insert_security_alert("critical", "injection_attempt", f"{len(suspicious_logs)} requisições suspeitas detectadas nos logs")
        all_alerts.append(alert)
        log_event("error", "security_agent", "Padrões de injeção detectados", f"{len(suspicious_logs)} ocorrências")

    findings = [{"type": "security_alert", "alert": a} for a in all_alerts if a]
    return {"findings": findings, "context": {"security_ran_at": datetime.now(timezone.utc).isoformat(), "alerts_created": len(all_alerts)}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

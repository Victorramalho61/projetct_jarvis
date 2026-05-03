"""Ferramentas HTTP para chamadas inter-servi�o autenticadas."""
import logging

import httpx
import jwt

from db import get_settings

log = logging.getLogger(__name__)

SERVICES = {
    "core": "http://core-service:8001",
    "monitoring": "http://monitoring-service:8002",
    "freshservice": "http://freshservice-service:8003",
    "moneypenny": "http://moneypenny-service:8004",
    "agents": "http://agents-service:8005",
    "expenses": "http://expenses-service:8006",
}


def _service_token() -> str:
    s = get_settings()
    return jwt.encode({"id": "cto-agent", "role": "admin", "active": True}, s.jwt_secret, algorithm="HS256")


def check_health(service: str) -> dict:
    base = SERVICES.get(service, service)
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        return {"service": service, "status": "up" if r.is_success else "down", "http_status": r.status_code, "latency_ms": int(r.elapsed.total_seconds() * 1000)}
    except Exception as e:
        return {"service": service, "status": "down", "error": str(e)}


def check_all_services() -> list[dict]:
    return [check_health(s) for s in SERVICES]


def call_internal_service(service: str, path: str, method: str = "GET", body: dict | None = None) -> dict:
    base = SERVICES.get(service, service)
    token = _service_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        r = httpx.request(method, f"{base}{path}", headers=headers, json=body, timeout=30)
        return {"status_code": r.status_code, "ok": r.is_success, "data": r.json() if r.content else {}}
    except Exception as e:
        log.warning("call_internal_service(%s %s%s) error: %s", method, service, path, e)
        return {"ok": False, "error": str(e)}


def get_metrics(monitor_agent_url: str = "http://monitor-agent:9100") -> dict:
    try:
        r = httpx.get(f"{monitor_agent_url}/metrics", timeout=5)
        return r.json() if r.is_success else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

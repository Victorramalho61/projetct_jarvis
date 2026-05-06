"""Ferramentas HTTP para chamadas inter-serviço autenticadas."""
import logging
import threading

import httpx
import jwt
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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

# ── Circuit breakers por serviço ────────────────────────────────────────────────
# Evita cascata: se freshservice estiver com falhas, não propaga para outros agentes.
_cb_lock = threading.Lock()
_service_cbs: dict = {}


def _get_service_cb(service: str):
    from graph_engine.resilience import CircuitBreaker
    with _cb_lock:
        if service not in _service_cbs:
            _service_cbs[service] = CircuitBreaker(
                f"http_{service}", failure_threshold=4, recovery_timeout_s=120
            )
        return _service_cbs[service]


def _service_token() -> str:
    s = get_settings()
    return jwt.encode({"id": "cto-agent", "role": "admin", "active": True}, s.jwt_secret, algorithm="HS256")


def check_health(service: str) -> dict:
    base = SERVICES.get(service, service)
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        return {
            "service": service,
            "status": "up" if r.is_success else "down",
            "http_status": r.status_code,
            "latency_ms": int(r.elapsed.total_seconds() * 1000),
        }
    except Exception as e:
        return {"service": service, "status": "down", "error": str(e)}


def check_all_services() -> list[dict]:
    results = [check_health(s) for s in SERVICES]
    # Anota estado dos circuit breakers no resultado
    for r in results:
        cb = _service_cbs.get(r["service"])
        if cb:
            r["circuit_breaker"] = cb.metrics()["state"]
    return results


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    before_sleep=lambda rs: log.warning(
        "HTTP retry %d/3 (erro: %s)", rs.attempt_number, rs.outcome.exception()
    ),
)
def _do_request(method: str, url: str, headers: dict, body: dict | None, timeout: int) -> httpx.Response:
    return httpx.request(method, url, headers=headers, json=body, timeout=timeout)


def call_internal_service(service: str, path: str, method: str = "GET", body: dict | None = None, timeout: int = 30) -> dict:
    from graph_engine.resilience import CircuitOpenError
    base = SERVICES.get(service, service)
    cb = _get_service_cb(service)
    token = _service_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{base}{path}"
    try:
        def _call():
            return _do_request(method, url, headers, body, timeout)
        r = cb.call(_call)
        return {"status_code": r.status_code, "ok": r.is_success, "data": r.json() if r.content else {}}
    except CircuitOpenError as e:
        log.warning("call_internal_service(%s): circuit OPEN — %s", service, e)
        return {"ok": False, "error": f"Serviço {service} indisponível (circuit open)", "circuit_open": True}
    except Exception as e:
        log.warning("call_internal_service(%s %s%s) error: %s", method, service, path, e)
        return {"ok": False, "error": str(e)}


def get_metrics(monitor_agent_url: str = "http://monitor-agent:9100") -> dict:
    try:
        r = httpx.get(f"{monitor_agent_url}/metrics", timeout=5)
        return r.json() if r.is_success else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

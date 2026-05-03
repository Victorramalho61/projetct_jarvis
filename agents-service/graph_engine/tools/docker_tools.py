"""Ferramentas Docker read-only para agentes LangGraph."""
import logging

log = logging.getLogger(__name__)

try:
    import docker as docker_sdk
    _client = docker_sdk.from_env()
except Exception:
    _client = None


def _check_client() -> bool:
    return _client is not None


def list_containers(status: str = "running") -> list[dict]:
    if not _check_client():
        return [{"error": "Docker socket n�o dispon�vel"}]
    try:
        containers = _client.containers.list(filters={"status": status})
        return [
            {
                "id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
            }
            for c in containers
        ]
    except Exception as e:
        log.warning("list_containers error: %s", e)
        return []


def get_container_logs(container_name: str, lines: int = 100, since_minutes: int = 60) -> str:
    if not _check_client():
        return "Docker socket n�o dispon�vel"
    try:
        from datetime import datetime, timedelta, timezone
        since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        c = _client.containers.get(container_name)
        logs = c.logs(tail=lines, since=since, timestamps=True).decode("utf-8", errors="replace")
        return logs[-8000:] if len(logs) > 8000 else logs
    except Exception as e:
        log.warning("get_container_logs(%s) error: %s", container_name, e)
        return f"Erro ao obter logs: {e}"


def get_container_stats(container_name: str) -> dict:
    if not _check_client():
        return {"error": "Docker socket n�o dispon�vel"}
    try:
        c = _client.containers.get(container_name)
        stats = c.stats(stream=False)
        # Calcula percentual CPU
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        sys_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        num_cpus = stats["cpu_stats"].get("online_cpus", 1)
        cpu_pct = (cpu_delta / sys_delta) * num_cpus * 100.0 if sys_delta > 0 else 0.0
        # Mem�ria
        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_limit = stats["memory_stats"].get("limit", 1)
        mem_pct = (mem_usage / mem_limit) * 100.0
        return {
            "name": container_name,
            "cpu_percent": round(cpu_pct, 2),
            "memory_usage_mb": round(mem_usage / 1024 / 1024, 1),
            "memory_limit_mb": round(mem_limit / 1024 / 1024, 1),
            "memory_percent": round(mem_pct, 2),
        }
    except Exception as e:
        log.warning("get_container_stats(%s) error: %s", container_name, e)
        return {"error": str(e)}


def inspect_container(container_name: str) -> dict:
    if not _check_client():
        return {"error": "Docker socket n�o dispon�vel"}
    try:
        c = _client.containers.get(container_name)
        attrs = c.attrs
        return {
            "name": container_name,
            "status": attrs["State"]["Status"],
            "image": attrs["Config"]["Image"],
            "restart_count": attrs["RestartCount"],
            "mem_limit": attrs["HostConfig"].get("Memory", 0),
            "cpu_quota": attrs["HostConfig"].get("CpuQuota", 0),
            "env": [e for e in attrs["Config"].get("Env", []) if not any(k in e for k in ["KEY", "SECRET", "PASSWORD", "TOKEN"])],
        }
    except Exception as e:
        return {"error": str(e)}


def list_networks() -> list[dict]:
    if not _check_client():
        return []
    try:
        networks = _client.networks.list()
        return [
            {
                "id": n.short_id,
                "name": n.name,
                "driver": n.attrs.get("Driver"),
                "containers": list(n.attrs.get("Containers", {}).keys()),
            }
            for n in networks
            if n.name not in ["bridge", "host", "none"]
        ]
    except Exception as e:
        log.warning("list_networks error: %s", e)
        return []


def restart_container(container_name: str) -> dict:
    """Reinicia um container (n�o faz rebuild � apenas restart)."""
    if not _check_client():
        return {"error": "Docker socket n�o dispon�vel", "success": False}
    try:
        c = _client.containers.get(container_name)
        c.restart(timeout=30)
        return {"success": True, "container": container_name, "action": "restart"}
    except Exception as e:
        log.warning("restart_container(%s) error: %s", container_name, e)
        return {"success": False, "error": str(e)}

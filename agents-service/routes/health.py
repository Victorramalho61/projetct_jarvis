import time

import httpx
from fastapi import APIRouter

from db import get_settings

router = APIRouter()
_START = time.monotonic()
_SERVICE = "agents-service"
_VERSION = "1.0.0"


@router.get("/health")
def health():
    return {"status": "ok", "service": _SERVICE, "version": _VERSION,
            "uptime_seconds": round(time.monotonic() - _START)}


@router.get("/ready")
async def ready():
    checks: dict = {}
    s = get_settings()

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.supabase_url}/rest/v1/",
                            headers={"apikey": s.supabase_key})
        checks["db"] = {"status": "ok" if r.status_code < 500 else "error",
                        "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        checks["db"] = {"status": "error", "detail": str(e)}

    overall = "ok" if all(v["status"] == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "service": _SERVICE, "checks": checks}


@router.get("/health/detailed")
async def health_detailed():
    """Health check expandido: status por módulo, dependências externas e circuit breakers."""
    import asyncio
    from graph_engine.tools.http_tools import check_all_services, _service_cbs

    s = get_settings()
    checks: dict = {}

    # Supabase / banco
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.supabase_url}/rest/v1/", headers={"apikey": s.supabase_key})
        checks["supabase"] = {
            "status": "ok" if r.status_code < 500 else "degraded",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except Exception as e:
        checks["supabase"] = {"status": "error", "detail": str(e)[:120]}

    # Serviços internos (via circuit breaker)
    try:
        svc_health = await asyncio.get_event_loop().run_in_executor(None, check_all_services)
        checks["services"] = {s["service"]: s for s in svc_health}
    except Exception as e:
        checks["services"] = {"error": str(e)[:120]}

    # Circuit breakers ativos
    cb_status = {name: cb.metrics() for name, cb in _service_cbs.items()}
    open_cbs = [n for n, m in cb_status.items() if m["state"] != "closed"]

    # LLM router status
    try:
        from graph_engine.llm import get_router_status
        checks["llm_providers"] = get_router_status()
    except Exception:
        checks["llm_providers"] = []

    # Pipeline scheduler — últimas execuções
    try:
        from db import get_supabase
        db = get_supabase()
        runs = (
            db.table("governance_reports")
            .select("pipeline,created_at,status")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data or []
        )
        seen: dict = {}
        for r in runs:
            p = r.get("pipeline", "unknown")
            if p not in seen:
                seen[p] = {"last_run": r.get("created_at"), "status": r.get("status")}
        checks["pipelines"] = seen
    except Exception:
        checks["pipelines"] = {}

    overall = "ok"
    if open_cbs:
        overall = "degraded"
    if checks.get("supabase", {}).get("status") == "error":
        overall = "error"

    return {
        "status": overall,
        "service": _SERVICE,
        "uptime_seconds": round(time.monotonic() - _START),
        "checks": checks,
        "circuit_breakers": cb_status,
        "open_circuit_breakers": open_cbs,
    }

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from db import get_settings, get_supabase
from services.app_logger import log_event

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    status: str
    latency_ms: int | None = None
    http_status: int | None = None
    detail: str | None = None
    metrics: dict | None = None


async def check_http(system: dict) -> CheckResult:
    cfg = system.get("config") or {}
    timeout = float(cfg.get("timeout_seconds", 5))
    expected = int(cfg.get("expected_status", 200))
    method = str(cfg.get("method", "GET")).upper()
    url = system.get("url", "")

    if not url:
        return CheckResult("unknown", detail="URL não configurada")

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await getattr(client, method.lower())(url)
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code == expected:
            return CheckResult("up", latency_ms, resp.status_code)
        elif resp.status_code < 500:
            return CheckResult("degraded", latency_ms, resp.status_code,
                               f"Status inesperado: {resp.status_code}")
        else:
            return CheckResult("down", latency_ms, resp.status_code,
                               f"Erro servidor: {resp.status_code}")
    except httpx.TimeoutException:
        return CheckResult("down", int((time.monotonic() - t0) * 1000),
                           detail="Timeout")
    except Exception as exc:
        return CheckResult("down", detail=f"{type(exc).__name__}: {exc}")


async def check_evolution(system: dict) -> CheckResult:
    s = get_settings()
    cfg = system.get("config") or {}
    instance = cfg.get("instance_name") or s.whatsapp_instance

    if not instance or not s.whatsapp_api_url:
        return CheckResult("unknown", detail="Evolution API não configurada nas settings")

    url = f"{s.whatsapp_api_url.rstrip('/')}/instance/connectionState/{instance}"
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"apikey": s.whatsapp_api_key})
        latency_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            return CheckResult("down", latency_ms, resp.status_code,
                               f"HTTP {resp.status_code}")

        data = resp.json()
        state = (data.get("instance") or {}).get("state", "unknown")

        if state == "open":
            return CheckResult("up", latency_ms, 200, f"state={state}")
        elif state in ("connecting", "qrcode"):
            return CheckResult("degraded", latency_ms, 200, f"state={state}")
        else:
            return CheckResult("down", latency_ms, 200, f"state={state}")
    except httpx.ReadTimeout:
        return CheckResult("degraded", detail="ReadTimeout — API lenta mas provavelmente ativa")
    except Exception as exc:
        return CheckResult("down", detail=f"{type(exc).__name__}: {exc}")


async def check_metrics(system: dict) -> CheckResult:
    s = get_settings()
    url = f"{s.monitor_agent_url.rstrip('/')}/metrics"
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        latency_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            return CheckResult("down", latency_ms, resp.status_code,
                               f"HTTP {resp.status_code}")

        data = resp.json()
        status = data.get("status", "unknown")
        return CheckResult(status, latency_ms, 200, metrics=data)
    except Exception as exc:
        return CheckResult("down", detail=f"{type(exc).__name__}: {exc}")


async def check_custom(system: dict) -> CheckResult:
    cfg = system.get("config") or {}
    url = cfg.get("endpoint") or system.get("url", "")
    headers = cfg.get("headers") or {}
    body = cfg.get("body") or {}
    timeout = float(cfg.get("timeout_seconds", 5))

    if not url:
        return CheckResult("unknown", detail="Endpoint não configurado")

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if body:
                resp = await client.post(url, json=body, headers=headers)
            else:
                resp = await client.get(url, headers=headers)
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.is_success:
            return CheckResult("up", latency_ms, resp.status_code)
        return CheckResult("down", latency_ms, resp.status_code,
                           f"HTTP {resp.status_code}")
    except Exception as exc:
        return CheckResult("down", detail=f"{type(exc).__name__}: {exc}")


_CHECKERS = {
    "http":      check_http,
    "evolution": check_evolution,
    "metrics":   check_metrics,
    "custom":    check_custom,
}


async def _alert_system_down(system_name: str, detail: str | None) -> None:
    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_instance:
        return
    try:
        db = get_supabase()
        admins = db.table("profiles").select("whatsapp_phone").eq("role", "admin").eq("active", True).execute()
        phones = [r["whatsapp_phone"] for r in admins.data if r.get("whatsapp_phone")]
        if not phones:
            return

        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        text = f"🚨 *SISTEMA DOWN*: {system_name}\n📅 {now}"
        if detail:
            text += f"\n⚠️ {detail[:200]}"

        url = f"{s.whatsapp_api_url.rstrip('/')}/message/sendText/{s.whatsapp_instance}"
        timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for phone in phones:
                await client.post(url,
                                  json={"number": phone, "text": text},
                                  headers={"apikey": s.whatsapp_api_key})
    except Exception as exc:
        logger.warning("Falha ao enviar alerta WhatsApp para sistema DOWN: %s", exc)


async def run_check(system: dict, checked_by: str = "scheduler") -> dict:
    checker = _CHECKERS.get(system.get("system_type", ""))
    if not checker:
        return {}

    result = await checker(system)

    db = get_supabase()
    row = db.table("system_checks").insert({
        "system_id":   system["id"],
        "status":      result.status,
        "latency_ms":  result.latency_ms,
        "http_status": result.http_status,
        "detail":      result.detail,
        "metrics":     result.metrics,
        "checked_by":  checked_by,
        "checked_at":  datetime.now(timezone.utc).isoformat(),
    }).execute().data[0]

    if result.status == "down":
        log_event("error", "monitoring",
                  f"Sistema DOWN: {system['name']}",
                  detail=result.detail)
        await _alert_system_down(system["name"], result.detail)
    elif result.status == "degraded":
        log_event("warning", "monitoring",
                  f"Sistema DEGRADADO: {system['name']}",
                  detail=result.detail)

    return row


async def run_all_checks() -> None:
    db = get_supabase()
    systems = db.table("monitored_systems").select("*").eq("enabled", True).execute().data

    if not systems:
        return

    now = datetime.now(timezone.utc)
    system_ids = [s["id"] for s in systems]

    recent = db.table("system_checks") \
        .select("system_id,checked_at") \
        .in_("system_id", system_ids) \
        .order("checked_at", desc=True) \
        .limit(len(system_ids) * 3) \
        .execute().data

    last_check: dict[str, datetime] = {}
    for chk in recent:
        sid = chk["system_id"]
        if sid not in last_check:
            last_check[sid] = datetime.fromisoformat(
                chk["checked_at"].replace("Z", "+00:00"))

    to_check = [
        s for s in systems
        if (sid := s["id"]) not in last_check
        or (now - last_check[sid]).total_seconds() >= s.get("check_interval_minutes", 5) * 60
    ]

    if not to_check:
        return

    results = await asyncio.gather(
        *[run_check(s) for s in to_check],
        return_exceptions=True,
    )
    for s, r in zip(to_check, results):
        if isinstance(r, Exception):
            logger.error("Erro no check de '%s': %s", s["name"], r)

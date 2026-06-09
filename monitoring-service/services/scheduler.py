import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


async def _ensure_waha_session() -> None:
    """Garante que a sessão WAHA default esteja WORKING. Relança se STOPPED."""
    from db import get_settings
    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_api_key:
        return
    base = s.whatsapp_api_url.rstrip("/")
    headers = {"X-Api-Key": s.whatsapp_api_key}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{base}/api/sessions/default", headers=headers)
            if r.status_code != 200:
                return
            status = r.json().get("status", "")
            if status not in ("STOPPED", "FAILED"):
                return
            logger.warning("WAHA session status=%s — reiniciando automaticamente", status)
            await client.post(f"{base}/api/sessions/default/start",
                              headers=headers, json={})
            logger.info("WAHA session start enviado")
    except Exception as exc:
        logger.debug("_ensure_waha_session erro: %s", exc)


def start_scheduler() -> None:
    from services.monitor import run_all_checks
    from services.log_monitor import run_log_monitor, run_error_growth_check
    from services.retention import run_data_retention

    _scheduler.add_job(_ensure_waha_session, CronTrigger(minute="*/2"),
                       id="waha_session_watchdog", replace_existing=True,
                       max_instances=1, misfire_grace_time=30)

    _scheduler.add_job(run_all_checks, CronTrigger(minute="*/5"),
                       id="monitoring_checks", replace_existing=True,
                       max_instances=1, misfire_grace_time=60)

    # Diário às 8h BRT (11h UTC) — varre app_logs e abre issue no GitHub se houver erros recorrentes
    _scheduler.add_job(run_log_monitor, CronTrigger(hour=11, minute=0, timezone="UTC"),
                       id="log_monitor_daily", replace_existing=True,
                       max_instances=1, misfire_grace_time=300)

    # A cada 6h — detecta crescimento acelerado de erros por módulo (≥80% em 24h)
    _scheduler.add_job(run_error_growth_check, CronTrigger(hour="*/6", minute=0, timezone="UTC"),
                       id="error_growth_check", replace_existing=True,
                       max_instances=1, misfire_grace_time=300)

    # Diário às 03h BRT (06h UTC) — remove registros antigos para manter banco leve
    _scheduler.add_job(run_data_retention, CronTrigger(hour=6, minute=0, timezone="UTC"),
                       id="data_retention", replace_existing=True,
                       max_instances=1, misfire_grace_time=600)

    _scheduler.start()
    logger.info("Monitoring scheduler started — waha watchdog 2min, checks 5min, log monitor 08h BRT, growth 6h, retention 03h BRT")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Monitoring scheduler stopped")

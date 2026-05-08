import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    from services.monitor import run_all_checks
    from services.log_monitor import run_log_monitor, run_error_growth_check

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

    _scheduler.start()
    logger.info("Monitoring scheduler started — checks every 5 min, log monitor daily at 08h BRT, growth check every 6h")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Monitoring scheduler stopped")

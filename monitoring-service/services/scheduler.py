import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    from services.monitor import run_all_checks
    _scheduler.add_job(run_all_checks, CronTrigger(minute="*/5"),
                       id="monitoring_checks", replace_existing=True,
                       max_instances=1, misfire_grace_time=60)
    _scheduler.start()
    logger.info("Monitoring scheduler started — checks every 5 min")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Monitoring scheduler stopped")

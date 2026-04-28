import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    from services.freshservice import run_daily_sync
    _scheduler.add_job(run_daily_sync, CronTrigger(hour=9, minute=0),
                       id="daily_freshservice_sync", replace_existing=True,
                       max_instances=1, misfire_grace_time=300)
    _scheduler.start()
    logger.info("Freshservice scheduler started — daily sync at 09h UTC")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Freshservice scheduler stopped")

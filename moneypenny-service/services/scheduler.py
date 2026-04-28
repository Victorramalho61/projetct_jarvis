import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    from services.summary import run_daily_summaries
    _scheduler.add_job(run_daily_summaries, CronTrigger(minute=0),
                       id="daily_summary", replace_existing=True)
    _scheduler.start()
    logger.info("Moneypenny scheduler started — summaries every hour at :00")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Moneypenny scheduler stopped")

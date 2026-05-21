"""
Scheduler PayFly V2 — sincroniza vendas do dia anterior às 04:00 BRT.
Independente do agents-service; APScheduler embutido no expenses-service.
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_TZ        = "America/Sao_Paulo"
_scheduler = AsyncIOScheduler(timezone=_TZ)


def start() -> None:
    _scheduler.add_job(
        _sync_yesterday,
        CronTrigger(hour=4, minute=0, timezone=_TZ),
        id="payfly_reservations_daily",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )
    _scheduler.start()
    logger.info("payfly_scheduler: job diário registrado para 04:00 BRT")


def stop() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("payfly_scheduler: encerrado")


async def _sync_yesterday() -> None:
    from datetime import date, timedelta
    from services.payfly_v2_client import sync_date_range
    yesterday = date.today() - timedelta(days=1)
    logger.info("payfly_scheduler: sincronizando %s", yesterday)
    try:
        ok, erros = await asyncio.to_thread(sync_date_range, yesterday, yesterday)
        logger.info("payfly_scheduler: %s — %d ok, %d erros", yesterday, ok, erros)
    except Exception as exc:
        logger.error("payfly_scheduler: erro inesperado — %s", exc, exc_info=True)

"""
Scheduler do pipeline de mídia PayFly — roda a cada 6 horas (00h, 06h, 12h, 18h BRT).
Independente do agents-service; vive no expenses-service.
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
        _run,
        CronTrigger(hour="*/6", minute=0, timezone=_TZ),
        id="payfly_media_6h",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,   # tolera até 10 min de atraso
    )
    _scheduler.start()
    logger.info("media_scheduler: pipeline PayFly registrado para cada 6h (00h, 06h, 12h, 18h BRT)")


def stop() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("media_scheduler: encerrado")


async def _run() -> None:
    logger.info("media_scheduler: iniciando pipeline PayFly")
    try:
        from services.media_pipeline import run
        result = await run()
        logger.info("media_scheduler: concluído — %s", result)
    except Exception as exc:
        logger.error("media_scheduler: erro inesperado — %s", exc, exc_info=True)

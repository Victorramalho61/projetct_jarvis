import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")
_TZ = "America/Sao_Paulo"


def start_scheduler() -> None:
    _scheduler.start()
    reload_agents()
    logger.info("Agents scheduler started")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Agents scheduler stopped")


def _build_trigger(agent: dict):
    stype = agent.get("schedule_type", "manual")
    config = agent.get("schedule_config") or {}

    if stype == "interval":
        m = max(1, int(config.get("minutes", 60)))
        return CronTrigger(minute=f"*/{m}", timezone=_TZ)
    elif stype == "daily":
        return CronTrigger(
            hour=int(config.get("hour", 9)),
            minute=int(config.get("minute", 0)),
            timezone=_TZ,
        )
    elif stype == "weekly":
        return CronTrigger(
            day_of_week=config.get("day_of_week", "mon"),
            hour=int(config.get("hour", 9)),
            minute=int(config.get("minute", 0)),
            timezone=_TZ,
        )
    elif stype == "monthly":
        return CronTrigger(
            day=int(config.get("day", 1)),
            hour=int(config.get("hour", 9)),
            minute=int(config.get("minute", 0)),
            timezone=_TZ,
        )
    return None  # manual — sem trigger automático


def reload_agents() -> None:
    try:
        from db import get_supabase
        db = get_supabase()
        agents = db.table("agents").select("*").eq("enabled", True).execute().data
    except Exception as exc:
        logger.warning("reload_agents: não foi possível carregar agentes do banco (%s). "
                       "Verifique se a migração do schema foi aplicada.", exc)
        return

    for job in _scheduler.get_jobs():
        if job.id.startswith("agent_"):
            job.remove()

    scheduled = 0
    for agent in agents:
        trigger = _build_trigger(agent)
        if trigger is None:
            continue
        _scheduler.add_job(
            _make_agent_job(agent),
            trigger=trigger,
            id=f"agent_{agent['id']}",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
        )
        scheduled += 1

    logger.info("Agent jobs reloaded — %d agentes agendados", scheduled)


def _make_agent_job(agent: dict):
    async def _job():
        from services.agent_runner import run_agent
        await run_agent(agent)
    return _job

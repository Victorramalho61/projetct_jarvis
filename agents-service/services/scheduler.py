import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    _scheduler.start()
    reload_agents()
    logger.info("Agents scheduler started")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Agents scheduler stopped")


def reload_agents() -> None:
    from db import get_supabase
    db = get_supabase()
    agents = db.table("agents").select("*").eq("enabled", True).execute().data

    for job in _scheduler.get_jobs():
        if job.id.startswith("agent_"):
            job.remove()

    for agent in agents:
        interval = agent.get("interval_minutes", 0)
        if interval <= 0:
            continue
        _scheduler.add_job(
            _make_agent_job(agent),
            trigger=CronTrigger(minute=f"*/{interval}"),
            id=f"agent_{agent['id']}",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
        )
    logger.info("Agent jobs reloaded — %d agentes agendados",
                sum(1 for a in agents if a.get("interval_minutes", 0) > 0))


def _make_agent_job(agent: dict):
    async def _job():
        from services.agent_runner import run_agent
        await run_agent(agent)
    return _job

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")
_TZ = "America/Sao_Paulo"


def start_scheduler() -> None:
    _scheduler.start()
    reload_agents()
    _register_langgraph_pipelines()
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
        return IntervalTrigger(minutes=m, timezone=_TZ)
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


def _make_agent_health_job():
    async def _job():
        import asyncio
        from services.agent_runner import run_langgraph_pipeline
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: __import__("importlib").import_module(
                    "graph_engine.agents.agent_health_supervisor"
                ).run({}),
            )
        except Exception as exc:
            logger.error("agent_health_supervisor job error: %s", exc)
    return _job


def _make_pipeline_job(pipeline: str):
    async def _job():
        from services.agent_runner import run_langgraph_pipeline
        await run_langgraph_pipeline(pipeline)
    return _job


def _register_langgraph_pipelines() -> None:
    from db import get_settings
    s = get_settings()

    pipelines = [
        ("monitoring", IntervalTrigger(minutes=s.monitoring_interval_minutes, timezone=_TZ)),
        ("security",   IntervalTrigger(minutes=s.security_interval_minutes, timezone=_TZ)),
        ("cicd",       IntervalTrigger(minutes=s.cicd_interval_minutes, timezone=_TZ)),
        ("dba",        IntervalTrigger(hours=s.dba_interval_hours, timezone=_TZ)),
        ("governance", CronTrigger(hour=s.governance_cron_hour, minute=0, timezone=_TZ)),
        ("evolution",  CronTrigger(hour=s.evolution_cron_hour, minute=0, timezone=_TZ)),
    ]

    for name, trigger in pipelines:
        _scheduler.add_job(
            _make_pipeline_job(name),
            trigger=trigger,
            id=f"pipeline_{name}",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )
        logger.info("Pipeline '%s' registrado no scheduler", name)

    logger.info("LangGraph pipelines registrados: %d", len(pipelines))

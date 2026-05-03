"""
Consome agent_events não processados via polling e aciona o CTO Agent
para eventos críticos ou de alta prioridade.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _poll_once() -> None:
    try:
        from db import get_supabase

        db = get_supabase()

        rows = (
            db.table("agent_events")
            .select("*")
            .eq("processed", False)
            .in_("priority", ["critical", "high"])
            .order("created_at")
            .limit(20)
            .execute()
            .data
        )

        if not rows:
            return

        for event in rows:
            event_type = event.get("event_type", "")
            pipeline = _map_event_to_pipeline(event_type)

            logger.info("event_consumer: acionando pipeline=%s evento=%s", pipeline, event_type)
            try:
                from services.agent_runner import run_langgraph_pipeline
                # Timeout de 5 min por pipeline — evita que um agente travado congele o loop inteiro
                await asyncio.wait_for(run_langgraph_pipeline(pipeline), timeout=300.0)
            except asyncio.TimeoutError:
                logger.error("event_consumer: pipeline '%s' excedeu 5 min — evento %s marcado como processado para evitar reprocessamento", pipeline, event["id"])
            except Exception as exc:
                logger.error("event_consumer: erro ao acionar pipeline %s evento %s: %s", pipeline, event["id"], exc)

            db.table("agent_events").update({"processed": True}).eq("id", event["id"]).execute()

    except Exception as exc:
        logger.error("event_consumer: erro no poll: %s", exc)


def _map_event_to_pipeline(event_type: str) -> str:
    if event_type in ("security_alert", "intrusion_detected", "brute_force_detected"):
        return "security"
    if event_type in ("deploy_failed", "deploy_started"):
        return "cicd"
    if event_type in ("strategic_proposals_ready", "opportunities_mapped", "evolution_briefing_ready"):
        return "governance"
    return "auto_fix"


async def run_event_consumer(poll_seconds: int = 60) -> None:
    logger.info("event_consumer: iniciado (poll a cada %ds)", poll_seconds)
    # Aguarda inicialização completa antes do primeiro poll
    await asyncio.sleep(10)
    while True:
        await _poll_once()
        await asyncio.sleep(poll_seconds)

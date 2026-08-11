"""Scheduler do Plano de Ação - Feedback.

Independente do stub legado services/sla_scheduler.py (não reaproveitado —
é de um fluxo desativado). Este scheduler NUNCA envia e-mail sozinho: ele só
sinaliza para o RH que uma fase venceu (status -> pending_rh_send). O envio
em si é sempre uma ação manual do RH via routes/action_plans.py.
"""
import fcntl
import logging
from datetime import date, datetime, timezone

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None
_lock_file = None  # mantido aberto pela vida do processo — libera o flock ao sair

TZ_BR = pytz.timezone("America/Sao_Paulo")

_LOCK_PATH = "/tmp/action_plan_scheduler.lock"


async def start_action_plan_scheduler() -> None:
    global _scheduler, _lock_file
    # uvicorn roda 4 workers — só um deve manter o scheduler ativo,
    # senão _flag_due_phases dispara 4x às 07:00 (um por worker).
    try:
        _lock_file = open(_LOCK_PATH, "w")
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _logger.info("Scheduler de Plano de Ação: outro worker já detém o lock — não inicia aqui")
        return

    _scheduler = AsyncIOScheduler(timezone=TZ_BR)
    _scheduler.add_job(
        _flag_due_phases,
        "cron",
        hour=7,
        minute=0,
        id="action_plan_flag_due_phases",
        misfire_grace_time=600,
    )
    _scheduler.start()
    _logger.info("Scheduler de Plano de Ação iniciado: 07:00 (sinaliza fases vencidas para o RH)")


async def stop_action_plan_scheduler() -> None:
    global _scheduler, _lock_file
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _logger.info("Scheduler de Plano de Ação encerrado")
    if _lock_file:
        _lock_file.close()
        _lock_file = None


async def _flag_due_phases() -> None:
    _logger.info("Plano de Ação 07:00 — verificando fases vencidas")
    from db import get_supabase

    db = get_supabase()
    today = date.today().isoformat()

    try:
        due_phases = (
            db.table("performance_action_plan_phases")
            .select("id,action_plan_id")
            .eq("status", "scheduled")
            .lte("due_date", today)
            .execute()
            .data
        ) or []
    except Exception:
        _logger.exception("Erro ao buscar fases vencidas")
        return

    if not due_phases:
        _logger.info("Nenhuma fase vencida hoje")
        return

    plan_ids = list({p["action_plan_id"] for p in due_phases})
    _CHUNK = 150
    active_plans = []
    for i in range(0, len(plan_ids), _CHUNK):
        active_plans.extend(
            db.table("performance_action_plans")
            .select("id")
            .in_("id", plan_ids[i:i + _CHUNK])
            .eq("status", "active")
            .execute()
            .data or []
        )
    active_plan_ids = {p["id"] for p in active_plans}

    to_flag = [p["id"] for p in due_phases if p["action_plan_id"] in active_plan_ids]
    if not to_flag:
        _logger.info("Fases vencidas encontradas, mas nenhum plano ainda ativo (aguardando preenchimento inicial)")
        return

    now = datetime.now(tz=timezone.utc).isoformat()
    for i in range(0, len(to_flag), _CHUNK):
        db.table("performance_action_plan_phases").update({
            "status": "pending_rh_send",
            "became_due_at": now,
        }).in_("id", to_flag[i:i + _CHUNK]).execute()
    _logger.info("%d fase(s) marcada(s) como pending_rh_send", len(to_flag))

import asyncio
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


async def _ensure_waha_session() -> None:
    """Garante que a sessão WAHA default esteja WORKING. Relança se STOPPED."""
    from db import get_settings
    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_api_key:
        return
    base = s.whatsapp_api_url.rstrip("/")
    headers = {"X-Api-Key": s.whatsapp_api_key}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{base}/api/sessions/default", headers=headers)
            if r.status_code != 200:
                return
            status = r.json().get("status", "")
            if status not in ("STOPPED", "FAILED"):
                return
            logger.warning("WAHA session status=%s — reiniciando automaticamente", status)
            await client.post(f"{base}/api/sessions/default/start",
                              headers=headers, json={})
            logger.info("WAHA session start enviado")
    except Exception as exc:
        logger.debug("_ensure_waha_session erro: %s", exc)


async def _sync_benner() -> None:
    """Captura snapshot comprimido do Benner e salva no Supabase; alerta se houver erros novos."""
    from db import get_settings
    from benner_db import query_new_errors
    from services.benner_monitor import sync_benner_snapshot

    await sync_benner_snapshot()

    try:
        errors = await asyncio.to_thread(query_new_errors, 15)
    except Exception as exc:
        logger.warning("benner_check: falha ao consultar SQL Server: %s", exc)
        return

    if not errors:
        return

    s = get_settings()
    if not s.whatsapp_api_url or not s.whatsapp_api_key:
        logger.info("benner_check: %d erros novos (WhatsApp não configurado)", len(errors))
        return

    logger.warning("benner_check: %d erros novos detectados", len(errors))
    produtos = {}
    for e in errors:
        p = e.get("produto") or "?"
        produtos[p] = produtos.get(p, 0) + 1

    linhas = "\n".join(f"  • {prod}: {qty}" for prod, qty in produtos.items())
    msg = (
        f"⚠️ *Benner Integração — Erros detectados*\n"
        f"Últimos 15 min: *{len(errors)} erros*\n\n"
        f"{linhas}\n\n"
        f"Último: {errors[0].get('mensagem', '')[:120]}"
    )

    try:
        base = s.whatsapp_api_url.rstrip("/")
        headers = {"X-Api-Key": s.whatsapp_api_key}
        payload = {
            "session": s.whatsapp_instance,
            "chatId": "admins",
            "text": msg,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{base}/api/sendText", headers=headers, json=payload)
            if r.status_code not in (200, 201):
                logger.warning("benner_check: falha no envio WhatsApp: %s", r.text[:200])
    except Exception as exc:
        logger.warning("benner_check: erro ao enviar WhatsApp: %s", exc)


def start_scheduler() -> None:
    from services.monitor import run_all_checks
    from services.log_monitor import run_log_monitor, run_error_growth_check
    from services.retention import run_data_retention

    _scheduler.add_job(_ensure_waha_session, CronTrigger(minute="*/5"),
                       id="waha_session_watchdog", replace_existing=True,
                       max_instances=1, misfire_grace_time=60)

    _scheduler.add_job(run_all_checks, CronTrigger(minute="*/5"),
                       id="monitoring_checks", replace_existing=True,
                       max_instances=1, misfire_grace_time=60)

    # Diário às 8h BRT (11h UTC) — varre app_logs e abre issue no GitHub se houver erros recorrentes
    _scheduler.add_job(run_log_monitor, CronTrigger(hour=11, minute=0, timezone="UTC"),
                       id="log_monitor_daily", replace_existing=True,
                       max_instances=1, misfire_grace_time=300)

    # A cada 6h — detecta crescimento acelerado de erros por módulo (≥80% em 24h)
    _scheduler.add_job(run_error_growth_check, CronTrigger(hour="*/6", minute=0, timezone="UTC"),
                       id="error_growth_check", replace_existing=True,
                       max_instances=1, misfire_grace_time=300)

    # Diário às 03h BRT (06h UTC) — remove registros antigos para manter banco leve
    _scheduler.add_job(run_data_retention, CronTrigger(hour=6, minute=0, timezone="UTC"),
                       id="data_retention", replace_existing=True,
                       max_instances=1, misfire_grace_time=600)

    # Diário às 07h BRT (10h UTC) — snapshot comprimido Benner → Supabase
    _scheduler.add_job(_sync_benner, CronTrigger(hour=10, minute=0, timezone="UTC"),
                       id="benner_sync", replace_existing=True,
                       max_instances=1, misfire_grace_time=600)

    _scheduler.start()
    logger.info("Monitoring scheduler started — waha watchdog 2min, checks 5min, log monitor 08h BRT, growth 6h, retention 03h BRT, benner 15min")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Monitoring scheduler stopped")

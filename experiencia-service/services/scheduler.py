"""APScheduler: sync Benner às 03h + cobranças automáticas às 08h."""
import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None

# Intervalo de reenvio de cobrança (em dias)
INTERVALO_COBRANCA_DIAS = 3


def _job_sync_benner():
    try:
        from services.benner_sync import run_sync
        stats = run_sync()
        log.info("[scheduler] sync_benner concluído: %s", stats)
    except Exception as exc:
        log.error("[scheduler] sync_benner falhou: %s", exc)


def _job_enviar_cobracas():
    """Envia cobranças automáticas para avaliações pendentes de resposta."""
    try:
        from db import get_supabase
        from services.email_service import send_cobranca
        sb = get_supabase()

        hoje = date.today().isoformat()

        # Busca avaliações com status=enviado e data_prevista <= hoje
        resp = (
            sb.table("exp_avaliacoes")
            .select("*, exp_employees(*)")
            .eq("status", "enviado")
            .lte("data_prevista", hoje)
            .execute()
        )

        enviadas = 0
        for av in (resp.data or []):
            try:
                # Verifica intervalo desde último envio
                from datetime import datetime, timezone
                ultimo = av.get("ultimo_envio_at")
                if ultimo:
                    dt = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
                    dias_desde = (datetime.now(timezone.utc) - dt).days
                    if dias_desde < INTERVALO_COBRANCA_DIAS:
                        continue

                emp = av.get("exp_employees") or {}
                gestor_email = emp.get("gestor_email")
                if not gestor_email:
                    continue

                ok = send_cobranca(av, emp)
                if ok:
                    enviadas += 1
            except Exception as exc:
                log.error("[scheduler] cobrança avaliacao %s falhou: %s", av.get("id"), exc)

        log.info("[scheduler] cobranças automáticas: %d enviadas", enviadas)
    except Exception as exc:
        log.error("[scheduler] job_enviar_cobracas falhou: %s", exc)


def start():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    _scheduler.add_job(_job_sync_benner,    "cron", hour=3,  minute=0,  id="sync_benner")
    _scheduler.add_job(_job_enviar_cobracas,"cron", hour=8,  minute=0,  id="cobracas_auto")
    _scheduler.start()
    log.info("[scheduler] iniciado (sync=03h00, cobranças=08h00)")


def stop():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[scheduler] parado")

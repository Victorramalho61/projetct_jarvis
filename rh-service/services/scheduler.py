"""APScheduler: relatório semanal de vagas — segunda-feira 7h BRT."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _job_relatorio_semanal():
    try:
        from services.relatorio_semanal import gerar_e_enviar
        gerar_e_enviar()
    except Exception as exc:
        log.error("[scheduler] relatorio_semanal falhou: %s", exc)


def start():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    _scheduler.add_job(_job_relatorio_semanal, "cron", day_of_week="mon", hour=7, minute=0, id="relatorio_semanal")
    _scheduler.start()
    log.info("[scheduler] iniciado (relatório semanal: segunda 07h00)")


def stop():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[scheduler] parado")

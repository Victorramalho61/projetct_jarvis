"""APScheduler: sync Benner às 04h · envio automático (D-10) às 08h · cobranças às 08h10."""
import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None

# Intervalo de reenvio de cobrança (em dias)
INTERVALO_COBRANCA_DIAS = 3

# Envio automático do formulário 10 dias antes do vencimento (35º e 80º dia da admissão).
DIAS_ANTECEDENCIA_ENVIO = 10
# Só avaliações cujo D-10 cai a partir desta data: o passivo já vencido/em D-10 no dia da
# implantação NÃO é disparado em massa — fica para o RH enviar manualmente pela tela.
GO_LIVE_ENVIO_AUTOMATICO = date(2026, 9, 25)


def _job_sync_benner():
    try:
        from services.benner_sync import run_sync
        stats = run_sync(completo=None)  # incremental: admitidos ontem + re-sync dos abertos
        log.info("[scheduler] sync_benner concluído: %s", stats)
    except Exception as exc:
        log.error("[scheduler] sync_benner falhou: %s", exc)


def avaliacoes_para_envio_automatico(sb, hoje: date | None = None) -> list[dict]:
    """Pendentes com gestor válido cujo D-10 já chegou e é >= go-live."""
    hoje = hoje or date.today()
    limite = (hoje + timedelta(days=DIAS_ANTECEDENCIA_ENVIO)).isoformat()
    minimo = (GO_LIVE_ENVIO_AUTOMATICO + timedelta(days=DIAS_ANTECEDENCIA_ENVIO)).isoformat()
    rows = (
        sb.table("exp_avaliacoes")
        .select("*, exp_employees(*)")
        .eq("status", "pendente")
        .is_("envio_automatico_at", "null")
        .lte("data_prevista", limite)
        .gte("data_prevista", minimo)
        .execute()
        .data or []
    )
    return [r for r in rows if (r.get("exp_employees") or {}).get("gestor_email")
            and (r.get("exp_employees") or {}).get("ativo", True)]


def _job_envio_automatico():
    """Envia o formulário ao gestor 10 dias antes do vencimento (35º/80º dia)."""
    try:
        from db import get_supabase
        from routes.admin import _gerar_token, _registrar_envio
        from services.email_service import send_primeiro_envio
        sb = get_supabase()
        enviados = 0
        for av in avaliacoes_para_envio_automatico(sb):
            try:
                emp = av.get("exp_employees") or {}
                token = av.get("token") or _gerar_token(av["id"], sb)
                ok = send_primeiro_envio(av, emp, token, automatico=True)
                _registrar_envio(sb, av["id"], emp.get("gestor_email"), "envio_automatico", ok)
                if ok:
                    sb.table("exp_avaliacoes").update({"envio_automatico_at": "now()"}).eq("id", av["id"]).execute()
                    enviados += 1
            except Exception as exc:
                log.error("[scheduler] envio automático %s falhou: %s", av.get("id"), exc)
        log.info("[scheduler] envio automático D-%d: %d enviados", DIAS_ANTECEDENCIA_ENVIO, enviados)
    except Exception as exc:
        log.error("[scheduler] job_envio_automatico falhou: %s", exc)


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
    _scheduler.add_job(_job_sync_benner,      "cron", hour=4, minute=0,  id="sync_benner")
    _scheduler.add_job(_job_envio_automatico, "cron", hour=8, minute=0,  id="envio_automatico")
    _scheduler.add_job(_job_enviar_cobracas,  "cron", hour=8, minute=10, id="cobracas_auto")
    _scheduler.start()
    log.info("[scheduler] iniciado (sync=04h00, envio automático D-10=08h00, cobranças=08h10)")


def stop():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[scheduler] parado")

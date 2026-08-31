"""APScheduler: verifica aderência/prazo (07h/07h30) + cobranças automáticas (08h)."""
import logging
from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None

# Intervalo mínimo entre cobranças automáticas (em dias corridos)
INTERVALO_COBRANCA_DIAS = 5


def _job_verificar_aderencia():
    """Postergação automática (+10 dias úteis) quando aderência < 30% — só na 1ª ocorrência por campanha."""
    try:
        from db import get_supabase
        from services.business_days import add_business_days
        from services.dashboard import build_campanha_dashboard
        from services.email_service import log_email, send_reforco_adesao
        sb = get_supabase()

        resp = sb.table("sat_campanhas").select("*").eq("status", "em_andamento").execute()
        for campanha in (resp.data or []):
            try:
                if (campanha.get("qtd_postergacoes") or 0) >= 1:
                    continue
                if not campanha.get("data_prazo"):
                    continue

                dashboard = build_campanha_dashboard(sb, campanha["id"])
                aderencia = dashboard.get("aderencia", {})
                if aderencia.get("atingiu_minimo", True):
                    continue

                # Só posterga a partir da metade do prazo original (evita postergar no 1º dia)
                if campanha.get("data_inicio") and campanha.get("data_prazo_original"):
                    inicio = date.fromisoformat(campanha["data_inicio"])
                    prazo_original = date.fromisoformat(campanha["data_prazo_original"])
                    dias_totais = (prazo_original - inicio).days
                    if (date.today() - inicio).days < dias_totais / 2:
                        continue

                nova_data_prazo = add_business_days(date.fromisoformat(campanha["data_prazo"]), 10)
                sb.table("sat_campanhas").update({
                    "status": "postergada",
                    "data_prazo": nova_data_prazo.isoformat(),
                    "postergada_em": datetime.now(timezone.utc).isoformat(),
                    "motivo_postergacao": "Aderência automática abaixo de 30% — postergação automática (+10 dias úteis)",
                    "qtd_postergacoes": (campanha.get("qtd_postergacoes") or 0) + 1,
                    "updated_at": "now()",
                }).eq("id", campanha["id"]).execute()
                sb.table("sat_campanhas").update({"status": "em_andamento"}).eq("id", campanha["id"]).execute()

                pendentes = (
                    sb.table("sat_respostas")
                    .select("*, sat_clientes(*)")
                    .eq("campanha_id", campanha["id"])
                    .in_("status", ["pendente", "enviado"])
                    .execute()
                )
                for resposta in (pendentes.data or []):
                    cliente = resposta.get("sat_clientes") or {}
                    if not cliente.get("contato_email") or not resposta.get("token"):
                        continue
                    ok = send_reforco_adesao(cliente, campanha, resposta)
                    log_email(sb, resposta["id"], cliente["contato_email"], "reforco_adesao", ok)

                log.info("[scheduler] campanha %s postergada automaticamente (+10 dias úteis)", campanha["id"])
            except Exception as exc:
                log.error("[scheduler] verificar_aderencia campanha %s falhou: %s", campanha.get("id"), exc)
    except Exception as exc:
        log.error("[scheduler] job_verificar_aderencia falhou: %s", exc)


def _job_verificar_prazo_vencido():
    """Encerra automaticamente campanhas cujo prazo já passou."""
    try:
        from db import get_supabase
        sb = get_supabase()
        hoje = date.today().isoformat()

        resp = (
            sb.table("sat_campanhas")
            .select("*")
            .in_("status", ["em_andamento", "postergada"])
            .lt("data_prazo", hoje)
            .execute()
        )
        for campanha in (resp.data or []):
            try:
                sb.table("sat_respostas").update({"status": "expirado"}).eq(
                    "campanha_id", campanha["id"]
                ).in_("status", ["pendente", "enviado"]).execute()
                sb.table("sat_campanhas").update({
                    "status": "encerrada",
                    "encerrada_em": datetime.now(timezone.utc).isoformat(),
                    "updated_at": "now()",
                }).eq("id", campanha["id"]).execute()
                log.info("[scheduler] campanha %s encerrada automaticamente (prazo vencido)", campanha["id"])
            except Exception as exc:
                log.error("[scheduler] verificar_prazo_vencido campanha %s falhou: %s", campanha.get("id"), exc)
    except Exception as exc:
        log.error("[scheduler] job_verificar_prazo_vencido falhou: %s", exc)


def _job_cobranca_automatica():
    """Envia cobranças automáticas para respostas pendentes de envio há mais de N dias."""
    try:
        from db import get_supabase
        from services.email_service import log_email, send_cobranca
        sb = get_supabase()

        resp = (
            sb.table("sat_respostas")
            .select("*, sat_clientes(*), sat_campanhas(*)")
            .eq("status", "enviado")
            .execute()
        )

        enviadas = 0
        for resposta in (resp.data or []):
            try:
                campanha = resposta.get("sat_campanhas") or {}
                if campanha.get("status") not in ("em_andamento", "postergada"):
                    continue

                ultimo = resposta.get("ultimo_envio_at")
                if ultimo:
                    dt = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
                    dias_desde = (datetime.now(timezone.utc) - dt).days
                    if dias_desde < INTERVALO_COBRANCA_DIAS:
                        continue

                cliente = resposta.get("sat_clientes") or {}
                if not cliente.get("contato_email"):
                    continue

                ok = send_cobranca(cliente, campanha, resposta)
                log_email(sb, resposta["id"], cliente["contato_email"], "cobranca", ok)
                if ok:
                    now = datetime.now(timezone.utc).isoformat()
                    sb.table("sat_respostas").update({
                        "total_envios": (resposta.get("total_envios") or 0) + 1,
                        "ultimo_envio_at": now,
                        "updated_at": "now()",
                    }).eq("id", resposta["id"]).execute()
                    enviadas += 1
            except Exception as exc:
                log.error("[scheduler] cobrança resposta %s falhou: %s", resposta.get("id"), exc)

        log.info("[scheduler] cobranças automáticas: %d enviadas", enviadas)
    except Exception as exc:
        log.error("[scheduler] job_cobranca_automatica falhou: %s", exc)


def start():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    _scheduler.add_job(_job_verificar_aderencia,    "cron", hour=7,  minute=0,  id="verificar_aderencia")
    _scheduler.add_job(_job_verificar_prazo_vencido,"cron", hour=7,  minute=30, id="verificar_prazo_vencido")
    _scheduler.add_job(_job_cobranca_automatica,    "cron", hour=8,  minute=0,  id="cobranca_automatica")
    _scheduler.start()
    log.info("[scheduler] iniciado (aderência=07h00, prazo=07h30, cobranças=08h00)")


def stop():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[scheduler] parado")

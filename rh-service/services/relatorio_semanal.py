"""Monta e envia o relatório semanal de vagas — segunda-feira 7h BRT."""
import logging

from db import get_supabase

log = logging.getLogger(__name__)

DESTINATARIO_EMAIL = "renata.facundo@voetur.com.br"
DESTINATARIO_NOME = "Renata Facundo"


def gerar_e_enviar():
    from routes.vagas import _SELECT, _serialize
    from services.email_service import send_relatorio_semanal

    sb = get_supabase()
    resp = sb.table("rh_vagas").select(_SELECT).execute()
    rows = [_serialize(r) for r in (resp.data or [])]
    rows = [r for r in rows if (r.get("data_recebimento") or "")[:4] >= "2026"]

    abertas = [r for r in rows if r.get("status_em_aberto")]
    concluidas_total = [r for r in rows if r.get("status_concluido")]

    sla_estourado = [r for r in abertas if r.get("sla_ok") is False]
    sla_estourando = []
    for r in abertas:
        dias = r.get("dias_corridos")
        alvo = r.get("sla_alvo_dias")
        if dias is None or not alvo or r.get("sla_ok") is False:
            continue
        if alvo - dias <= 3:
            sla_estourando.append(r)

    kpis = {"abertas": len(abertas), "concluidas_periodo": len(concluidas_total)}

    ok = send_relatorio_semanal(DESTINATARIO_EMAIL, DESTINATARIO_NOME, kpis, sla_estourado, sla_estourando)
    log.info(
        "[relatorio_semanal] enviado=%s abertas=%d sla_estourado=%d sla_estourando=%d",
        ok, len(abertas), len(sla_estourado), len(sla_estourando),
    )
    return ok

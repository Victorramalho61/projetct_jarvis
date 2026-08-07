"""KPIs e breakdowns do módulo de RH — usado pelo dashboard e pelo relatório impresso."""
import logging
from collections import Counter, defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/rh/dashboard")
log = logging.getLogger(__name__)

_ROLES = ("admin", "rh")


def _require_rh(user=Depends(require_role(*_ROLES))):
    return user


@router.post("/relatorio-semanal/enviar-agora")
def enviar_relatorio_semanal_agora(user=Depends(_require_rh)):
    from services.relatorio_semanal import gerar_e_enviar
    ok = gerar_e_enviar()
    return {"ok": ok}


@router.get("")
def dashboard(
    q: Optional[str] = Query(None),
    status_id: Optional[list[str]] = Query(None),
    ano: Optional[list[int]] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    empresa_id: Optional[str] = Query(None),
    tipo_vaga_id: Optional[str] = Query(None),
    tipo_contrato_id: Optional[str] = Query(None),
    nivel_id: Optional[str] = Query(None),
    hierarquia_id: Optional[str] = Query(None),
    etapa_atual_id: Optional[str] = Query(None),
    secao_id: Optional[str] = Query(None),
    responsavel_id: Optional[str] = Query(None),
    requisitante_id: Optional[str] = Query(None),
    cargo_id: Optional[str] = Query(None),
    user=Depends(_require_rh),
):
    from routes.vagas import _FILTER_COLS, _SELECT, _serialize

    sb = get_supabase()
    query = sb.table("rh_vagas").select(_SELECT)

    if status_id:
        query = query.in_("status_id", status_id)
    if data_inicio:
        query = query.gte("data_recebimento", data_inicio)
    if data_fim:
        query = query.lte("data_recebimento", data_fim)

    locals_ = locals()
    for col in _FILTER_COLS:
        val = locals_.get(col)
        if val:
            query = query.eq(col, val)

    resp = query.execute()
    rows = [_serialize(r) for r in (resp.data or [])]

    if ano:
        anos_str = {str(a) for a in ano}
        rows = [r for r in rows if (r.get("data_recebimento") or "")[:4] in anos_str]

    if q:
        q_lower = q.lower()
        rows = [
            r for r in rows
            if q_lower in (r.get("candidato") or "").lower()
            or q_lower in (r.get("cargo") or "").lower()
            or q_lower in (r.get("numero_requisicao") or "").lower()
        ]

    abertas = [r for r in rows if r.get("status_em_aberto")]
    concluidas = [r for r in rows if r.get("status_concluido")]
    canceladas = [r for r in rows if r.get("status") == "CANCELADO"]
    congeladas = [r for r in rows if r.get("status") == "CONGELADO"]

    slas_validos = [r["sla_ok"] for r in rows if r.get("sla_ok") is not None]
    pct_no_prazo = round(100 * sum(slas_validos) / len(slas_validos), 1) if slas_validos else None

    dias_validos = [r["dias_corridos"] for r in concluidas if r.get("dias_corridos") is not None]
    sla_medio_dias = round(sum(dias_validos) / len(dias_validos), 1) if dias_validos else None

    atrasadas = [r for r in abertas if r.get("sla_ok") is False]

    # SLA estourado (já passou do prazo) e estourando (faltam <=3 dias, ainda no prazo)
    sla_estourado = [r for r in atrasadas]
    sla_estourando = []
    for r in abertas:
        dias = r.get("dias_corridos")
        alvo = r.get("sla_alvo_dias")
        if dias is None or not alvo or r.get("sla_ok") is False:
            continue
        if alvo - dias <= 3:
            sla_estourando.append(r)

    def _resumo_alerta(r):
        return {
            "id": r.get("id"), "numero_requisicao": r.get("numero_requisicao"),
            "cargo": r.get("cargo"), "empresa": r.get("empresa"),
            "responsavel": r.get("responsavel"), "dias_corridos": r.get("dias_corridos"),
            "sla_alvo_dias": r.get("sla_alvo_dias"), "etapa_atual": r.get("etapa_atual"),
            "status": r.get("status"),
        }

    # Vagas por analista
    por_analista_map: dict[str, dict] = {}
    for r in rows:
        nome = r.get("responsavel") or "NÃO INFORMADO"
        item = por_analista_map.setdefault(nome, {
            "analista": nome, "total": 0, "abertas": 0, "concluidas": 0,
            "canceladas": 0, "congeladas": 0,
        })
        item["total"] += 1
        if r.get("status_em_aberto"):
            item["abertas"] += 1
        if r.get("status_concluido"):
            item["concluidas"] += 1
        if r.get("status") == "CANCELADO":
            item["canceladas"] += 1
        if r.get("status") == "CONGELADO":
            item["congeladas"] += 1

    por_status = Counter(r.get("status") or "NÃO INFORMADO" for r in rows)
    por_empresa = Counter(r.get("empresa") or "NÃO INFORMADO" for r in rows)
    top_cargos = Counter(r.get("cargo") for r in rows if r.get("cargo"))

    tendencia: dict[str, dict[str, int]] = defaultdict(lambda: {"abertas": 0, "concluidas": 0})
    for r in rows:
        mes = (r.get("data_recebimento") or "")[:7]
        if mes:
            tendencia[mes]["abertas"] += 1
    for r in concluidas:
        mes = (r.get("data_admissao") or r.get("data_recebimento") or "")[:7]
        if mes:
            tendencia[mes]["concluidas"] += 1

    etapas_resp = sb.table("rh_etapas_processo").select("id,nome,ordem").order("ordem").execute()
    contagem_etapa = Counter(r.get("etapa_atual_id") for r in rows if r.get("etapa_atual_id"))
    funil_etapas = [
        {"etapa": e["nome"], "ordem": e["ordem"], "total": contagem_etapa.get(e["id"], 0)}
        for e in (etapas_resp.data or [])
    ]

    return {
        "kpis": {
            "total": len(rows),
            "abertas": len(abertas),
            "concluidas_periodo": len(concluidas),
            "sla_medio_dias": sla_medio_dias,
            "pct_no_prazo": pct_no_prazo,
            "atrasadas": len(atrasadas),
            "canceladas": len(canceladas),
            "congeladas": len(congeladas),
        },
        "por_status": [{"status": k, "total": v} for k, v in sorted(por_status.items(), key=lambda x: -x[1])],
        "por_empresa": [{"empresa": k, "total": v} for k, v in sorted(por_empresa.items(), key=lambda x: -x[1])],
        "top_cargos": [{"cargo": k, "total": v} for k, v in top_cargos.most_common(10)],
        "tendencia_mensal": [
            {"mes": mes, **vals} for mes, vals in sorted(tendencia.items())
        ],
        "funil_etapas": funil_etapas,
        "por_analista": sorted(por_analista_map.values(), key=lambda x: -x["total"]),
        "sla_estourado": [_resumo_alerta(r) for r in sla_estourado],
        "sla_estourando": [_resumo_alerta(r) for r in sla_estourando],
        "abertas_lista": [_resumo_alerta(r) for r in abertas],
        "canceladas_congeladas_lista": [_resumo_alerta(r) for r in canceladas + congeladas],
    }

"""CRUD de vagas (processos de admissão) — núcleo do módulo de RH."""
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/rh/vagas")
log = logging.getLogger(__name__)

_ROLES = ("admin", "rh")


def _require_rh(user=Depends(require_role(*_ROLES))):
    return user


_SELECT = (
    "*, "
    "rh_empresas(nome,prefixo_requisicao), "
    "rh_alocacoes(nome), "
    "rh_tipos_contrato(nome), "
    "rh_tipos_vaga(nome), "
    "rh_cargos(nome), "
    "rh_niveis(nome), "
    "rh_hierarquias(nome), "
    "rh_requisitantes(nome), "
    "rh_status_vaga(nome,em_aberto,concluido), "
    "rh_etapas_processo(nome,ordem), "
    "rh_secoes(nome), "
    "rh_modalidades(nome), "
    "rh_analistas(nome), "
    "rh_perfis_calculo(nome)"
)


def _dias_corridos(v: dict) -> Optional[int]:
    recebimento = v.get("data_recebimento")
    if not recebimento:
        return None
    recebimento = datetime.strptime(recebimento, "%Y-%m-%d").date() if isinstance(recebimento, str) else recebimento

    status = v.get("rh_status_vaga") or {}
    if status.get("concluido"):
        admissao = v.get("data_admissao")
        if not admissao:
            return None
        fim = datetime.strptime(admissao, "%Y-%m-%d").date() if isinstance(admissao, str) else admissao
    else:
        fim = date.today()

    dias = (fim - recebimento).days
    return dias if dias >= 0 else None


def _sla_ok(v: dict) -> Optional[bool]:
    status = v.get("rh_status_vaga") or {}
    if status.get("nome") == "CANCELADO":
        return None
    dias = _dias_corridos(v)
    sla = v.get("sla_alvo_dias")
    if dias is None or not sla:
        return None
    return dias <= sla


def _serialize(v: dict) -> dict:
    v = dict(v)
    v["empresa"] = (v.pop("rh_empresas", None) or {}).get("nome")
    v["alocacao"] = (v.pop("rh_alocacoes", None) or {}).get("nome")
    v["tipo_contrato"] = (v.pop("rh_tipos_contrato", None) or {}).get("nome")
    v["tipo_vaga"] = (v.pop("rh_tipos_vaga", None) or {}).get("nome")
    v["cargo"] = (v.pop("rh_cargos", None) or {}).get("nome")
    v["nivel"] = (v.pop("rh_niveis", None) or {}).get("nome")
    v["hierarquia"] = (v.pop("rh_hierarquias", None) or {}).get("nome")
    v["requisitante"] = (v.pop("rh_requisitantes", None) or {}).get("nome")
    status = v.pop("rh_status_vaga", None) or {}
    v["status"] = status.get("nome")
    v["status_em_aberto"] = status.get("em_aberto")
    v["status_concluido"] = status.get("concluido")
    etapa = v.pop("rh_etapas_processo", None) or {}
    v["etapa_atual"] = etapa.get("nome")
    v["secao"] = (v.pop("rh_secoes", None) or {}).get("nome")
    v["modalidade"] = (v.pop("rh_modalidades", None) or {}).get("nome")
    v["responsavel"] = (v.pop("rh_analistas", None) or {}).get("nome")
    v["perfil_calculo"] = (v.pop("rh_perfis_calculo", None) or {}).get("nome")

    v["dias_corridos"] = _dias_corridos({**v, "rh_status_vaga": status, "data_recebimento": v.get("data_recebimento"), "data_admissao": v.get("data_admissao")})
    v["sla_ok"] = _sla_ok({**v, "rh_status_vaga": status})
    return v


# ── Automação: cargo->nível, etapa->seção/status, salário->custo total ──────

def _apply_automacao(sb, payload: dict, current: Optional[dict] = None) -> dict:
    payload = dict(payload)
    current = current or {}

    if payload.get("cargo_id") and "nivel_id" not in payload:
        cargo = sb.table("rh_cargos").select("nivel_padrao_id").eq("id", payload["cargo_id"]).single().execute()
        nivel_padrao = (cargo.data or {}).get("nivel_padrao_id")
        if nivel_padrao:
            payload["nivel_id"] = nivel_padrao

    if payload.get("etapa_atual_id"):
        etapa = sb.table("rh_etapas_processo").select("nome,secao_responsavel_id").eq("id", payload["etapa_atual_id"]).single().execute()
        etapa_data = etapa.data or {}
        if "secao_id" not in payload and etapa_data.get("secao_responsavel_id"):
            payload["secao_id"] = etapa_data["secao_responsavel_id"]
        if "status_id" not in payload and etapa_data.get("nome") in ("CONCLUÍDO", "CANCELADO"):
            status = sb.table("rh_status_vaga").select("id").eq("nome", etapa_data["nome"]).single().execute()
            if status.data:
                payload["status_id"] = status.data["id"]

    # Auto-sugestão de perfil de cálculo (sempre editável) quando empresa/
    # alocação mudam e a vaga ainda não tem perfil escolhido
    if (
        ("empresa_id" in payload or "alocacao_id" in payload)
        and "perfil_calculo_id" not in payload
        and not current.get("perfil_calculo_id")
    ):
        from services.calculadora import sugerir_perfil

        empresa_id = payload.get("empresa_id", current.get("empresa_id"))
        alocacao_id = payload.get("alocacao_id", current.get("alocacao_id"))
        tipo_contrato_id = payload.get("tipo_contrato_id", current.get("tipo_contrato_id"))

        def _nome(tabela, item_id):
            if not item_id:
                return None
            r = sb.table(tabela).select("nome").eq("id", item_id).single().execute()
            return (r.data or {}).get("nome")

        perfis = sb.table("rh_perfis_calculo").select("id,nome").execute().data or []
        sugestao = sugerir_perfil(
            perfis,
            _nome("rh_empresas", empresa_id),
            _nome("rh_alocacoes", alocacao_id),
            _nome("rh_tipos_contrato", tipo_contrato_id),
        )
        if sugestao:
            payload["perfil_calculo_id"] = sugestao

    # Cálculo de custo total — snapshot, recalculado só quando salário ou
    # perfil de cálculo mudam (fica congelado depois, mesmo se o perfil for
    # editado na tela de Listas)
    perfil_calculo_id = payload.get("perfil_calculo_id", current.get("perfil_calculo_id"))
    salario = payload.get("salario", current.get("salario"))
    if perfil_calculo_id and salario is not None and ("salario" in payload or "perfil_calculo_id" in payload):
        from services.calculadora import calcular_custo

        perfil = sb.table("rh_perfis_calculo").select("*").eq("id", perfil_calculo_id).single().execute()
        if perfil.data:
            detalhado = calcular_custo(perfil.data, salario)
            payload["custo_total"] = detalhado["custo_total"]
            payload["calculo_detalhado"] = detalhado

    return payload


# ── Listagem com busca + filtros ─────────────────────────────────────────────

_FILTER_COLS = [
    "empresa_id", "tipo_vaga_id", "tipo_contrato_id", "nivel_id",
    "hierarquia_id", "etapa_atual_id", "secao_id", "responsavel_id",
    "requisitante_id", "cargo_id", "modalidade_id",
]


@router.get("")
def listar_vagas(
    q: Optional[str] = Query(None, description="Busca por candidato, cargo ou nº de requisição"),
    status_id: Optional[list[str]] = Query(None),
    ano: Optional[list[int]] = Query(None, description="Filtra por ano de data_recebimento — múltiplos anos não-contíguos"),
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
    modalidade_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user=Depends(_require_rh),
):
    sb = get_supabase()
    query = sb.table("rh_vagas").select(_SELECT).order("data_recebimento", desc=True)

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

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start:start + page_size]

    return {"total": total, "page": page, "page_size": page_size, "items": page_rows}


# ── Iniciar novo processo (draft imediato) ───────────────────────────────────

class IniciarPayload(BaseModel):
    empresa_id: str


@router.post("/iniciar")
def iniciar_processo(payload: IniciarPayload, user=Depends(_require_rh)):
    from services.numbering import gerar_numero_requisicao

    sb = get_supabase()
    empresa = sb.table("rh_empresas").select("id").eq("id", payload.empresa_id).execute()
    if not empresa.data:
        raise HTTPException(status_code=400, detail="Empresa inválida")

    status_inicial = sb.table("rh_status_vaga").select("id").eq("nome", "EM ANDAMENTO").single().execute()
    if not status_inicial.data:
        raise HTTPException(status_code=500, detail="Status inicial 'EM ANDAMENTO' não configurado")

    numero_requisicao = gerar_numero_requisicao(sb, payload.empresa_id)

    row = {
        "numero_requisicao": numero_requisicao,
        "empresa_id": payload.empresa_id,
        "data_recebimento": date.today().isoformat(),
        "status_id": status_inicial.data["id"],
        "created_by": user.get("id"),
        "updated_by": user.get("id"),
    }
    resp = sb.table("rh_vagas").insert(row).execute()
    novo = resp.data[0]

    detalhe = sb.table("rh_vagas").select(_SELECT).eq("id", novo["id"]).single().execute()
    return _serialize(detalhe.data)


# ── Detalhe / edição / exclusão ───────────────────────────────────────────────

@router.get("/{vaga_id}")
def detalhe_vaga(vaga_id: str, user=Depends(_require_rh)):
    sb = get_supabase()
    resp = sb.table("rh_vagas").select(_SELECT).eq("id", vaga_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    return _serialize(resp.data[0])


@router.patch("/{vaga_id}")
def editar_vaga(vaga_id: str, payload: dict, user=Depends(_require_rh)):
    sb = get_supabase()
    existente = sb.table("rh_vagas").select(
        "id,salario,perfil_calculo_id,empresa_id,alocacao_id,tipo_contrato_id"
    ).eq("id", vaga_id).execute()
    if not existente.data:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")

    payload = {k: v for k, v in payload.items() if k not in ("id", "created_at", "created_by")}
    payload = _apply_automacao(sb, payload, current=existente.data[0])
    payload["updated_at"] = datetime.utcnow().isoformat()
    payload["updated_by"] = user.get("id")

    sb.table("rh_vagas").update(payload).eq("id", vaga_id).execute()

    detalhe = sb.table("rh_vagas").select(_SELECT).eq("id", vaga_id).single().execute()
    return _serialize(detalhe.data)


@router.delete("/{vaga_id}")
def excluir_vaga(vaga_id: str, user=Depends(_require_rh)):
    sb = get_supabase()
    existente = sb.table("rh_vagas").select("id").eq("id", vaga_id).execute()
    if not existente.data:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    sb.table("rh_vagas").delete().eq("id", vaga_id).execute()
    return {"ok": True}


# ── Template / import de planilha ─────────────────────────────────────────────

@router.get("/template")
def baixar_template(user=Depends(_require_rh)):
    from fastapi.responses import StreamingResponse
    from services.excel_template import gerar_template

    buffer = gerar_template(get_supabase())
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="modelo_controle_de_vagas.xlsx"'},
    )


@router.post("/import")
async def importar_planilha(arquivo: UploadFile = File(...), user=Depends(_require_rh)):
    from services.excel_import import importar_planilha as _importar

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    sb = get_supabase()
    resultado = _importar(sb, conteudo, arquivo.filename, user)
    return resultado

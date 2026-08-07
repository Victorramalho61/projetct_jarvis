"""CRUD genérico das listas suspensas do módulo de RH."""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/rh/lookups")
log = logging.getLogger(__name__)

_ROLES = ("admin", "rh")


def _require_rh(user=Depends(require_role(*_ROLES))):
    return user


# tipo (segmento da URL) -> (tabela, coluna do nome, campos extras aceitos, coluna FK em rh_vagas usada p/ checar "em uso")
LOOKUP_CONFIG: dict[str, dict[str, Any]] = {
    "empresas":      {"table": "rh_empresas",        "name_col": "nome",  "extra": ["prefixo_requisicao"], "fk_col": "empresa_id"},
    "ufs":           {"table": "rh_ufs",              "name_col": "sigla", "extra": [],                     "fk_col": None},
    "alocacoes":     {"table": "rh_alocacoes",        "name_col": "nome",  "extra": [],                     "fk_col": "alocacao_id"},
    "tipos-contrato":{"table": "rh_tipos_contrato",   "name_col": "nome",  "extra": [],                     "fk_col": "tipo_contrato_id"},
    "tipos-vaga":    {"table": "rh_tipos_vaga",       "name_col": "nome",  "extra": [],                     "fk_col": "tipo_vaga_id"},
    "cargos":        {"table": "rh_cargos",           "name_col": "nome",  "extra": ["nivel_padrao_id"],    "fk_col": "cargo_id"},
    "niveis":        {"table": "rh_niveis",           "name_col": "nome",  "extra": [],                     "fk_col": "nivel_id"},
    "hierarquias":   {"table": "rh_hierarquias",      "name_col": "nome",  "extra": [],                     "fk_col": "hierarquia_id"},
    "secoes":        {"table": "rh_secoes",           "name_col": "nome",  "extra": [],                     "fk_col": "secao_id"},
    "status":        {"table": "rh_status_vaga",      "name_col": "nome",  "extra": ["em_aberto", "concluido"], "fk_col": "status_id"},
    "modalidades":   {"table": "rh_modalidades",      "name_col": "nome",  "extra": [],                     "fk_col": "modalidade_id"},
    "analistas":     {"table": "rh_analistas",        "name_col": "nome",  "extra": [],                     "fk_col": "responsavel_id"},
    "requisitantes": {"table": "rh_requisitantes",    "name_col": "nome",  "extra": [],                     "fk_col": "requisitante_id"},
    "etapas":        {"table": "rh_etapas_processo",  "name_col": "nome",  "extra": ["ordem", "secao_responsavel_id"], "fk_col": "etapa_atual_id"},
    "perfis-calculo": {"table": "rh_perfis_calculo",  "name_col": "nome",  "extra": [
        "vale_transporte", "vale_alimentacao", "seguro_vida", "plano_saude",
        "uniforme", "cracha_cordao", "aso", "insalubridade", "periculosidade",
        "aparelhos_eletronicos", "outros_creditos", "taxa_administrativa",
        "pct_inss", "pct_fgts", "pct_multa_fgts", "fgts_base_com_provisoes",
    ], "fk_col": "perfil_calculo_id"},
}


def _config(tipo: str) -> dict[str, Any]:
    cfg = LOOKUP_CONFIG.get(tipo)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Lista '{tipo}' não existe")
    return cfg


@router.get("")
def list_tipos(user=Depends(_require_rh)):
    return sorted(LOOKUP_CONFIG.keys())


@router.get("/{tipo}")
def list_itens(tipo: str, user=Depends(_require_rh)):
    cfg = _config(tipo)
    sb = get_supabase()
    order_col = "ordem" if tipo == "etapas" else cfg["name_col"]
    resp = sb.table(cfg["table"]).select("*").order(order_col).execute()
    return resp.data or []


@router.post("/{tipo}")
def criar_item(tipo: str, payload: dict = Body(...), user=Depends(_require_rh)):
    cfg = _config(tipo)
    nome = (payload.get(cfg["name_col"]) or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail=f"Campo '{cfg['name_col']}' é obrigatório")

    sb = get_supabase()
    existente = sb.table(cfg["table"]).select("id").eq(cfg["name_col"], nome).execute()
    if existente.data:
        raise HTTPException(status_code=409, detail="Esse item já existe na lista")

    row = {cfg["name_col"]: nome}
    for campo in cfg["extra"]:
        if campo in payload:
            row[campo] = payload[campo]

    resp = sb.table(cfg["table"]).insert(row).execute()
    return resp.data[0] if resp.data else row


@router.patch("/{tipo}/{item_id}")
def editar_item(tipo: str, item_id: str, payload: dict = Body(...), user=Depends(_require_rh)):
    cfg = _config(tipo)
    sb = get_supabase()
    row: dict[str, Any] = {}
    if cfg["name_col"] in payload:
        row[cfg["name_col"]] = payload[cfg["name_col"]]
    for campo in cfg["extra"]:
        if campo in payload:
            row[campo] = payload[campo]
    if not row:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    resp = sb.table(cfg["table"]).update(row).eq("id", item_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    return resp.data[0]


@router.delete("/{tipo}/{item_id}")
def excluir_item(tipo: str, item_id: str, user=Depends(_require_rh)):
    cfg = _config(tipo)
    sb = get_supabase()

    item = sb.table(cfg["table"]).select("id").eq("id", item_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    if cfg["fk_col"]:
        em_uso = sb.table("rh_vagas").select("id").eq(cfg["fk_col"], item_id).limit(1).execute()
        if em_uso.data:
            raise HTTPException(
                status_code=409,
                detail="Não é possível remover: este item está em uso em uma ou mais vagas cadastradas",
            )

    sb.table(cfg["table"]).delete().eq("id", item_id).execute()
    return {"ok": True}

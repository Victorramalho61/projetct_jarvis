"""
Conferência: documentos fiscais (NFe/CTe) sincronizados no Jarvis sem correspondência no Benner.

Escopo: só NFe/CTe, comparados por chave de acesso (44 dígitos).
NFSe fica fora — o Benner corporativo não guarda chave de acesso de NFSe (Portal Nacional,
50 dígitos) na tabela FN_DOCUMENTONFE, então não dá pra comparar com confiança.
Visão agregada: todas as empresas, sem filtro de período (mesmo padrão do dashboard NFSe).
"""
import csv
import io
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from lxml import etree

from auth import get_current_user
from db import get_mssql, get_supabase

router = APIRouter(prefix="/api/fiscal", tags=["benner-reconciliation"])

_logger = logging.getLogger(__name__)

_TTL = 1800  # 30 min — comparação é cara (varre toda a tabela Benner), dado muda pouco
_cache: dict | None = None
_cache_at: float = 0.0

_FIELDS = [
    "chave_acesso", "tipo", "numero", "data_emissao",
    "emitente_nome", "valor_total", "status", "company_id",
]
_SELECT_FIELDS = _FIELDS + ["xml_content"]


def _fetch_fiscal_docs() -> list[dict]:
    sb = get_supabase()
    rows: list[dict] = []
    start = 0
    page = 1000
    while True:
        batch = (
            sb.table("fiscal_documents")
            .select(",".join(_SELECT_FIELDS))
            .in_("tipo", ["NFe", "CTe"])
            .not_.is_("chave_acesso", "null")
            .range(start, start + page - 1)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return rows


def _xpath_text(root, path: str) -> str:
    r = root.xpath(path)
    return r[0].text.strip() if r and r[0].text else ""


def _parse_header_from_xml(xml_str: str) -> dict:
    """Extrai numero/emitente_nome/data_emissao/valor_total direto do XML via local-name()
    (ignora namespace, robusto a NFe solta ou envolvida em nfeProc/cteProc)."""
    try:
        root = etree.fromstring(xml_str.encode("utf-8"))
    except Exception:
        return {}
    numero = (
        _xpath_text(root, ".//*[local-name()='ide']/*[local-name()='nNF']")
        or _xpath_text(root, ".//*[local-name()='ide']/*[local-name()='nCT']")
    )
    emit_nome = _xpath_text(root, ".//*[local-name()='emit']/*[local-name()='xNome']")
    data = (
        _xpath_text(root, ".//*[local-name()='ide']/*[local-name()='dhEmi']")
        or _xpath_text(root, ".//*[local-name()='ide']/*[local-name()='dEmi']")
    )
    valor = (
        _xpath_text(root, ".//*[local-name()='ICMSTot']/*[local-name()='vNF']")
        or _xpath_text(root, ".//*[local-name()='vTPrest']")
    )
    return {
        "numero": numero,
        "emitente_nome": emit_nome,
        "data_emissao": data[:10] if data else "",
        "valor_total": float(valor) if valor else None,
    }


def _enrich_from_xml(doc: dict) -> dict:
    """Alguns documentos (fonte=sefaz, ainda não conferidos) têm as colunas de cabeçalho
    (numero/emitente_nome/data_emissao/valor_total) vazias — só o xml_content é populado
    nesse estágio do fluxo. Preenche a partir do XML pra exibição, sem tocar no banco."""
    xml = doc.pop("xml_content", None)
    if not xml or all(doc.get(f) for f in ("numero", "emitente_nome", "data_emissao", "valor_total")):
        return doc
    parsed = _parse_header_from_xml(xml)
    for f in ("numero", "emitente_nome", "data_emissao", "valor_total"):
        if not doc.get(f) and parsed.get(f):
            doc[f] = parsed[f]
    return doc


def _fetch_benner_chaves() -> set[str]:
    conn = get_mssql()
    try:
        cur = conn.cursor()
        cur.execute("SELECT CHAVE FROM dbo.FN_DOCUMENTONFE WHERE LEN(CHAVE) = 44")
        return {r["CHAVE"] for r in cur.fetchall() if r.get("CHAVE")}
    finally:
        conn._conn.close()


def _company_names() -> dict[str, str]:
    sb = get_supabase()
    rows = sb.table("fiscal_companies").select("id,nome").execute().data or []
    return {r["id"]: r["nome"] for r in rows}


def _compute() -> dict:
    docs = _fetch_fiscal_docs()
    benner_chaves = _fetch_benner_chaves()
    names = _company_names()

    not_in_benner = []
    for d in docs:
        if d["chave_acesso"] not in benner_chaves:
            item = _enrich_from_xml(dict(d))
            item["company_nome"] = names.get(d.get("company_id"), "")
            not_in_benner.append(item)

    not_in_benner.sort(key=lambda d: d.get("data_emissao") or "", reverse=True)

    return {
        "total_nfe_cte": len(docs),
        "not_in_benner_count": len(not_in_benner),
        "not_in_benner": not_in_benner,
    }


def _get_cached() -> dict:
    global _cache, _cache_at
    now = time.monotonic()
    if _cache is not None and now - _cache_at < _TTL:
        return _cache
    data = _compute()
    _cache = data
    _cache_at = now
    return data


@router.get("/benner-reconciliation/nfe-cte")
def get_benner_reconciliation(
    refresh: bool = Query(False, description="Ignora cache e recalcula agora"),
    _user: dict = Depends(get_current_user),
):
    if refresh:
        global _cache
        _cache = None
    try:
        return _get_cached()
    except Exception:
        _logger.exception("benner_reconciliation: falha ao consultar Benner")
        raise


@router.get("/benner-reconciliation/nfe-cte/export")
def export_benner_reconciliation_csv(_user: dict = Depends(get_current_user)):
    data = _get_cached()
    fieldnames = ["company_nome"] + _FIELDS

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data["not_in_benner"])

    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nao_encontrados_benner_nfe_cte.csv"'},
    )

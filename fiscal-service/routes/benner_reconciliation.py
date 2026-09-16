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
import re
import threading
import time
from datetime import date as _date, datetime as _datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from lxml import etree

from auth import get_current_user
from db import get_mssql, get_supabase

router = APIRouter(prefix="/api/fiscal", tags=["benner-reconciliation"])

_logger = logging.getLogger(__name__)

# Consulta cara (varre tabelas do Benner com milhões de linhas, sem índice bom pro nosso
# filtro — já visto levando 10s a mais de 1 min dependendo da carga do SQL Server no
# momento). TTL longo + revalidação em segundo plano: uma carga de página normal (sem
# refresh=true) nunca fica esperando o recálculo — recebe o último resultado pronto (a
# única exceção é a 1a chamada depois do serviço subir, coberta pelo pré-aquecimento do
# scheduler em services/scheduler.py). O botão "Atualizar" (refresh=true) continua síncrono
# de propósito: o usuário pediu dado fresco agora e espera o spinner.
_TTL = 1800  # 30 min — dado muda pouco


class _StaleCache:
    """Cache com revalidação em segundo plano: serve o último dado pronto na hora
    (mesmo vencido) e dispara o recálculo numa thread à parte, sem nunca fazer o
    request do usuário esperar — exceto na 1a carga do processo (sem nada pra servir)
    ou quando `force=True` (botão "Atualizar", que deve mesmo bloquear)."""

    def __init__(self, compute_fn, ttl: float = _TTL):
        self._compute_fn = compute_fn
        self._ttl = ttl
        self._data: dict | None = None
        self._at: float = 0.0
        self._lock = threading.Lock()
        self._refreshing = False

    def get(self, force: bool = False) -> dict:
        if force:
            self._refresh_blocking()
            return self._data
        if self._data is None:
            self._refresh_blocking()
            return self._data
        if time.monotonic() - self._at >= self._ttl:
            self._refresh_background()
        return self._data

    def _refresh_blocking(self) -> None:
        requested_at = time.monotonic()
        with self._lock:
            # Se outra requisição já recalculou enquanto esperávamos o lock (dois
            # cliques em "Atualizar", ou request concorrente com o pré-aquecimento),
            # aproveita o resultado dela em vez de recalcular de novo à toa.
            if self._at > requested_at:
                return
            self._data = self._compute_fn()
            self._at = time.monotonic()

    def _refresh_background(self) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True

        def _run():
            try:
                self._data = self._compute_fn()
                self._at = time.monotonic()
            except Exception:
                _logger.exception("benner_reconciliation: falha ao atualizar cache em segundo plano")
            finally:
                self._refreshing = False

        threading.Thread(target=_run, daemon=True).start()


def _filter_by_company(data: dict, list_key: str, count_key: str, total_key: str, total_by_company_key: str, company_id: str | None) -> dict:
    if not company_id:
        return data
    filtered = [d for d in data[list_key] if d.get("company_id") == company_id]
    out = dict(data)
    out[list_key] = filtered
    out[count_key] = len(filtered)
    out[total_key] = data[total_by_company_key].get(company_id, 0)
    return out


# A tela só renderiza as 100 primeiras linhas (busca client-side refina o restante) e
# tem exportação CSV pra ver tudo — devolver a lista inteira (pode passar de 40MB de
# JSON quando a maior parte dos documentos não bate com o Benner) deixa a tela lenta à
# toa. Cap só no endpoint da tela; o /export sempre recebe a lista completa.
_JSON_LIST_CAP = 500


def _cap_json_list(data: dict, list_key: str, limit: int = _JSON_LIST_CAP) -> dict:
    if len(data[list_key]) <= limit:
        return data
    out = dict(data)
    out[list_key] = data[list_key][:limit]
    return out

def _only_digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")

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

    total_by_company: dict[str, int] = {}
    for d in docs:
        cid = d.get("company_id")
        if cid:
            total_by_company[cid] = total_by_company.get(cid, 0) + 1

    return {
        "total_nfe_cte": len(docs),
        "total_nfe_cte_by_company": total_by_company,
        "not_in_benner_count": len(not_in_benner),
        "not_in_benner": not_in_benner,
    }


# ── NFSe recebida: comparação aproximada (sem chave confiável) ──────────────────
# Levanta as NFSe emitidas CONTRA a VTC e demais empresas (ou seja, serviços que
# terceiros nos venderam) sem o lançamento financeiro (contas a pagar) correspondente
# no Benner. NFSe que NÓS emitimos (nossa receita) fica fora de propósito — não tem
# lançamento de entrada mesmo, então comparar não diria nada útil.
# Critério: CNPJ do emitente/fornecedor (via GN_PESSOAS) + valor (±R$0,05) + janela de
# data (±30 dias) contra lançamentos de entrada (ENTRADASAIDA='E') em FN_DOCUMENTOS.
# É "melhor esforço": pode gerar falso positivo (coincidência de valor/data com outro
# lançamento do mesmo fornecedor) ou falso negativo (lançamento fora da janela).
# Controladoria deve validar manualmente os casos antes de tratar como divergência real.
_NFSE_MIN_DATE = "2025-01-01"
_NFSE_LANCAMENTOS_DESDE = "2024-12-01"  # folga de 30 dias antes do início do escopo
_NFSE_MATCH_WINDOW_DAYS = 30
_NFSE_VALUE_TOLERANCE = 0.05

_NFSE_FIELDS = [
    "chave_acesso", "numero", "data_emissao", "emitente_nome", "emitente_cnpj",
    "destinatario_nome", "valor_total", "status", "company_id",
]

def _fetch_nfse_recebidas() -> list[dict]:
    sb = get_supabase()
    rows: list[dict] = []
    start = 0
    page = 1000
    while True:
        batch = (
            sb.table("fiscal_documents")
            .select(",".join(_NFSE_FIELDS))
            .eq("tipo", "NFSe")
            .eq("direcao", "recebida")
            .gte("data_emissao", _NFSE_MIN_DATE)
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


def _fetch_filial_handles() -> list[int]:
    """Handles das FILIAIS do Benner que correspondem às empresas rastreadas no fiscal-service."""
    sb = get_supabase()
    companies = sb.table("fiscal_companies").select("cnpj").execute().data or []
    wanted = {_only_digits(c["cnpj"]) for c in companies if c.get("cnpj")}

    conn = get_mssql()
    try:
        cur = conn.cursor()
        cur.execute("SELECT HANDLE, CGC FROM dbo.FILIAIS")
        rows = cur.fetchall()
    finally:
        conn._conn.close()
    return [r["HANDLE"] for r in rows if _only_digits(r.get("CGC")) in wanted]


def _fetch_gn_pessoas_cnpj_map() -> dict[str, list[int]]:
    conn = get_mssql()
    try:
        cur = conn.cursor()
        cur.execute("SELECT HANDLE, CGCCPF FROM dbo.GN_PESSOAS WHERE CGCCPF IS NOT NULL")
        rows = cur.fetchall()
    finally:
        conn._conn.close()
    m: dict[str, list[int]] = {}
    for r in rows:
        cnpj = _only_digits(r.get("CGCCPF"))
        if cnpj:
            m.setdefault(cnpj, []).append(r["HANDLE"])
    return m


def _fetch_benner_lancamentos_entrada(filial_handles: list[int]) -> dict[int, list[tuple]]:
    """Lançamentos de ENTRADA (contas a pagar) do Benner — o que deveria existir quando
    um fornecedor emite NFSe contra a gente."""
    if not filial_handles:
        return {}
    conn = get_mssql()
    try:
        cur = conn.cursor()
        placeholders = ",".join(str(int(h)) for h in filial_handles)
        cur.execute(
            "SELECT PESSOA, DATAEMISSAO, VALORNOMINAL FROM dbo.FN_DOCUMENTOS "
            f"WHERE FILIAL IN ({placeholders}) AND ENTRADASAIDA='E' AND DATAEMISSAO >= %s",
            (_NFSE_LANCAMENTOS_DESDE,),
        )
        rows = cur.fetchall()
    finally:
        conn._conn.close()
    m: dict[int, list[tuple]] = {}
    for r in rows:
        if r.get("PESSOA") is None or r.get("DATAEMISSAO") is None:
            continue
        m.setdefault(r["PESSOA"], []).append((r.get("VALORNOMINAL") or 0.0, r["DATAEMISSAO"].date()))
    return m


def _parse_date(s) -> "_date | None":
    if not s:
        return None
    if isinstance(s, _date):
        return s
    try:
        return _datetime.fromisoformat(str(s)[:10]).date()
    except ValueError:
        return None


def _compute_nfse_aproximado() -> dict:
    docs = _fetch_nfse_recebidas()
    cnpj_pessoa = _fetch_gn_pessoas_cnpj_map()
    filial_handles = _fetch_filial_handles()
    lancamentos = _fetch_benner_lancamentos_entrada(filial_handles)
    names = _company_names()

    not_in_benner = []
    for d in docs:
        cnpj = _only_digits(d.get("emitente_cnpj"))
        data_emissao = _parse_date(d.get("data_emissao"))
        valor = d.get("valor_total") or 0.0
        handles = cnpj_pessoa.get(cnpj, [])

        found = False
        if handles and data_emissao:
            for h in handles:
                for v, dt in lancamentos.get(h, []):
                    if abs(v - valor) <= _NFSE_VALUE_TOLERANCE and abs((dt - data_emissao).days) <= _NFSE_MATCH_WINDOW_DAYS:
                        found = True
                        break
                if found:
                    break

        if not found:
            item = dict(d)
            item["company_nome"] = names.get(d.get("company_id"), "")
            item["motivo"] = (
                "Fornecedor sem cadastro localizado no Benner" if not handles
                else "Sem lançamento compatível (mesmo valor, ±30 dias)"
            )
            not_in_benner.append(item)

    not_in_benner.sort(key=lambda d: d.get("data_emissao") or "", reverse=True)

    total_by_company: dict[str, int] = {}
    for d in docs:
        cid = d.get("company_id")
        if cid:
            total_by_company[cid] = total_by_company.get(cid, 0) + 1

    return {
        "aproximado": True,
        "criterio": "CNPJ do fornecedor (emitente) + valor (±R$0,05) + data (±30 dias) — sem chave de acesso confiável",
        "desde": _NFSE_MIN_DATE,
        "total_nfse_recebida": len(docs),
        "total_nfse_recebida_by_company": total_by_company,
        "not_in_benner_count": len(not_in_benner),
        "not_in_benner": not_in_benner,
    }


_cache_nfse = _StaleCache(_compute_nfse_aproximado)


@router.get("/benner-reconciliation/nfse-recebida")
def get_benner_reconciliation_nfse(
    refresh: bool = Query(False, description="Ignora cache e recalcula agora (bloqueia até terminar)"),
    company_id: Optional[str] = Query(None, description="Filtra o resultado por empresa"),
    _user: dict = Depends(get_current_user),
):
    try:
        data = _cache_nfse.get(force=refresh)
        data = _filter_by_company(
            data, "not_in_benner", "not_in_benner_count",
            "total_nfse_recebida", "total_nfse_recebida_by_company", company_id,
        )
        return _cap_json_list(data, "not_in_benner")
    except Exception:
        _logger.exception("benner_reconciliation: falha ao consultar Benner (NFSe)")
        raise


@router.get("/benner-reconciliation/nfse-recebida/export")
def export_benner_reconciliation_nfse_csv(
    company_id: Optional[str] = Query(None),
    _user: dict = Depends(get_current_user),
):
    data = _filter_by_company(
        _cache_nfse.get(), "not_in_benner", "not_in_benner_count",
        "total_nfse_recebida", "total_nfse_recebida_by_company", company_id,
    )
    fieldnames = ["company_nome"] + _NFSE_FIELDS + ["motivo"]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data["not_in_benner"])

    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nao_encontrados_benner_nfse_recebida.csv"'},
    )


_cache = _StaleCache(_compute)


@router.get("/benner-reconciliation/nfe-cte")
def get_benner_reconciliation(
    refresh: bool = Query(False, description="Ignora cache e recalcula agora (bloqueia até terminar)"),
    company_id: Optional[str] = Query(None, description="Filtra o resultado por empresa"),
    _user: dict = Depends(get_current_user),
):
    try:
        data = _cache.get(force=refresh)
        data = _filter_by_company(
            data, "not_in_benner", "not_in_benner_count",
            "total_nfe_cte", "total_nfe_cte_by_company", company_id,
        )
        return _cap_json_list(data, "not_in_benner")
    except Exception:
        _logger.exception("benner_reconciliation: falha ao consultar Benner")
        raise


@router.get("/benner-reconciliation/nfe-cte/export")
def export_benner_reconciliation_csv(
    company_id: Optional[str] = Query(None),
    _user: dict = Depends(get_current_user),
):
    data = _filter_by_company(
        _cache.get(), "not_in_benner", "not_in_benner_count",
        "total_nfe_cte", "total_nfe_cte_by_company", company_id,
    )
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

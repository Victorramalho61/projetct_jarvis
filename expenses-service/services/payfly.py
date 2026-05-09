"""
PayFly — investimentos no Benner (Empresa = 03).
Captura:
  1) HISTORICO LIKE '%PAYFLY%'  → categoria 'PayFly'
  2) Fornecedores de dev (Hiperlink, Next Squad) → categoria 'Desenvolvimento'
  3) Infraestrutura cloud (Amazon / AWS) → categoria 'Infraestrutura'
"""
import logging
from datetime import date, datetime
from typing import Any

from cachetools import TTLCache
from db import get_sql_connection

logger = logging.getLogger(__name__)

_investments_cache: TTLCache = TTLCache(maxsize=10, ttl=3600)  # 1h — Benner não muda com frequência
_detail_cache: TTLCache = TTLCache(maxsize=5, ttl=3600)

_PJ_COLLABORATORS = {
    "KARLA SANJULIO",
    "RICARDO GONÇALVES",
    "MARCOS FELIPE CHAVES BITENCOURT",
}

# Mapeamento de categoria por padrão de nome de fornecedor
_CATEGORIA_RULES = [
    (["HIPERLINK", "NEXT SQUAD", "NEXTSQUAD", "NEXT_SQUAD"], "Desenvolvimento"),
    (["AMAZON WEB SERVICES", "AWS"], "Infraestrutura"),
]


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso_date(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return str(v)[:10]


def _classify_categoria(nome: str) -> str:
    upper = (nome or "").upper()
    for patterns, cat in _CATEGORIA_RULES:
        if any(p in upper for p in patterns):
            return cat
    return "PayFly"


# ── SQL filter helpers ─────────────────────────────────────────────────────────

# Fornecedores de desenvolvimento (by supplier name)
_DEV_SUPPLIERS = (
    "UPPER(PES.NOME) LIKE '%HIPERLINK%' OR UPPER(PES.NOME) LIKE '%HIPER LINK%'"
    " OR UPPER(PES.NOME) LIKE '%NEXT%SQUAD%' OR UPPER(PES.NOME) LIKE '%NEXTSQUAD%'"
    " OR UPPER(PES.NOME) LIKE '%NEXT SQUAD%'"
)

# Infraestrutura cloud — apenas AWS (exclui Amazon Plaza, Amazon Service, Amazon Varejo, etc.)
_INFRA_SUPPLIERS = "UPPER(PES.NOME) LIKE '%AMAZON WEB SERVICES%' OR UPPER(PES.NOME) LIKE '%AWS%' OR UPPER(DOC.HISTORICO) LIKE '%AWS%'"

# Exclusão de hotéis/hospedagem e lançamentos de relocação (RLOC)
_EXCLUSION = """NOT (
    UPPER(PES.NOME) LIKE '%HOTEL%'
    OR UPPER(PES.NOME) LIKE '%HOTEIS%'
    OR UPPER(PES.NOME) LIKE '%POUSADA%'
    OR UPPER(PES.NOME) LIKE '%RESORT%'
    OR UPPER(PES.NOME) LIKE '%HOSTEL%'
    OR UPPER(PES.NOME) LIKE '% INN%'
    OR UPPER(PES.NOME) LIKE '%SUITES%'
    OR UPPER(PES.NOME) LIKE '%HOSPEDAGEM%'
    OR UPPER(PES.NOME) LIKE '%APART HOTEL%'
    OR UPPER(PES.NOME) LIKE '%APARTHOTEL%'
    OR UPPER(PES.NOME) LIKE '%ADMINISTRACAO DE HOT%'
    OR UPPER(DOC.HISTORICO) LIKE '%RLOC%'
)"""

_PAYFLY_FILTER = f"""(
    UPPER(DOC.HISTORICO) LIKE '%PAYFLY%'
    OR {_DEV_SUPPLIERS}
    OR {_INFRA_SUPPLIERS}
)
AND {_EXCLUSION}"""


# ── Queries ────────────────────────────────────────────────────────────────────

_BY_SUPPLIER_QUERY = """
SELECT
    PES.NOME                                                              AS FORNECEDOR,
    PES.CODIGO                                                            AS COD_FORNECEDOR,
    SUM(PAR.VALOR)                                                        AS TOTAL,
    SUM(CASE WHEN PAR.DATALIQUIDACAO IS NOT NULL THEN PAR.VALOR ELSE 0 END) AS TOTAL_PAGO,
    SUM(CASE WHEN PAR.DATALIQUIDACAO IS NULL     THEN PAR.VALOR ELSE 0 END) AS TOTAL_PENDENTE,
    COUNT(*)                                                              AS QTD,
    COUNT(CASE WHEN PAR.DATALIQUIDACAO IS NOT NULL THEN 1 END)           AS QTD_PAGO,
    MIN(PAR.DATAVENCIMENTO)                                               AS PRIMEIRA_DATA,
    MAX(PAR.DATAVENCIMENTO)                                               AS ULTIMA_DATA
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE PAR.EMPRESA = 3
  AND DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND {payfly_filter}
  {{year_filter}}
GROUP BY PES.NOME, PES.CODIGO
ORDER BY TOTAL DESC
""".format(payfly_filter=_PAYFLY_FILTER)

_SERIES_QUERY = """
SELECT
    LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)                     AS COMPETENCIA,
    SUM(PAR.VALOR)                                                           AS TOTAL,
    SUM(CASE WHEN PAR.DATALIQUIDACAO IS NOT NULL THEN PAR.VALOR ELSE 0 END) AS TOTAL_PAGO,
    COUNT(*)                                                                 AS QTD
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE PAR.EMPRESA = 3
  AND DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND {payfly_filter}
  {{year_filter}}
GROUP BY LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)
ORDER BY COMPETENCIA
""".format(payfly_filter=_PAYFLY_FILTER)

_DETAIL_QUERY = """
SELECT
    PAR.HANDLE                                                               AS AP,
    PES.NOME                                                                 AS FORNECEDOR,
    DOC.HISTORICO,
    PAR.DATAVENCIMENTO,
    PAR.DATALIQUIDACAO,
    PAR.VALOR,
    CASE WHEN PAR.DATALIQUIDACAO IS NOT NULL THEN 'pago' ELSE 'pendente' END AS STATUS_PAR,
    ISNULL(FIL.NOME, '')                                                     AS FILIAL
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
LEFT  JOIN FILIAIS        FIL WITH (NOLOCK) ON FIL.HANDLE = PAR.FILIAL
WHERE PAR.EMPRESA = 3
  AND DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND {payfly_filter}
  {{year_filter}}
ORDER BY PAR.DATAVENCIMENTO DESC
""".format(payfly_filter=_PAYFLY_FILTER)


def _year_filter(year: int | None) -> str:
    if year:
        return f"AND YEAR(PAR.DATAVENCIMENTO) = {int(year)}"
    return ""


def fetch_payfly_investments(year: int | None = None) -> dict:
    """Agrupa gastos PayFly por fornecedor + série mensal."""
    yf = _year_filter(year)
    cache_key = f"investments_{year}"
    if cache_key in _investments_cache:
        return _investments_cache[cache_key]

    conn = get_sql_connection()
    try:
        cur = conn.cursor()

        # Por fornecedor
        cur.execute(_BY_SUPPLIER_QUERY.format(year_filter=yf))
        cols = [d[0].lower() for d in cur.description]
        fornecedores = []
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            nome = r.get("fornecedor") or ""
            nome_upper = nome.upper().strip()
            is_pj = any(nome_upper == c for c in _PJ_COLLABORATORS)
            fornecedores.append({
                "fornecedor":      nome,
                "cod_fornecedor":  str(r.get("cod_fornecedor") or ""),
                "categoria":       _classify_categoria(nome),
                "total":           _to_float(r["total"]) or 0.0,
                "total_pago":      _to_float(r["total_pago"]) or 0.0,
                "total_pendente":  _to_float(r["total_pendente"]) or 0.0,
                "qtd":             int(r["qtd"] or 0),
                "qtd_pago":        int(r.get("qtd_pago") or 0),
                "primeira_data":   _iso_date(r.get("primeira_data")),
                "ultima_data":     _iso_date(r.get("ultima_data")),
                "is_pj_collaborator": is_pj,
            })

        # Série mensal
        cur.execute(_SERIES_QUERY.format(year_filter=yf))
        cols2 = [d[0].lower() for d in cur.description]
        serie = []
        for row in cur.fetchall():
            r = dict(zip(cols2, row))
            serie.append({
                "competencia": str(r["competencia"]),
                "total":       _to_float(r["total"]) or 0.0,
                "total_pago":  _to_float(r["total_pago"]) or 0.0,
                "qtd":         int(r["qtd"] or 0),
            })

        total = sum(f["total"] for f in fornecedores)
        total_pago = sum(f["total_pago"] for f in fornecedores)

        # Totais por categoria
        categorias: dict[str, float] = {}
        for f in fornecedores:
            cat = f["categoria"]
            categorias[cat] = categorias.get(cat, 0.0) + f["total"]

        result = {
            "fornecedores": fornecedores,
            "serie_mensal": serie,
            "totais": {
                "total":             total,
                "total_pago":        total_pago,
                "total_pendente":    total - total_pago,
                "qtd_fornecedores":  len(fornecedores),
            },
            "por_categoria": [
                {"categoria": cat, "total": round(val, 2)}
                for cat, val in sorted(categorias.items(), key=lambda x: -x[1])
            ],
        }
        _investments_cache[cache_key] = result
        return result
    finally:
        conn.close()


def fetch_payfly_investments_detail(year: int | None = None) -> list[dict]:
    """Lista detalhada de todos os documentos PayFly para drill-down."""
    yf = _year_filter(year)
    cache_key = f"detail_{year}"
    if cache_key in _detail_cache:
        return _detail_cache[cache_key]

    conn = get_sql_connection()
    try:
        cur = conn.cursor()
        cur.execute(_DETAIL_QUERY.format(year_filter=yf))
        cols = [d[0].lower() for d in cur.description]
        rows = []
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            nome = r.get("fornecedor") or ""
            rows.append({
                "ap":             int(r["ap"]) if r["ap"] else None,
                "fornecedor":     nome,
                "categoria":      _classify_categoria(nome),
                "historico":      r.get("historico") or "",
                "datavencimento": _iso_date(r.get("datavencimento")),
                "dataliquidacao": _iso_date(r.get("dataliquidacao")),
                "valor":          _to_float(r["valor"]) or 0.0,
                "status_par":     r.get("status_par") or "pendente",
                "filial":         r.get("filial") or "",
            })
        _detail_cache[cache_key] = rows
        return rows
    finally:
        conn.close()

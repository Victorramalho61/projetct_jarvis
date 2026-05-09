"""
PayFly — investimentos no Benner.
Captura três origens:
  1) EMPRESA=3 + HISTORICO LIKE '%PAYFLY%'  → categoria 'PayFly'
  2) Fornecedores de dev (Hiperlink/NextSquad) em QUALQUER empresa  → 'Desenvolvimento'
  3) Infraestrutura cloud (AWS) na EMPRESA=3  → 'Infraestrutura'
"""
import logging
from datetime import date, datetime
from typing import Any

from cachetools import TTLCache
from db import get_sql_connection

logger = logging.getLogger(__name__)

_investments_cache: TTLCache = TTLCache(maxsize=10, ttl=3600)
_detail_cache: TTLCache = TTLCache(maxsize=5, ttl=3600)

_PJ_COLLABORATORS = {
    "KARLA SANJULIO",
    "RICARDO GONÇALVES",
    "MARCOS FELIPE CHAVES BITENCOURT",
}

_CATEGORIA_RULES = [
    (["HIPERLINK", "HIPER LINK", "NEXT SQUAD", "NEXTSQUAD"], "Desenvolvimento"),
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


# ── SQL building blocks ────────────────────────────────────────────────────────

# Fornecedores de dev — todos os padrões de nome, qualquer empresa
_DEV_NAME_MATCH = """(
    UPPER(PES.NOME) LIKE '%HIPERLINK%'
    OR UPPER(PES.NOME) LIKE '%HIPER LINK%'
    OR UPPER(PES.NOME) LIKE '%NEXTSQUAD%'
    OR UPPER(PES.NOME) LIKE '%NEXT SQUAD%'
    OR UPPER(PES.NOME) LIKE '%NEXT%SQUAD%'
    OR UPPER(DOC.HISTORICO) LIKE '%NEXTSQUAD%'
    OR UPPER(DOC.HISTORICO) LIKE '%NEXT SQUAD%'
    OR UPPER(DOC.HISTORICO) LIKE '%HIPERLINK%'
    OR UPPER(DOC.HISTORICO) LIKE '%HIPER LINK%'
)"""

# Gastos PayFly/AWS — apenas empresa 3 (ledger PayFly)
_PAYFLY_EMPRESA3 = """(
    PAR.EMPRESA = 3
    AND (
        UPPER(DOC.HISTORICO) LIKE '%PAYFLY%'
        OR UPPER(PES.NOME) LIKE '%AMAZON WEB SERVICES%'
        OR UPPER(PES.NOME) LIKE '%AWS%'
        OR UPPER(DOC.HISTORICO) LIKE '%AWS%'
    )
)"""

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

# Filtro composto: (PayFly empresa3 OU dev fornecedores qualquer empresa) E NÃO exclusões
_COMBINED_FILTER = f"({_PAYFLY_EMPRESA3} OR {_DEV_NAME_MATCH}) AND {_EXCLUSION}"


# ── Queries ────────────────────────────────────────────────────────────────────

_BY_SUPPLIER_QUERY = f"""
SELECT
    PES.NOME                   AS FORNECEDOR,
    PES.CODIGO                 AS COD_FORNECEDOR,
    SUM(PAR.VALOR)             AS TOTAL,
    COUNT(*)                   AS QTD,
    MIN(PAR.DATALIQUIDACAO)    AS PRIMEIRA_DATA,
    MAX(PAR.DATALIQUIDACAO)    AS ULTIMA_DATA,
    MAX(CASE WHEN UPPER(DOC.HISTORICO) LIKE '%CONTRATO%'
             OR   UPPER(DOC.HISTORICO) LIKE '%CSA/%'
             THEN 1 ELSE 0 END) AS TEM_CONTRATO
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND PAR.DATALIQUIDACAO IS NOT NULL
  AND {_COMBINED_FILTER}
  {{year_filter}}
GROUP BY PES.NOME, PES.CODIGO
ORDER BY TOTAL DESC
"""

# Comprometimentos: parcelas pendentes de contratos (DATALIQUIDACAO IS NULL)
_COMPROMETIMENTOS_QUERY = f"""
SELECT
    PES.NOME                          AS FORNECEDOR,
    SUM(PAR.VALOR)                    AS TOTAL_PENDENTE,
    COUNT(*)                          AS QTD,
    MIN(PAR.DATAVENCIMENTO)           AS PROXIMA_VENCIMENTO,
    MAX(PAR.DATAVENCIMENTO)           AS ULTIMA_VENCIMENTO
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND PAR.DATALIQUIDACAO IS NULL
  AND (UPPER(DOC.HISTORICO) LIKE '%CONTRATO%' OR UPPER(DOC.HISTORICO) LIKE '%CSA/%')
  AND {_COMBINED_FILTER}
GROUP BY PES.NOME
ORDER BY TOTAL_PENDENTE DESC
"""

_COMPROMETIMENTOS_DETAIL_QUERY = f"""
SELECT
    PES.NOME              AS FORNECEDOR,
    PAR.DATAVENCIMENTO,
    PAR.VALOR,
    LEFT(DOC.HISTORICO, 120) AS HISTORICO
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND PAR.DATALIQUIDACAO IS NULL
  AND (UPPER(DOC.HISTORICO) LIKE '%CONTRATO%' OR UPPER(DOC.HISTORICO) LIKE '%CSA/%')
  AND {_COMBINED_FILTER}
ORDER BY PES.NOME, PAR.DATAVENCIMENTO
"""

_SERIES_QUERY = f"""
SELECT
    LEFT(CONVERT(VARCHAR, PAR.DATALIQUIDACAO, 120), 7) AS COMPETENCIA,
    SUM(PAR.VALOR)                                      AS TOTAL,
    COUNT(*)                                            AS QTD
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND PAR.DATALIQUIDACAO IS NOT NULL
  AND {_COMBINED_FILTER}
  {{year_filter}}
GROUP BY LEFT(CONVERT(VARCHAR, PAR.DATALIQUIDACAO, 120), 7)
ORDER BY COMPETENCIA
"""

_DETAIL_QUERY = f"""
SELECT
    PAR.HANDLE              AS AP,
    PES.NOME                AS FORNECEDOR,
    DOC.HISTORICO,
    PAR.DATAVENCIMENTO,
    PAR.DATALIQUIDACAO,
    PAR.VALOR,
    'pago'                  AS STATUS_PAR,
    ISNULL(FIL.NOME, '')    AS FILIAL,
    PAR.EMPRESA             AS EMPRESA
FROM FN_PARCELAS     PAR WITH (NOLOCK)
INNER JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
INNER JOIN GN_PESSOAS    PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
LEFT  JOIN FILIAIS        FIL WITH (NOLOCK) ON FIL.HANDLE = PAR.FILIAL
WHERE DOC.ABRANGENCIA <> 'R'
  AND DOC.ENTRADASAIDA IN ('I', 'E')
  AND PAR.DATALIQUIDACAO IS NOT NULL
  AND {_COMBINED_FILTER}
  {{year_filter}}
ORDER BY PAR.DATALIQUIDACAO DESC
"""


def _year_filter(year: int | None) -> str:
    if year:
        return f"AND YEAR(PAR.DATALIQUIDACAO) = {int(year)}"
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
            tipo = "Contrato" if int(r.get("tem_contrato") or 0) == 1 else "Eventual"
            fornecedores.append({
                "fornecedor":      nome,
                "cod_fornecedor":  str(r.get("cod_fornecedor") or ""),
                "categoria":       _classify_categoria(nome),
                "tipo":            tipo,
                "total":           _to_float(r["total"]) or 0.0,
                "qtd":             int(r["qtd"] or 0),
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
                "qtd":         int(r["qtd"] or 0),
            })

        total = sum(f["total"] for f in fornecedores)

        categorias: dict[str, float] = {}
        tipos: dict[str, float] = {}
        for f in fornecedores:
            categorias[f["categoria"]] = categorias.get(f["categoria"], 0.0) + f["total"]
            tipos[f["tipo"]] = tipos.get(f["tipo"], 0.0) + f["total"]

        total_tipo = sum(tipos.values()) or 1
        por_tipo = [
            {"tipo": t, "total": round(v, 2), "pct": round(v / total_tipo * 100, 1)}
            for t, v in sorted(tipos.items(), key=lambda x: -x[1])
        ]

        result = {
            "fornecedores": fornecedores,
            "serie_mensal": serie,
            "totais": {
                "total":            total,
                "qtd_fornecedores": len(fornecedores),
            },
            "por_categoria": [
                {"categoria": cat, "total": round(val, 2)}
                for cat, val in sorted(categorias.items(), key=lambda x: -x[1])
            ],
            "por_tipo": por_tipo,
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
                "empresa":        str(r.get("empresa") or ""),
            })
        _detail_cache[cache_key] = rows
        return rows
    finally:
        conn.close()


_comprometimentos_cache: TTLCache = TTLCache(maxsize=5, ttl=3600)


def fetch_payfly_comprometimentos() -> list[dict]:
    """Parcelas pendentes de contratos — agrupadas por fornecedor com detalhes."""
    if "comprometimentos" in _comprometimentos_cache:
        return _comprometimentos_cache["comprometimentos"]

    conn = get_sql_connection()
    try:
        cur = conn.cursor()

        # Resumo por fornecedor
        cur.execute(_COMPROMETIMENTOS_QUERY)
        cols = [d[0].lower() for d in cur.description]
        resumo: dict[str, dict] = {}
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            nome = r.get("fornecedor") or ""
            resumo[nome] = {
                "fornecedor":        nome,
                "categoria":         _classify_categoria(nome),
                "total_pendente":    _to_float(r["total_pendente"]) or 0.0,
                "qtd":               int(r["qtd"] or 0),
                "proxima_vencimento": _iso_date(r.get("proxima_vencimento")),
                "ultima_vencimento":  _iso_date(r.get("ultima_vencimento")),
                "parcelas":          [],
            }

        # Detalhe por parcela
        cur.execute(_COMPROMETIMENTOS_DETAIL_QUERY)
        cols2 = [d[0].lower() for d in cur.description]
        for row in cur.fetchall():
            r = dict(zip(cols2, row))
            nome = r.get("fornecedor") or ""
            if nome in resumo:
                resumo[nome]["parcelas"].append({
                    "datavencimento": _iso_date(r.get("datavencimento")),
                    "valor":          _to_float(r["valor"]) or 0.0,
                    "historico":      (r.get("historico") or "")[:120],
                })

        result = sorted(resumo.values(), key=lambda x: -x["total_pendente"])
        _comprometimentos_cache["comprometimentos"] = result
        return result
    finally:
        conn.close()

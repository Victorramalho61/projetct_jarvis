import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from db import get_sql_connection

logger = logging.getLogger(__name__)

_QUERY = """
SELECT
    FIL.NOME AS FILIAL,
    PES.CODIGO AS COD_PESSOA,
    PES.NOME AS PESSOA,
    DOC.DATAEMISSAO AS DATA_EMISSAO,
    DOC1.DATAINCLUSAO AS DATA_INCLUSAO_RF,
    DOC.DATAINCLUSAO AS DATA_INCLUSAO_CPA,
    DOC.DOCUMENTODIGITADO,
    DOC.HANDLE AS HDL_DOC,
    DOC1.HANDLE AS HDL_DOC_RF,
    CASE DOC.SEQUENCIAALCADA
        WHEN 1 THEN '1'
        WHEN 2 THEN '2'
        WHEN 3 THEN '3'
        WHEN 4 THEN '4'
        ELSE 'Não se aplica'
    END AS SEQUENCIA_ALCADA_DOC,
    TPD.SIGLA AS SIGLA,
    CASE DOC.EHPREVISAO
        WHEN 'S' THEN 'Previsao'
        WHEN 'N' THEN 'Efetivo'
    END AS TIPO_DOC,
    CASE DOC.ENTRADASAIDA
        WHEN 'E' THEN 'Confirmado'
        WHEN 'I' THEN 'Bloqueado'
    END AS STATUS_DOC,
    CASE
        WHEN DOC.RECEBIMENTOFISICO IN (SELECT RECEBIMENTOFISICOPAI FROM CP_RECEBIMENTOFISICO WITH (NOLOCK) WHERE CONTRATO IS NOT NULL) THEN 'Contrato'
        WHEN DOC.RECEBIMENTOFISICO IN (SELECT RECEBIMENTOFISICOPAI FROM CP_RECEBIMENTOFISICO WITH (NOLOCK) WHERE ORDEMCOMPRA IS NOT NULL) THEN 'Ordem de Compra'
        WHEN DOC.DOCUMENTODIGITADO LIKE '%OC%' AND DOC.DOCUMENTODIGITADO LIKE '%--%' THEN 'Ordem de Compra'
        WHEN DOC.DOCUMENTODIGITADO LIKE '%CME/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSER/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSE/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSCR/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSA/%' OR DOC.DOCUMENTODIGITADO LIKE '%CONT/%' THEN 'Contrato'
        ELSE 'Financeiro'
    END AS ORIGEM,
    DOC.HISTORICO,
    DOC.GRUPOASSINATURAS,
    PAR.HANDLE AS AP,
    PAR.DATAVENCIMENTO,
    PAR.DATALIQUIDACAO,
    PAR.VALOR,
    CASE PAR.DOCUMENTOSUSPENSO
        WHEN 'S' THEN 'Suspensa'
        WHEN 'N' THEN 'Liberada'
    END AS STATUS_PAR,
    LAN.HANDLE AS HDL_LAN,
    CASE LAN.NATUREZA
        WHEN 'C' THEN LAN.VALOR * -1
        ELSE LAN.VALOR
    END AS VALOR_CONTA_FINANCEIRA,
    CONCAT(CT.ESTRUTURA, ' - ', CT.NOME) AS CONTA_CONCATENADA,
    CT.NOME AS CONTA,
    CT.HANDLE AS HDL_CONTA,
    (SELECT top 1 NOMEDOGRUPO FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE handle = DOC.GRUPOASSINATURAS) AS GRUPO_ALCADA
FROM FN_PARCELAS PAR WITH (NOLOCK)
    INNER JOIN FILIAIS FIL WITH (NOLOCK) ON PAR.FILIAL = FIL.HANDLE
    LEFT JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
    LEFT JOIN FN_DOCUMENTOS DOC1 WITH (NOLOCK) ON DOC1.HANDLE = PAR.DOCUMENTORF
    LEFT JOIN FN_TIPOSDOCUMENTOS TPD WITH (NOLOCK) ON TPD.HANDLE = DOC.TIPODOCUMENTO
    LEFT JOIN GN_PESSOAS PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
    OUTER APPLY (
        SELECT TOP 1 L.HANDLE, L.NATUREZA, L.VALOR, L.CONTA
        FROM FN_LANCAMENTOS L WITH (NOLOCK)
            JOIN FN_CONTAS C WITH (NOLOCK) ON C.HANDLE = L.CONTA
        WHERE L.PARCELA = PAR.HANDLE AND L.TIPO = 3
        ORDER BY
            CASE WHEN L.NATUREZA = 'D'
                  AND C.ESTRUTURA NOT LIKE '%.03.004.%'
                  AND C.ESTRUTURA NOT LIKE '%.03.002.%'
                  AND C.ESTRUTURA NOT LIKE '%.03.003.%'
                  AND C.ESTRUTURA NOT LIKE '%.03.005.%'
                 THEN 0 ELSE 1 END,
            L.HANDLE ASC
    ) LAN
    LEFT JOIN FN_CONTAS CT WITH (NOLOCK) ON CT.HANDLE = LAN.CONTA
WHERE PAR.EMPRESA = 1
    AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
    AND DOC.ENTRADASAIDA IN ('I','E')
    AND DOC.ABRANGENCIA <> 'R'
    AND PAR.DATAVENCIMENTO BETWEEN ? AND ?
"""

_SPARKLINE_QUERY = """
SELECT
    LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7) AS MES,
    SUM(PAR.VALOR) AS TOTAL
FROM FN_PARCELAS PAR WITH (NOLOCK)
    LEFT JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
WHERE PAR.EMPRESA = 1
    AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
    AND DOC.ENTRADASAIDA IN ('I','E')
    AND DOC.ABRANGENCIA <> 'R'
    AND PAR.DATAVENCIMENTO >= DATEADD(MONTH, -12, GETDATE())
GROUP BY LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)
ORDER BY MES ASC
"""

_YOY_QUERY = """
SELECT
    LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7) AS MES,
    SUM(PAR.VALOR) AS TOTAL
FROM FN_PARCELAS PAR WITH (NOLOCK)
    LEFT JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
WHERE PAR.EMPRESA = 1
    AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
    AND DOC.ENTRADASAIDA IN ('I','E')
    AND DOC.ABRANGENCIA <> 'R'
    AND PAR.DATAVENCIMENTO BETWEEN ? AND ?
GROUP BY LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)
ORDER BY MES ASC
"""

_YOY_MENSAL_QUERY = """
SELECT MES,
    CASE WHEN ORIGEM = 'Contrato' THEN 'contrato' ELSE 'eventual' END AS CATEGORIA,
    SUM(TOTAL) AS TOTAL
FROM (
    SELECT
        LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7) AS MES,
        CASE
            WHEN DOC.RECEBIMENTOFISICO IN (SELECT RECEBIMENTOFISICOPAI FROM CP_RECEBIMENTOFISICO WITH (NOLOCK) WHERE CONTRATO IS NOT NULL) THEN 'Contrato'
            WHEN DOC.RECEBIMENTOFISICO IN (SELECT RECEBIMENTOFISICOPAI FROM CP_RECEBIMENTOFISICO WITH (NOLOCK) WHERE ORDEMCOMPRA IS NOT NULL) THEN 'Financeiro'
            WHEN DOC.DOCUMENTODIGITADO LIKE '%OC%' AND DOC.DOCUMENTODIGITADO LIKE '%--%' THEN 'Financeiro'
            WHEN DOC.DOCUMENTODIGITADO LIKE '%CME/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSER/%'
              OR DOC.DOCUMENTODIGITADO LIKE '%CSE/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSCR/%'
              OR DOC.DOCUMENTODIGITADO LIKE '%CSA/%' OR DOC.DOCUMENTODIGITADO LIKE '%CONT/%' THEN 'Contrato'
            ELSE 'Financeiro'
        END AS ORIGEM,
        PAR.VALOR AS TOTAL
    FROM FN_PARCELAS PAR WITH (NOLOCK)
        LEFT JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
    WHERE PAR.EMPRESA = 1
        AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
        AND DOC.ENTRADASAIDA IN ('I','E')
        AND DOC.ABRANGENCIA <> 'R'
        AND PAR.DATAVENCIMENTO BETWEEN ? AND ?
) AS T
GROUP BY MES, CASE WHEN ORIGEM = 'Contrato' THEN 'contrato' ELSE 'eventual' END
ORDER BY MES ASC
"""


def _serialize(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _aggregate(rows: list[dict], key_fn, val_key: str) -> list[dict]:
    totals: dict = defaultdict(float)
    for row in rows:
        k = key_fn(row)
        v = row.get(val_key) or 0
        totals[k] += float(v)
    return sorted(
        [{"key": k, "valor": round(v, 2)} for k, v in totals.items()],
        key=lambda x: x["valor"],
        reverse=True,
    )


_RECURRENCE_QUERY = """
SELECT
    PES.HANDLE,
    COUNT(DISTINCT LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)) AS MESES
FROM FN_PARCELAS PAR WITH (NOLOCK)
    LEFT JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
    LEFT JOIN GN_PESSOAS PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE PAR.EMPRESA = 1
    AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
    AND DOC.ENTRADASAIDA IN ('I','E')
    AND DOC.ABRANGENCIA <> 'R'
    AND PAR.DATAVENCIMENTO >= DATEADD(MONTH, -16, GETDATE())
    AND PES.HANDLE IN ({placeholders})
GROUP BY PES.HANDLE
"""


def _fetch_recurrence(handles: list) -> dict[str, str]:
    """Returns {pessoa_handle_str: meses_count} for a list of PESSOA handles."""
    if not handles:
        return {}
    unique = list({h for h in handles if h is not None})
    if not unique:
        return {}
    placeholders = ",".join("?" * len(unique))
    query = _RECURRENCE_QUERY.format(placeholders=placeholders)
    conn = get_sql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, unique)
        result = {str(row[0]): row[1] for row in cursor.fetchall()}
    finally:
        conn.close()
    return result


def _categoria(meses: int) -> str:
    if meses >= 3:
        return "Recorrente"
    return "Eventual"


def _fetch_sparkline() -> list[float]:
    """Returns last 12 months of monthly totals, oldest-first."""
    conn = get_sql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_SPARKLINE_QUERY)
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [round(float(row[1]), 2) for row in rows]


def _fetch_yoy(year: int) -> dict[str, float]:
    """Returns {month_str: valor} for the prior year (year-1)."""
    prior_year = year - 1
    date_from = f"{prior_year}-01-01"
    date_to = f"{prior_year}-12-31"
    conn = get_sql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_YOY_QUERY, (date_from, date_to))
        rows = cursor.fetchall()
    finally:
        conn.close()
    return {row[0]: round(float(row[1]), 2) for row in rows}


def _fetch_yoy_mensal(year: int) -> dict[str, dict]:
    """Returns {month_str: {contrato, eventual}} for the prior year (year-1)."""
    prior_year = year - 1
    date_from = f"{prior_year}-01-01"
    date_to = f"{prior_year}-12-31"
    conn = get_sql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_YOY_MENSAL_QUERY, (date_from, date_to))
        rows = cursor.fetchall()
    finally:
        conn.close()
    result: dict[str, dict] = {}
    for mes, categoria, total in rows:
        if mes not in result:
            result[mes] = {"contrato": 0.0, "eventual": 0.0}
        cat = categoria if categoria in ("contrato", "eventual") else "eventual"
        result[mes][cat] += float(total) if total is not None else 0.0
    return {k: {"contrato": round(v["contrato"], 2), "eventual": round(v["eventual"], 2)}
            for k, v in result.items()}


def _kpi_comp(cur: float, prev: float | None) -> dict | None:
    if prev is None or prev == 0:
        return None
    pct = round((cur / prev - 1) * 100, 1)
    direcao = "alta" if pct > 2 else ("baixa" if pct < -2 else "estavel")
    return {"valor": round(cur - prev, 2), "pct": pct, "direcao": direcao}


def fetch_dashboard(
    year: int,
    filial: str | None = None,
    tipo: str = "todos",  # "todos" | "contrato" | "eventual"
) -> dict:
    date_from = f"{year}-01-01"
    date_to = f"{year}-12-31"

    conn = get_sql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_QUERY, (date_from, date_to))
        columns = [col[0] for col in cursor.description]
        rows = [
            {col: _serialize(val) for col, val in zip(columns, row)}
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()

    # Apply filial filter in Python
    if filial:
        rows = [r for r in rows if r.get("FILIAL") == filial]

    # Apply tipo filter in Python
    if tipo == "contrato":
        rows = [r for r in rows if r.get("ORIGEM") == "Contrato"]
    elif tipo == "eventual":
        rows = [r for r in rows if r.get("ORIGEM") in ("Ordem de Compra", "Financeiro")]

    # Compute recurrence per supplier using 16-month history
    pessoa_handles = [r.get("COD_PESSOA") for r in rows]
    recurrence_map = _fetch_recurrence(pessoa_handles)
    for row in rows:
        handle = str(row.get("COD_PESSOA")) if row.get("COD_PESSOA") is not None else None
        meses = recurrence_map.get(handle, 1) if handle else 1
        row["CATEGORIA"] = _categoria(meses)

    total_valor = sum(float(r.get("VALOR") or 0) for r in rows)
    efetivo_rows = [r for r in rows if r.get("TIPO_DOC") == "Efetivo"]
    previsao_rows = [r for r in rows if r.get("TIPO_DOC") == "Previsao"]
    total_efetivo = sum(float(r.get("VALOR") or 0) for r in efetivo_rows)
    total_previsao = sum(float(r.get("VALOR") or 0) for r in previsao_rows)

    months_in_period = len({
        str(r.get("DATAVENCIMENTO") or "")[:7]
        for r in rows
        if r.get("DATAVENCIMENTO")
    }) or 1

    by_month_raw = _aggregate(rows, lambda r: str(r.get("DATAVENCIMENTO") or "")[:7], "VALOR")
    by_month = sorted(
        [{"month": e["key"], "valor": e["valor"]} for e in by_month_raw if e["key"]],
        key=lambda x: x["month"],
    )

    by_conta_raw = _aggregate(rows, lambda r: r.get("CONTA") or "Sem conta", "VALOR")
    by_conta = [{"conta": e["key"], "valor": e["valor"]} for e in by_conta_raw]

    by_origem_raw = _aggregate(rows, lambda r: r.get("ORIGEM") or "Outros", "VALOR")
    by_origem = [{"origem": e["key"], "valor": e["valor"]} for e in by_origem_raw]

    by_categoria_raw = _aggregate(rows, lambda r: r.get("CATEGORIA", "Eventual"), "VALOR")
    by_categoria = [{"categoria": e["key"], "valor": e["valor"]} for e in by_categoria_raw]

    recorrente_rows = [r for r in rows if r.get("CATEGORIA") == "Recorrente"]
    eventual_rows = [r for r in rows if r.get("CATEGORIA") == "Eventual"]

    # by_filial: aggregated totals per filial
    by_filial_raw = _aggregate(rows, lambda r: r.get("FILIAL") or "Sem filial", "VALOR")
    by_filial = [{"filial": e["key"], "valor": e["valor"]} for e in by_filial_raw]

    # filiais: unique filial names for dropdown
    filiais = sorted({r.get("FILIAL") for r in rows if r.get("FILIAL")})

    # by_fornecedor: top 20 by valor
    fornecedor_totals: dict[str, dict] = {}
    for row in rows:
        pessoa = row.get("PESSOA") or "Sem fornecedor"
        origem = row.get("ORIGEM") or "Outros"
        valor = float(row.get("VALOR") or 0)
        if pessoa not in fornecedor_totals:
            fornecedor_totals[pessoa] = {"pessoa": pessoa, "valor": 0.0, "origem": origem}
        fornecedor_totals[pessoa]["valor"] += valor
    by_fornecedor = sorted(
        fornecedor_totals.values(),
        key=lambda x: x["valor"],
        reverse=True,
    )[:20]
    for entry in by_fornecedor:
        entry["valor"] = round(entry["valor"], 2)

    # by_origem_mensal: per-month breakdown of Contrato vs Eventual
    mensal_map: dict[str, dict] = defaultdict(lambda: {"contrato": 0.0, "eventual": 0.0})
    for row in rows:
        mes = str(row.get("DATAVENCIMENTO") or "")[:7]
        if not mes:
            continue
        origem = row.get("ORIGEM") or ""
        valor = float(row.get("VALOR") or 0)
        if origem == "Contrato":
            mensal_map[mes]["contrato"] += valor
        elif origem in ("Ordem de Compra", "Financeiro"):
            mensal_map[mes]["eventual"] += valor
    by_origem_mensal = sorted(
        [
            {
                "mes": mes,
                "contrato": round(v["contrato"], 2),
                "eventual": round(v["eventual"], 2),
            }
            for mes, v in mensal_map.items()
        ],
        key=lambda x: x["mes"],
    )

    # Sparkline: last 12 months of totals
    try:
        sparkline = _fetch_sparkline()
    except Exception:
        logger.exception("Erro ao buscar sparkline")
        sparkline = []

    # YoY: prior year monthly totals (only when year >= 2026)
    yoy: dict[str, float] = {}
    yoy_mensal: dict[str, dict] = {}
    if year >= 2026:
        try:
            yoy = _fetch_yoy(year)
        except Exception:
            logger.exception("Erro ao buscar YoY")
        try:
            yoy_mensal = _fetch_yoy_mensal(year)
        except Exception:
            logger.exception("Erro ao buscar yoy_mensal")

    # KPI comparisons — month-over-month (last 2 months from by_origem_mensal)
    vs_mes_ant_total = vs_mes_ant_cont = vs_mes_ant_ev = None
    if len(by_origem_mensal) >= 2:
        last_m = by_origem_mensal[-1]
        prev_m = by_origem_mensal[-2]
        last_total = last_m["contrato"] + last_m["eventual"]
        prev_total = prev_m["contrato"] + prev_m["eventual"]
        vs_mes_ant_total = _kpi_comp(last_total, prev_total)
        vs_mes_ant_cont = _kpi_comp(last_m["contrato"], prev_m["contrato"])
        vs_mes_ant_ev = _kpi_comp(last_m["eventual"], prev_m["eventual"])

    # vs prior year same period
    vs_ly_total = None
    if year >= 2026 and yoy:
        existing_months = {m["mes"] for m in by_origem_mensal}
        prior_period_keys = {m.replace(str(year), str(year - 1)) for m in existing_months}
        ytd_prior = sum(yoy.get(k, 0.0) for k in prior_period_keys)
        vs_ly_total = _kpi_comp(total_valor, ytd_prior) if ytd_prior > 0 else None

    total_recorrente = round(sum(float(r.get("VALOR") or 0) for r in recorrente_rows), 2)
    total_eventual_val = round(sum(float(r.get("VALOR") or 0) for r in eventual_rows), 2)
    media_mensal_val = round(total_valor / months_in_period, 2)

    return {
        "kpis": {
            # Legacy flat fields (kept for compatibility)
            "total_valor": round(total_valor, 2),
            "total_efetivo": round(total_efetivo, 2),
            "total_previsao": round(total_previsao, 2),
            "count_parcelas": len(rows),
            "count_efetivo": len(efetivo_rows),
            "count_previsao": len(previsao_rows),
            "media_mensal": media_mensal_val,
            "media_mensal_valor": media_mensal_val,
            "total_recorrente": total_recorrente,
            "total_eventual": total_eventual_val,
            "sparkline": sparkline,
            # KPIWithContext objects
            "total_ytd": {
                "valor": round(total_valor, 2),
                "sparkline": sparkline,
                "vs_mes_anterior": vs_mes_ant_total,
                "vs_ly": vs_ly_total,
            },
            "contratos": {
                "valor": total_recorrente,
                "sparkline": [],
                "vs_mes_anterior": vs_mes_ant_cont,
            },
            "eventual": {
                "valor": total_eventual_val,
                "sparkline": [],
                "vs_mes_anterior": vs_mes_ant_ev,
            },
            "media_mensal_kpi": {
                "valor": media_mensal_val,
                "sparkline": sparkline,
                "vs_mes_anterior": None,
            },
        },
        "by_month": by_month,
        "by_conta": by_conta,
        "by_origem": by_origem,
        "by_categoria": by_categoria,
        "by_filial": by_filial,
        "by_fornecedor": by_fornecedor,
        "by_origem_mensal": by_origem_mensal,
        "filiais": filiais,
        "yoy": yoy,
        "yoy_mensal": yoy_mensal,
        "rows": rows,
    }

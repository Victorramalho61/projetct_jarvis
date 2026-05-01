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
    LEFT JOIN FN_LANCAMENTOS LAN WITH (NOLOCK) ON LAN.PARCELA = PAR.HANDLE AND LAN.TIPO = 3
    LEFT JOIN FN_CONTAS CT WITH (NOLOCK) ON CT.HANDLE = LAN.CONTA
WHERE PAR.EMPRESA = 1
    AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
    AND DOC.ENTRADASAIDA IN ('I','E')
    AND DOC.ABRANGENCIA <> 'R'
    AND PAR.DATAVENCIMENTO BETWEEN ? AND ?
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
    """Returns {pessoa_nome: categoria} for a list of PESSOA handles."""
    if not handles:
        return {}
    # handles are mixed (int/None), keep unique non-null
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
    if meses == 2:
        return "Ocasional"
    return "Pontual"


def fetch_dashboard(date_from: str, date_to: str) -> dict:
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

    by_categoria_raw = _aggregate(rows, lambda r: r.get("CATEGORIA", "Pontual"), "VALOR")
    by_categoria = [{"categoria": e["key"], "valor": e["valor"]} for e in by_categoria_raw]

    recorrente_rows = [r for r in rows if r.get("CATEGORIA") == "Recorrente"]
    pontual_rows = [r for r in rows if r.get("CATEGORIA") == "Pontual"]

    return {
        "kpis": {
            "total_valor": round(total_valor, 2),
            "total_efetivo": round(total_efetivo, 2),
            "total_previsao": round(total_previsao, 2),
            "count_parcelas": len(rows),
            "count_efetivo": len(efetivo_rows),
            "count_previsao": len(previsao_rows),
            "media_mensal": round(total_valor / months_in_period, 2),
            "total_recorrente": round(sum(float(r.get("VALOR") or 0) for r in recorrente_rows), 2),
            "total_pontual": round(sum(float(r.get("VALOR") or 0) for r in pontual_rows), 2),
        },
        "by_month": by_month,
        "by_conta": by_conta,
        "by_origem": by_origem,
        "by_categoria": by_categoria,
        "rows": rows,
    }

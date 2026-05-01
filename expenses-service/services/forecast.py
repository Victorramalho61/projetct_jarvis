import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from db import get_sql_connection

logger = logging.getLogger(__name__)

# Query all monthly totals with ORIGEM breakdown.
# Uses a subquery so CASO only appears in SELECT (not GROUP BY) — avoids WITH NOLOCK in GROUP BY.
_ALL_MONTHS_QUERY = """
SELECT MES, ORIGEM, SUM(TOTAL) AS TOTAL
FROM (
    SELECT
        LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7) AS MES,
        CASE
            WHEN DOC.RECEBIMENTOFISICO IN (SELECT RECEBIMENTOFISICOPAI FROM CP_RECEBIMENTOFISICO WITH (NOLOCK) WHERE CONTRATO IS NOT NULL) THEN 'Contrato'
            WHEN DOC.RECEBIMENTOFISICO IN (SELECT RECEBIMENTOFISICOPAI FROM CP_RECEBIMENTOFISICO WITH (NOLOCK) WHERE ORDEMCOMPRA IS NOT NULL) THEN 'Ordem de Compra'
            WHEN DOC.DOCUMENTODIGITADO LIKE '%OC%' AND DOC.DOCUMENTODIGITADO LIKE '%--%' THEN 'Ordem de Compra'
            WHEN DOC.DOCUMENTODIGITADO LIKE '%CME/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSER/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSE/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSCR/%' OR DOC.DOCUMENTODIGITADO LIKE '%CSA/%' OR DOC.DOCUMENTODIGITADO LIKE '%CONT/%' THEN 'Contrato'
            ELSE 'Financeiro'
        END AS ORIGEM,
        PAR.VALOR AS TOTAL
    FROM FN_PARCELAS PAR WITH (NOLOCK)
        LEFT JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
    WHERE PAR.EMPRESA = 1
        AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
        AND DOC.ENTRADASAIDA IN ('I','E')
        AND DOC.ABRANGENCIA <> 'R'
) AS T
GROUP BY MES, ORIGEM
ORDER BY MES ASC
"""

# Fornecedor query: top suppliers with Contrato origin in a given year
_FORNECEDOR_QUERY = """
SELECT
    PES.NOME AS PESSOA,
    LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7) AS MES,
    SUM(PAR.VALOR) AS TOTAL
FROM FN_PARCELAS PAR WITH (NOLOCK)
    LEFT JOIN FN_DOCUMENTOS DOC WITH (NOLOCK) ON DOC.HANDLE = PAR.DOCUMENTO
    LEFT JOIN GN_PESSOAS PES WITH (NOLOCK) ON PES.HANDLE = DOC.PESSOA
WHERE PAR.EMPRESA = 1
    AND DOC.GRUPOASSINATURAS IN (SELECT HANDLE FROM CP_GRUPOALCADAS WITH (NOLOCK) WHERE K_GESTOR = 23)
    AND DOC.ENTRADASAIDA IN ('I','E')
    AND DOC.ABRANGENCIA <> 'R'
    AND (
        DOC.RECEBIMENTOFISICO IN (SELECT RECEBIMENTOFISICOPAI FROM CP_RECEBIMENTOFISICO WITH (NOLOCK) WHERE CONTRATO IS NOT NULL)
        OR DOC.DOCUMENTODIGITADO LIKE '%CME/%'
        OR DOC.DOCUMENTODIGITADO LIKE '%CSER/%'
        OR DOC.DOCUMENTODIGITADO LIKE '%CSE/%'
        OR DOC.DOCUMENTODIGITADO LIKE '%CSCR/%'
        OR DOC.DOCUMENTODIGITADO LIKE '%CSA/%'
        OR DOC.DOCUMENTODIGITADO LIKE '%CONT/%'
    )
    AND PAR.DATAVENCIMENTO BETWEEN ? AND ?
GROUP BY PES.NOME, LEFT(CONVERT(VARCHAR, PAR.DATAVENCIMENTO, 120), 7)
ORDER BY PES.NOME, MES
"""


def _linear_regression(x: list, y: list) -> tuple[float, float]:
    n = len(x)
    if n == 0:
        return 0.0, 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)
    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def _moving_average(values: list[float], window: int = 3) -> float:
    """Returns the moving average of the last `window` values."""
    if not values:
        return 0.0
    tail = values[-window:]
    return sum(tail) / len(tail)


def _tendencia(monthly_values: list[float]) -> str:
    """Compare avg of last 3 months vs 3 months before that."""
    if len(monthly_values) < 6:
        return "estavel"
    recent = monthly_values[-3:]
    prior = monthly_values[-6:-3]
    avg_recent = sum(recent) / len(recent)
    avg_prior = sum(prior) / len(prior)
    if avg_prior == 0:
        return "estavel"
    change = (avg_recent - avg_prior) / avg_prior
    if change > 0.10:
        return "alta"
    if change < -0.10:
        return "baixa"
    return "estavel"


def _is_eventual(origem: str) -> bool:
    return origem in ("Ordem de Compra", "Financeiro")


def fetch_forecast(year: int = 2026) -> dict:
    # --- Fetch all monthly data ---
    conn = get_sql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_ALL_MONTHS_QUERY)
        raw_rows = cursor.fetchall()
    finally:
        conn.close()

    # raw_rows: (MES str, ORIGEM str, TOTAL float)
    # Aggregate into per-month Contrato vs Eventual
    month_contrato: dict[str, float] = defaultdict(float)
    month_eventual: dict[str, float] = defaultdict(float)

    for mes, origem, total in raw_rows:
        total_f = float(total) if total is not None else 0.0
        if origem == "Contrato":
            month_contrato[mes] += total_f
        elif _is_eventual(origem):
            month_eventual[mes] += total_f

    all_months = sorted(set(list(month_contrato.keys()) + list(month_eventual.keys())))

    today = date.today()
    current_month = today.strftime("%Y-%m")

    # Identify "consistent" training months: Jul/2025 onward (avoid low initial values)
    # Use last 10 months of data that are strictly before the current partial month
    training_cutoff = "2025-07"
    training_months = [
        m for m in all_months
        if m >= training_cutoff and m < current_month
    ]
    # Cap at last 10 months
    training_months = training_months[-10:]

    # --- Build combined totals for each training month ---
    training_totals_contrato = [month_contrato.get(m, 0.0) for m in training_months]
    training_totals_eventual = [month_eventual.get(m, 0.0) for m in training_months]

    # Linear regression indices
    x_indices = list(range(len(training_months)))

    slope_c, intercept_c = _linear_regression(x_indices, training_totals_contrato)
    slope_e, intercept_e = _linear_regression(x_indices, training_totals_eventual)

    # --- Determine which months of `year` already have real data ---
    year_prefix = str(year)
    year_months_real = {
        m: (month_contrato.get(m, 0.0) + month_eventual.get(m, 0.0))
        for m in all_months
        if m.startswith(year_prefix) and m < current_month
    }
    # Current partial month counts as real if it exists
    if current_month.startswith(year_prefix) and (
        month_contrato.get(current_month, 0) + month_eventual.get(current_month, 0)
    ) > 0:
        year_months_real[current_month] = (
            month_contrato.get(current_month, 0.0) + month_eventual.get(current_month, 0.0)
        )

    # Months in the target year with no real data yet
    all_year_months = [f"{year}-{m:02d}" for m in range(1, 13)]
    year_months_future = [m for m in all_year_months if m not in year_months_real]

    # --- Project future months ---
    # The last training index is len(training_months)-1
    # Future months project from that last index onward
    last_training_idx = len(training_months) - 1 if training_months else 0

    def _project_month(offset_from_last: int) -> float:
        idx = last_training_idx + offset_from_last
        lr_c = slope_c * idx + intercept_c
        lr_e = slope_e * idx + intercept_e
        lr_total = max(lr_c + lr_e, 0.0)

        ma_c = _moving_average(training_totals_contrato)
        ma_e = _moving_average(training_totals_eventual)
        ma_total = ma_c + ma_e

        blended = 0.6 * lr_total + 0.4 * ma_total
        return round(max(blended, 0.0), 2)

    # Map future months to their projection offset
    projected: dict[str, float] = {}
    for i, m in enumerate(year_months_future, start=1):
        projected[m] = _project_month(i)

    # --- Build meses list (real + projected) ---
    # Include all training months as real data context plus the target year
    prior_year_prefix = str(year - 1)
    context_real_months = [
        m for m in all_months
        if m >= training_cutoff and not m.startswith(year_prefix)
    ]

    meses = []
    for m in context_real_months:
        total = round(month_contrato.get(m, 0.0) + month_eventual.get(m, 0.0), 2)
        meses.append({"mes": m, "valor": total, "tipo": "real"})

    for m in all_year_months:
        if m in year_months_real:
            meses.append({"mes": m, "valor": round(year_months_real[m], 2), "tipo": "real"})
        elif m in projected:
            val = projected[m]
            meses.append({
                "mes": m,
                "valor": val,
                "tipo": "projecao",
                "valor_min": round(val * 0.85, 2),
                "valor_max": round(val * 1.15, 2),
            })

    # --- Totals ---
    total_year = sum(
        month_contrato.get(m, 0.0) + month_eventual.get(m, 0.0)
        for m in all_months
        if m.startswith(year_prefix)
    )
    # Prior year total (for context)
    prior_year_months = [m for m in all_months if m.startswith(prior_year_prefix)]
    total_prior_year = sum(
        month_contrato.get(m, 0.0) + month_eventual.get(m, 0.0)
        for m in prior_year_months
    )

    total_year_real = sum(year_months_real.values())
    total_year_projecao = sum(projected.values())
    total_year_estimado = round(total_year_real + total_year_projecao, 2)

    # --- Fornecedor forecast ---
    date_from = f"{year}-01-01"
    date_to = f"{year}-12-31"
    conn2 = get_sql_connection()
    try:
        cursor2 = conn2.cursor()
        cursor2.execute(_FORNECEDOR_QUERY, (date_from, date_to))
        forn_rows = cursor2.fetchall()
    finally:
        conn2.close()

    # forn_rows: (PESSOA, MES, TOTAL)
    # Group by pessoa → list of (mes, total)
    forn_map: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for pessoa, mes, total in forn_rows:
        pessoa_name = pessoa or "Sem fornecedor"
        forn_map[pessoa_name].append((mes, float(total) if total is not None else 0.0))

    # Sort each supplier's entries by month
    for pessoa_name in forn_map:
        forn_map[pessoa_name].sort(key=lambda x: x[0])

    # Months already executed in the year (real data)
    months_with_real_data = sorted(year_months_real.keys())
    months_done = len(months_with_real_data)
    months_remaining = 12 - months_done

    by_fornecedor = []
    for pessoa_name, entries in forn_map.items():
        month_values = [v for _, v in entries]
        valor_executado = round(sum(month_values), 2)
        media_mensal = round(valor_executado / max(months_done, 1), 2)
        tendencia = _tendencia(month_values)
        valor_projetado_restante = round(media_mensal * months_remaining, 2)
        total_estimado_ano = round(valor_executado + valor_projetado_restante, 2)

        by_fornecedor.append({
            "pessoa": pessoa_name,
            "valor_executado": valor_executado,
            "media_mensal": media_mensal,
            "meses_restantes": months_remaining,
            "valor_projetado_restante": valor_projetado_restante,
            "total_estimado_ano": total_estimado_ano,
            "tendencia": tendencia,
        })

    # Sort by total estimated descending, take top 20
    by_fornecedor.sort(key=lambda x: x["total_estimado_ano"], reverse=True)
    by_fornecedor = by_fornecedor[:20]

    return {
        "meses": meses,
        "total_prior_year": round(total_prior_year, 2),
        f"total_{prior_year_prefix}": round(total_prior_year, 2),
        f"total_{year}_real": round(total_year_real, 2),
        f"total_{year}_projecao": round(total_year_projecao, 2),
        f"total_{year}_estimado": total_year_estimado,
        "modelo": "linear_regression",
        "by_fornecedor": by_fornecedor,
    }

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote as _url_quote

from fastapi import APIRouter, Depends, Query, Response

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql, fmt_sql_raw
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/impostos-retidos")
def impostos_retidos(
    response: Response,
    data_inicio: str = Query(..., alias="dataInicio"),
    data_fim:    str = Query(..., alias="dataFim"),
    empresa: str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    validar_periodo(data_inicio, data_fim)
    cache_key = f"empresa={empresa}&dataInicio={data_inicio}&dataFim={data_fim}"
    hit = cache_get("impostos_retidos", cache_key)
    if hit is not None:
        return hit

    conditions = ["m.DATA BETWEEN %s AND %s"]
    params: list = [data_inicio, data_fim]
    if empresa: conditions.append("m.EMPRESA = %s"); params.append(empresa)
    where = f"WHERE {' AND '.join(conditions)}"
    where_com_filtro = (
        where + " AND (m.K_IRRFARECUPERAR>0 OR m.K_PISARECUPERAR>0"
        " OR m.K_COFINSARECUPERAR>0 OR m.K_ISSARECUPERAR>0 OR m.K_CSLLARECUPERAR>0)"
    )

    def _totais():
        sql = (
            "SELECT"
            " SUM(ISNULL(m.K_IRRFARECUPERAR,0)) AS irrf,"
            " SUM(ISNULL(m.K_PISARECUPERAR,0)) AS pis,"
            " SUM(ISNULL(m.K_COFINSARECUPERAR,0)) AS cofins,"
            " SUM(ISNULL(m.K_ISSARECUPERAR,0)) AS iss,"
            " SUM(ISNULL(m.K_CSLLARECUPERAR,0)) AS csll,"
            " SUM(ISNULL(m.K_IRRFARECUPERAR,0)+ISNULL(m.K_PISARECUPERAR,0)"
            "    +ISNULL(m.K_COFINSARECUPERAR,0)+ISNULL(m.K_ISSARECUPERAR,0)"
            "    +ISNULL(m.K_CSLLARECUPERAR,0)) AS totalRetido"
            " FROM dbo.FN_MOVIMENTACOES m"
            f" {where}"
        )
        with get_mssql() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchone() or {}, sql

    def _detalhes():
        sql = (
            "SELECT TOP 500"
            " CONVERT(varchar(10), m.DATA, 120) AS data,"
            " m.DOCUMENTO AS documento,"
            " ISNULL(p.NOME,'') AS pessoaNome, ISNULL(p.CGCCPF,'') AS cpfCnpj,"
            " m.VALOR AS valorBruto,"
            " ISNULL(m.K_IRRFARECUPERAR,0) AS irrf,"
            " ISNULL(m.K_PISARECUPERAR,0) AS pis,"
            " ISNULL(m.K_COFINSARECUPERAR,0) AS cofins,"
            " ISNULL(m.K_ISSARECUPERAR,0) AS iss,"
            " ISNULL(m.K_CSLLARECUPERAR,0) AS csll,"
            " ISNULL(m.VALORIMPOSTOSRETIDOS,0) AS totalRetencoes,"
            " CASE WHEN m.CONTABILIZADO='S' THEN 'baixado' ELSE 'pendente' END AS statusBaixa"
            " FROM dbo.FN_MOVIMENTACOES m"
            " LEFT JOIN dbo.GN_PESSOAS p ON p.HANDLE = m.PESSOA"
            f" {where_com_filtro}"
            " ORDER BY m.DATA DESC"
        )
        with get_mssql() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall(), sql

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_totais   = pool.submit(_totais)
        f_detalhes = pool.submit(_detalhes)
        totais_rows, sql_totais     = f_totais.result()
        detalhes_rows, sql_detalhes = f_detalhes.result()

    _debug = "\n\n-- ===\n\n".join([
        f"-- TOTAIS\n{fmt_sql_raw(sql_totais, params)}",
        f"-- DETALHES\n{fmt_sql_raw(sql_detalhes, params)}",
    ])
    response.headers["X-SQL"] = _url_quote(_debug)
    result = {"totais": totais_rows, "detalhes": detalhes_rows}
    cache_set("impostos_retidos", cache_key, result)
    return result

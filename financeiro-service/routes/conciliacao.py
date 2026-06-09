from concurrent.futures import ThreadPoolExecutor

from urllib.parse import quote as _url_quote

from fastapi import APIRouter, Depends, Query, Response

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql, fmt_sql_raw
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


def _query_movimentacoes(empresa, filial, conta, data_inicio, data_fim):
    conditions = ["l.DATA BETWEEN %s AND %s"]
    params: list = [data_inicio, data_fim]
    if empresa: conditions.append("l.EMPRESA = %s"); params.append(empresa)
    if filial:  conditions.append("l.FILIAL = %s");  params.append(filial)
    if conta:   conditions.append("c.NUMEROCONTA = %s"); params.append(conta)

    sql = (
        "SELECT TOP 500"
        " l.HANDLE AS handle,"
        " CONVERT(varchar(10), l.DATA, 120) AS data,"
        " l.DOCUMENTO AS documento, l.VALOR AS valor, l.NATUREZA AS natureza,"
        " l.CONTABILIZADO AS contabilizado,"
        " CASE WHEN m.ENCONTROCONTAS IS NOT NULL THEN m.ENCONTROCONTAS ELSE NULL END AS encontroContas,"
        " ISNULL(p.NOME,'') AS pessoaNome,"
        " ISNULL(c.NUMEROCONTA,'') AS conta, ISNULL(b.NOME,'') AS banco,"
        " ISNULL(l.HISTORICO,'') AS historico,"
        " CASE WHEN m.ENCONTROCONTAS IS NOT NULL THEN 'conciliado'"
        "      WHEN l.CONTABILIZADO='S' THEN 'contabilizado'"
        "      ELSE 'pendente' END AS status"
        " FROM dbo.FN_LANCAMENTOS l"
        " LEFT JOIN dbo.GN_PESSOAS p ON p.HANDLE = l.PESSOA"
        " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE = l.CONTA"
        " LEFT JOIN dbo.GN_BANCOS b ON b.HANDLE = c.BANCO"
        " LEFT JOIN dbo.FN_MOVIMENTACOES m ON m.HANDLE = l.MOVIMENTACAO"
        f" WHERE {' AND '.join(conditions)}"
        " ORDER BY l.DATA DESC"
    )
    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall(), sql, params


def _query_resumo(empresa, data_inicio, data_fim):
    conditions = ["l.DATA BETWEEN %s AND %s"]
    params: list = [data_inicio, data_fim]
    if empresa: conditions.append("l.EMPRESA = %s"); params.append(empresa)

    sql = (
        "SELECT"
        " ISNULL(c.NUMEROCONTA,'S/Conta') AS conta, ISNULL(b.NOME,'') AS banco,"
        " SUM(CASE WHEN l.NATUREZA='C' THEN l.VALOR ELSE 0 END) AS totalCredito,"
        " SUM(CASE WHEN l.NATUREZA='D' THEN l.VALOR ELSE 0 END) AS totalDebito,"
        " SUM(CASE WHEN l.NATUREZA='C' THEN l.VALOR WHEN l.NATUREZA='D' THEN -l.VALOR ELSE 0 END) AS saldo,"
        " COUNT(*) AS totalLancamentos,"
        " SUM(CASE WHEN m.ENCONTROCONTAS IS NOT NULL THEN 1 ELSE 0 END) AS conciliados"
        " FROM dbo.FN_LANCAMENTOS l"
        " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE = l.CONTA"
        " LEFT JOIN dbo.GN_BANCOS b ON b.HANDLE = c.BANCO"
        " LEFT JOIN dbo.FN_MOVIMENTACOES m ON m.HANDLE = l.MOVIMENTACAO"
        f" WHERE {' AND '.join(conditions)}"
        " GROUP BY c.NUMEROCONTA, b.NOME ORDER BY totalLancamentos DESC"
    )
    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall(), sql, params


@router.get("/conciliacao")
def conciliacao(
    response: Response,
    data_inicio: str = Query(..., alias="dataInicio"),
    data_fim:    str = Query(..., alias="dataFim"),
    empresa: str | None = Query(None),
    filial:  str | None = Query(None),
    conta:   str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    validar_periodo(data_inicio, data_fim)
    cache_key = f"empresa={empresa}&filial={filial}&conta={conta}&dataInicio={data_inicio}&dataFim={data_fim}"
    hit = cache_get("conciliacao", cache_key)
    if hit is not None:
        return hit

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_mov    = pool.submit(_query_movimentacoes, empresa, filial, conta, data_inicio, data_fim)
        f_resumo = pool.submit(_query_resumo, empresa, data_inicio, data_fim)
        movimentacoes, sql_mov, params_mov       = f_mov.result()
        resumo_por_conta, sql_resumo, params_resumo = f_resumo.result()

    _debug = "\n\n-- ===\n\n".join([
        f"-- MOVIMENTACOES\n{fmt_sql_raw(sql_mov, params_mov)}",
        f"-- RESUMO\n{fmt_sql_raw(sql_resumo, params_resumo)}",
    ])
    response.headers["X-SQL"] = _url_quote(_debug)
    result = {"movimentacoes": movimentacoes, "resumoPorConta": resumo_por_conta}
    cache_set("conciliacao", cache_key, result)
    return result

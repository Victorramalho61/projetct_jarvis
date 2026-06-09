from fastapi import APIRouter, Depends, Query, Response

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql, fmt_sql
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/log-movimentacoes")
def log_movimentacoes(
    response: Response,
    data_inicio: str = Query(..., alias="dataInicio"),
    data_fim:    str = Query(..., alias="dataFim"),
    empresa: str | None = Query(None),
    filial:  str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    validar_periodo(data_inicio, data_fim)
    cache_key = f"empresa={empresa}&filial={filial}&dataInicio={data_inicio}&dataFim={data_fim}"
    hit = cache_get("log_movimentacoes", cache_key)
    if hit is not None:
        return hit

    conditions = ["l.DATA BETWEEN %s AND %s"]
    params: list = [data_inicio, data_fim]
    if empresa: conditions.append("l.EMPRESA = %s"); params.append(empresa)
    if filial:  conditions.append("l.FILIAL = %s");  params.append(filial)

    sql = (
        "SELECT TOP 1000"
        " CONVERT(varchar(10), l.DATA, 120) AS data,"
        " l.HANDLE AS handle, l.DOCUMENTO AS documento,"
        " l.VALOR AS valor, l.NATUREZA AS natureza,"
        " l.CONTABILIZADO AS contabilizado,"
        " CASE WHEN m.ENCONTROCONTAS IS NOT NULL THEN m.ENCONTROCONTAS ELSE NULL END AS encontroContas,"
        " ISNULL(p.NOME,'') AS pessoaNome,"
        " ISNULL(l.HISTORICO,'') AS operacao,"
        " ISNULL(cc.NOME,'') AS centroCusto,"
        " ISNULL(ct.NOME,'') AS contaContabil,"
        " CONVERT(varchar(19), l.DATAINCLUSAO, 120) AS dataInclusao,"
        " CAST(l.USUARIOINCLUIU AS varchar) AS usuarioInclusao"
        " FROM dbo.FN_LANCAMENTOS l"
        " LEFT JOIN dbo.GN_PESSOAS p ON p.HANDLE = l.PESSOA"
        " LEFT JOIN dbo.FN_LANCAMENTOCC lcc ON lcc.LANCAMENTO = l.HANDLE"
        " LEFT JOIN dbo.CT_CC cc ON cc.HANDLE = lcc.CENTROCUSTO"
        " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE = l.CONTA"
        " LEFT JOIN dbo.CT_CONTAS ct ON ct.HANDLE = c.CONTACONTABIL"
        " LEFT JOIN dbo.FN_MOVIMENTACOES m ON m.HANDLE = l.MOVIMENTACAO"
        f" WHERE {' AND '.join(conditions)}"
        " ORDER BY l.DATA DESC, l.DATAINCLUSAO DESC"
    )

    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchall()

    response.headers["X-SQL"] = fmt_sql(sql, params)
    cache_set("log_movimentacoes", cache_key, result)
    return result

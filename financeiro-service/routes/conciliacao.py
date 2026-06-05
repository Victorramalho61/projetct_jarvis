from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Query

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


def _query_movimentacoes(empresa, filial, conta, data_inicio, data_fim):
    conditions = ["m.DATA BETWEEN %s AND %s"]
    params: list = [data_inicio, data_fim]
    if empresa: conditions.append("m.EMPRESA = %s"); params.append(empresa)
    if filial:  conditions.append("m.FILIAL = %s");  params.append(filial)
    if conta:   conditions.append("c.NUMEROCONTA = %s"); params.append(conta)

    sql = (
        "SELECT TOP 500"
        " m.HANDLE AS handle,"
        " CONVERT(varchar(10), m.DATA, 120) AS data,"
        " m.DOCUMENTO AS documento, m.VALOR AS valor, m.NATUREZA AS natureza,"
        " m.CONTABILIZADO AS contabilizado, m.ENCONTROCONTAS AS encontroContas,"
        " ISNULL(p.NOME,'') AS pessoaNome,"
        " ISNULL(c.NUMEROCONTA,'') AS conta, ISNULL(b.NOME,'') AS banco,"
        " ISNULL(o.DESCRICAO,'') AS historico,"
        " CASE WHEN m.ENCONTROCONTAS IS NOT NULL THEN 'conciliado'"
        "      WHEN m.CONTABILIZADO='S' THEN 'contabilizado'"
        "      ELSE 'pendente' END AS status"
        " FROM dbo.FN_MOVIMENTACOES m"
        " LEFT JOIN dbo.GN_PESSOAS p ON p.HANDLE = m.PESSOA"
        " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE = m.CONTACORRENTE"
        " LEFT JOIN dbo.GN_BANCOS b ON b.HANDLE = c.BANCO"
        " LEFT JOIN dbo.GN_OPERACOES o ON o.HANDLE = m.OPERACAO"
        f" WHERE {' AND '.join(conditions)}"
        " ORDER BY m.DATA DESC"
    )
    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()


def _query_resumo(empresa, data_inicio, data_fim):
    conditions = ["m.DATA BETWEEN %s AND %s"]
    params: list = [data_inicio, data_fim]
    if empresa: conditions.append("m.EMPRESA = %s"); params.append(empresa)

    sql = (
        "SELECT"
        " ISNULL(c.NUMEROCONTA,'S/Conta') AS conta, ISNULL(b.NOME,'') AS banco,"
        " SUM(CASE WHEN m.NATUREZA='C' THEN m.VALOR ELSE 0 END) AS totalCredito,"
        " SUM(CASE WHEN m.NATUREZA='D' THEN m.VALOR ELSE 0 END) AS totalDebito,"
        " SUM(CASE WHEN m.NATUREZA='C' THEN m.VALOR WHEN m.NATUREZA='D' THEN -m.VALOR ELSE 0 END) AS saldo,"
        " COUNT(*) AS totalLancamentos,"
        " SUM(CASE WHEN m.ENCONTROCONTAS IS NOT NULL THEN 1 ELSE 0 END) AS conciliados"
        " FROM dbo.FN_MOVIMENTACOES m"
        " LEFT JOIN dbo.FN_CONTASTESOURARIA c ON c.HANDLE = m.CONTACORRENTE"
        " LEFT JOIN dbo.GN_BANCOS b ON b.HANDLE = c.BANCO"
        f" WHERE {' AND '.join(conditions)}"
        " GROUP BY c.NUMEROCONTA, b.NOME ORDER BY totalLancamentos DESC"
    )
    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()


@router.get("/conciliacao")
def conciliacao(
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
        movimentacoes  = f_mov.result()
        resumo_por_conta = f_resumo.result()

    result = {"movimentacoes": movimentacoes, "resumoPorConta": resumo_por_conta}
    cache_set("conciliacao", cache_key, result)
    return result

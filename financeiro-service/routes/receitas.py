from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Query

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/receitas")
def receitas(
    data_inicio: str = Query(..., alias="dataInicio"),
    data_fim:    str = Query(..., alias="dataFim"),
    empresa: str | None = Query(None),
    filial:  str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    validar_periodo(data_inicio, data_fim)
    cache_key = f"empresa={empresa}&filial={filial}&dataInicio={data_inicio}&dataFim={data_fim}"
    hit = cache_get("receitas", cache_key)
    if hit is not None:
        return hit

    conditions = ["m.DATA BETWEEN %s AND %s"]
    params: list = [data_inicio, data_fim]
    if empresa: conditions.append("m.EMPRESA = %s"); params.append(empresa)
    if filial:  conditions.append("m.FILIAL = %s");  params.append(filial)
    where = f"WHERE m.NATUREZA='C' AND {' AND '.join(conditions)}"

    def _resumo():
        sql = (
            "SELECT ISNULL(o.DESCRICAO,'Sem Operação') AS operacao,"
            " SUM(m.VALOR) AS total, COUNT(*) AS qtd,"
            " SUM(m.VALOR)*100.0/NULLIF(SUM(SUM(m.VALOR)) OVER(),0) AS pct"
            " FROM dbo.FN_MOVIMENTACOES m"
            " LEFT JOIN dbo.GN_OPERACOES o ON o.HANDLE = m.OPERACAO"
            f" {where}"
            " GROUP BY o.DESCRICAO ORDER BY total DESC"
        )
        with get_mssql() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    def _detalhe():
        sql = (
            "SELECT TOP 500"
            " CONVERT(varchar(10), m.DATA, 120) AS data,"
            " m.DOCUMENTO AS documento, m.VALOR AS valor,"
            " ISNULL(p.NOME,'') AS pessoaNome, ISNULL(o.DESCRICAO,'') AS historico,"
            " ISNULL(cc.NOME,'') AS centroCusto"
            " FROM dbo.FN_MOVIMENTACOES m"
            " LEFT JOIN dbo.GN_PESSOAS p ON p.HANDLE = m.PESSOA"
            " LEFT JOIN dbo.GN_OPERACOES o ON o.HANDLE = m.OPERACAO"
            " LEFT JOIN dbo.CT_CC cc ON cc.HANDLE = m.CENTROCUSTO"
            f" {where}"
            " ORDER BY m.DATA DESC"
        )
        with get_mssql() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_resumo  = pool.submit(_resumo)
        f_detalhe = pool.submit(_detalhe)
        result = {"resumoPorOperacao": f_resumo.result(), "detalhe": f_detalhe.result()}

    cache_set("receitas", cache_key, result)
    return result

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/razao")
def razao(
    natureza: str = Query(..., pattern="^(cliente|fornecedor)$"),
    data_inicio: str = Query(..., alias="dataInicio"),
    data_fim:    str = Query(..., alias="dataFim"),
    empresa: str | None = Query(None),
    filial:  str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    validar_periodo(data_inicio, data_fim)
    natureza_sql = "C" if natureza == "cliente" else "D"
    cache_key = f"natureza={natureza}&empresa={empresa}&filial={filial}&dataInicio={data_inicio}&dataFim={data_fim}"
    hit = cache_get("razao", cache_key)
    if hit is not None:
        return hit

    conditions = ["m.NATUREZA = %s", "m.DATA BETWEEN %s AND %s"]
    params: list = [natureza_sql, data_inicio, data_fim]
    if empresa: conditions.append("m.EMPRESA = %s"); params.append(empresa)
    if filial:  conditions.append("m.FILIAL = %s");  params.append(filial)

    sql = (
        "SELECT TOP 500"
        " CONVERT(varchar(10), m.DATA, 120) AS data,"
        " m.DOCUMENTO AS documento, m.VALOR AS valor, m.NATUREZA AS natureza,"
        " m.CONTABILIZADO AS contabilizado,"
        " ISNULL(p.NOME,'') AS pessoaNome, ISNULL(p.CPFCNPJ,'') AS cpfCnpj,"
        " ISNULL(o.DESCRICAO,'') AS historico,"
        " ISNULL(cc.NOME,'') AS centroCusto, ISNULL(ct.NOME,'') AS contaContabil,"
        " m.HANDLE AS handle"
        " FROM dbo.FN_MOVIMENTACOES m"
        " LEFT JOIN dbo.GN_PESSOAS p ON p.HANDLE = m.PESSOA"
        " LEFT JOIN dbo.GN_OPERACOES o ON o.HANDLE = m.OPERACAO"
        " LEFT JOIN dbo.CT_CC cc ON cc.HANDLE = m.CENTROCUSTO"
        " LEFT JOIN dbo.CT_CONTAS ct ON ct.HANDLE = m.CONTACONTABIL"
        f" WHERE {' AND '.join(conditions)}"
        " ORDER BY m.DATA DESC, m.DOCUMENTO"
    )

    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchall()

    cache_set("razao", cache_key, result)
    return result

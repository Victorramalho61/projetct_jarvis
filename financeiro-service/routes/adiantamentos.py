from fastapi import APIRouter, Depends, Query

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/adiantamentos")
def adiantamentos(
    natureza: str = Query(..., pattern="^(cliente|fornecedor)$"),
    data_inicio: str = Query(..., alias="dataInicio"),
    data_fim:    str = Query(..., alias="dataFim"),
    empresa: str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    validar_periodo(data_inicio, data_fim)
    natureza_sql = "C" if natureza == "cliente" else "D"
    cache_key = f"natureza={natureza}&empresa={empresa}&dataInicio={data_inicio}&dataFim={data_fim}"
    hit = cache_get("adiantamentos", cache_key)
    if hit is not None:
        return hit

    conditions = ["l.NATUREZA = %s", "l.DATA BETWEEN %s AND %s"]
    params: list = [natureza_sql, data_inicio, data_fim]
    if empresa: conditions.append("l.EMPRESA = %s"); params.append(empresa)

    sql = (
        "SELECT TOP 500"
        " CONVERT(varchar(10), l.DATA, 120) AS data,"
        " l.DOCUMENTO AS documento, l.VALOR AS valor,"
        " ISNULL(p.NOME,'') AS pessoaNome, ISNULL(p.CGCCPF,'') AS cpfCnpj,"
        " CASE WHEN l.CONTABILIZADO='S' THEN 'baixado' ELSE 'pendente' END AS status,"
        " ISNULL(l.HISTORICO,'') AS historico"
        " FROM dbo.FN_LANCAMENTOS l"
        " LEFT JOIN dbo.GN_PESSOAS p ON p.HANDLE = l.PESSOA"
        " LEFT JOIN dbo.FN_DOCUMENTOS d ON d.HANDLE = l.DOCUMENTO"
        f" WHERE d.EHADIANTAMENTO='S' AND {' AND '.join(conditions)}"
        " ORDER BY l.DATA DESC"
    )

    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchall()

    cache_set("adiantamentos", cache_key, result)
    return result

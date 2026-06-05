from fastapi import APIRouter, Depends, Query

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql
from routes._validators import validar_periodo

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/balanco")
def balanco(
    data_inicio: str = Query(..., alias="dataInicio"),
    data_fim:    str = Query(..., alias="dataFim"),
    empresa: str | None = Query(None),
    current_user: dict = Depends(require_role("admin", "user")),
):
    validar_periodo(data_inicio, data_fim)
    cache_key = f"empresa={empresa}&dataInicio={data_inicio}&dataFim={data_fim}"
    hit = cache_get("balanco", cache_key)
    if hit is not None:
        return hit

    # Balanço usa competência YYYYMM, não data completa
    competencia_ini = data_inicio[:7]
    competencia_fim = data_fim[:7]

    join_params: list = [competencia_ini, competencia_fim]
    where_conditions: list[str] = []
    where_params: list = []

    if empresa:
        join_params.append(empresa)
        where_conditions.append("ct.EMPRESA = %s")
        where_params.append(empresa)

    empresa_join = "AND tot.EMPRESA = %s" if empresa else ""
    where_clause = (" AND " + " AND ".join(where_conditions)) if where_conditions else ""

    sql = (
        "SELECT TOP 500"
        " ct.ESTRUTURA AS estrutura, ct.NOME AS nome, ct.TIPO AS tipo,"
        " ISNULL(tot.DEBITOS,0) AS debitos, ISNULL(tot.CREDITOS,0) AS creditos,"
        " ISNULL(tot.DEBITOS,0) - ISNULL(tot.CREDITOS,0) AS saldo"
        " FROM dbo.CT_CONTAS ct"
        " LEFT JOIN dbo.CT_CONTATOTAIS tot"
        "   ON tot.CONTA = ct.HANDLE"
        "  AND tot.COMPETENCIA BETWEEN %s AND %s"
        f" {empresa_join}"
        " WHERE ct.ULTIMONIVEL='S' AND ct.PERMITECONCILIAR='S'"
        f"{where_clause}"
        " ORDER BY ct.ESTRUTURA"
    )

    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, join_params + where_params)
        result = cursor.fetchall()

    cache_set("balanco", cache_key, result)
    return result

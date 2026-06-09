from fastapi import APIRouter, Depends, Response

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql, fmt_sql

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/empresas")
def listar_empresas(response: Response, current_user: dict = Depends(require_role("admin", "user"))):
    cache_key = "all"
    hit = cache_get("empresas", cache_key)
    if hit is not None:
        return hit

    sql = (
        "SELECT e.HANDLE AS handle, e.NOME AS nome, e.CODIGOREDUZIDO AS codigo"
        " FROM dbo.EMPRESAS e WHERE e.EMPRATIVA = 'S' ORDER BY e.NOME"
    )
    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()

    response.headers["X-SQL"] = fmt_sql(sql)
    cache_set("empresas", cache_key, result)
    return result

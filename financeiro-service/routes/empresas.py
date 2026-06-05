from fastapi import APIRouter, Depends

from auth import require_role
from cache import cache_get, cache_set
from db import get_mssql

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


@router.get("/empresas")
def listar_empresas(current_user: dict = Depends(require_role("admin", "user"))):
    cache_key = "all"
    hit = cache_get("empresas", cache_key)
    if hit is not None:
        return hit

    with get_mssql() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT e.HANDLE AS handle, e.NOME AS nome, e.CODIGO AS codigo"
            " FROM dbo.EMPRESAS e WHERE e.ATIVO = 'S' ORDER BY e.NOME"
        )
        result = cursor.fetchall()

    cache_set("empresas", cache_key, result)
    return result

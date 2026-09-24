"""Leitura paginada do PostgREST — sem isso toda consulta para em 1000 linhas (max-rows do
Supabase) e o dashboard/relatórios ficariam incompletos sem nenhum aviso.

Recebe uma *fábrica* de query (e não a query pronta): no postgrest-py o `.range()` acumula
parâmetros no builder, então cada página precisa de um builder novo.
"""
from typing import Callable

_PAGINA = 1000


def buscar_todos(montar_query: Callable[[], object], pagina: int = _PAGINA) -> list[dict]:
    """montar_query() deve devolver o builder já com select/filtros/order.
    Acrescenta `order("id")` como desempate para a paginação ser estável."""
    linhas: list[dict] = []
    inicio = 0
    while True:
        lote = montar_query().order("id").range(inicio, inicio + pagina - 1).execute().data or []
        linhas.extend(lote)
        if len(lote) < pagina:
            return linhas
        inicio += pagina

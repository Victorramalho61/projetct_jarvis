"""Leitura paginada do PostgREST — sem isso toda consulta para em 1000 linhas (max-rows do
Supabase), e `.limit(n > 1000)` também é cortado em 1000 sem aviso.

Recebe uma *fábrica* de query (e não a query pronta): no postgrest-py o `.range()` acumula
parâmetros no builder, então cada página precisa de um builder novo.
Cópia por serviço do padrão de rh-service/services/paginacao.py (docs/paginacao-1000-linhas.md).
"""
from typing import Callable, Optional

_PAGINA = 1000


def buscar_todos(
    montar_query: Callable[[], object],
    pagina: int = _PAGINA,
    max_linhas: Optional[int] = None,
    desempate: Optional[str] = "id",
) -> list[dict]:
    """montar_query() devolve o builder já com select/filtros/order.
    `desempate` (default "id") é acrescentado ao order para a paginação ser estável —
    passe None se a tabela não tiver coluna id. `max_linhas` substitui o antigo .limit(n)."""
    linhas: list[dict] = []
    inicio = 0
    while True:
        tamanho = pagina if max_linhas is None else min(pagina, max_linhas - len(linhas))
        if tamanho <= 0:
            return linhas
        q = montar_query()
        if desempate:
            q = q.order(desempate)
        lote = q.range(inicio, inicio + tamanho - 1).execute().data or []
        linhas.extend(lote)
        if len(lote) < tamanho:
            return linhas
        inicio += tamanho

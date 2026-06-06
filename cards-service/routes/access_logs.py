import logging

from fastapi import APIRouter, Depends, Query, Response

from auth import require_supervisor
from db import get_supabase
from services.export import to_csv, to_xml

router = APIRouter(prefix="/api/cards")
_logger = logging.getLogger(__name__)


def _apply_filters(q, params: dict):
    if params.get("cartao_id"):
        q = q.eq("cartao_id", params["cartao_id"])
    if params.get("cliente_id"):
        q = q.eq("cliente_id", params["cliente_id"])
    if params.get("user_id"):
        q = q.eq("user_id", params["user_id"])
    if params.get("localizador_os"):
        q = q.ilike("localizador_os", f"%{params['localizador_os']}%")
    if params.get("nome_cliente"):
        q = q.ilike("nome_cliente", f"%{params['nome_cliente']}%")
    if params.get("produto"):
        q = q.eq("produto", params["produto"])
    if params.get("data_reserva_de"):
        q = q.gte("data_reserva", params["data_reserva_de"])
    if params.get("data_reserva_ate"):
        q = q.lte("data_reserva", params["data_reserva_ate"])
    if params.get("nome_pax"):
        q = q.ilike("nome_pax", f"%{params['nome_pax']}%")
    if params.get("fornecedor"):
        q = q.ilike("fornecedor", f"%{params['fornecedor']}%")
    if params.get("valor_min") is not None:
        q = q.gte("valor_transacao", params["valor_min"])
    if params.get("valor_max") is not None:
        q = q.lte("valor_transacao", params["valor_max"])
    if params.get("data_acesso_de"):
        q = q.gte("data_hora_acesso", params["data_acesso_de"])
    if params.get("data_acesso_ate"):
        q = q.lte("data_hora_acesso", params["data_acesso_ate"])
    return q


def _build_query(sb, params: dict):
    q = sb.table("cards_acessos").select(
        "*, cards_cartoes(bandeira, numero_final, cards_clientes(nome))"
    )
    return _apply_filters(q, params)


def _count_query(sb, params: dict):
    """Conta registros sem materializar dados — usa o header Count do PostgREST."""
    q = sb.table("cards_acessos").select("id", count="exact")
    return _apply_filters(q, params)


@router.get("/access-logs")
def list_access_logs(
    cartao_id: str | None = None,
    cliente_id: str | None = None,
    user_id: str | None = None,
    localizador_os: str | None = None,
    nome_cliente: str | None = None,
    produto: str | None = None,
    data_reserva_de: str | None = None,
    data_reserva_ate: str | None = None,
    nome_pax: str | None = None,
    fornecedor: str | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    data_acesso_de: str | None = None,
    data_acesso_ate: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _sup: dict = Depends(require_supervisor),
):
    params = {k: v for k, v in locals().items() if k not in ("page", "page_size", "_sup") and v is not None}
    sb = get_supabase()

    count_res = _count_query(sb, params).execute()
    total = count_res.count or 0

    offset = (page - 1) * page_size
    res = _build_query(sb, params).order("data_hora_acesso", desc=True).range(offset, offset + page_size - 1).execute()
    return {
        "data": res.data or [],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/access-logs/export")
def export_access_logs(
    format: str = "csv",
    cartao_id: str | None = None,
    cliente_id: str | None = None,
    user_id: str | None = None,
    localizador_os: str | None = None,
    nome_cliente: str | None = None,
    produto: str | None = None,
    data_reserva_de: str | None = None,
    data_reserva_ate: str | None = None,
    nome_pax: str | None = None,
    fornecedor: str | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    data_acesso_de: str | None = None,
    data_acesso_ate: str | None = None,
    sup: dict = Depends(require_supervisor),
):
    params = {k: v for k, v in locals().items() if k not in ("format", "sup") and v is not None}
    sb = get_supabase()
    res = _build_query(sb, params).order("data_hora_acesso", desc=True).limit(5000).execute()
    rows = res.data or []

    sup_login = sup.get("email") or sup.get("username") or sup.get("user_id") or "unknown"
    _logger.info(
        "Export de logs de acesso solicitado por %s: formato=%s filtros=%s total=%d",
        sup_login, format.lower(), list(params.keys()), len(rows),
    )

    if format.lower() == "xml":
        content = to_xml(rows)
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=acessos_cartoes.xml"},
        )

    content = to_csv(rows)
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=acessos_cartoes.csv"},
    )

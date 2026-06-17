import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_role
from services.freshdesk import search_tickets_by_empresa

router = APIRouter(prefix="/freshservice/freshdesk", tags=["freshdesk"])
logger = logging.getLogger(__name__)

_STATUS_LABELS = {2: "Aberto", 3: "Pendente", 4: "Resolvido", 5: "Fechado", 6: "Aguardando"}


@router.get("/tickets")
async def tickets_by_empresa(
    empresa: str = Query(..., description="Valor exato do campo cf_empresa no Freshdesk"),
    page: int = Query(1, ge=1, le=10),
    _: dict = Depends(require_role("admin")),
):
    """Busca requisições (vendas) no Freshdesk filtradas pelo campo Empresa."""
    try:
        result = search_tickets_by_empresa(empresa=empresa, page=page)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Erro ao buscar tickets no Freshdesk para empresa=%s", empresa)
        raise HTTPException(status_code=502, detail="Erro ao consultar Freshdesk")

    for ticket in result["results"]:
        ticket["status_label"] = _STATUS_LABELS.get(ticket.get("status", 0), "Desconhecido")

    return result

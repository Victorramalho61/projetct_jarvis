import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_role
from services.expenses import fetch_dashboard

router = APIRouter(prefix="/expenses", tags=["expenses"])
logger = logging.getLogger(__name__)


def _default_period() -> tuple[str, str]:
    today = date.today()
    ninety_days_ago = today - timedelta(days=90)
    return str(ninety_days_ago), str(today)


@router.get("/dashboard")
async def dashboard(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(require_role("admin")),
):
    p_from, p_to = (from_date, to_date) if (from_date and to_date) else _default_period()
    try:
        return fetch_dashboard(p_from, p_to)
    except Exception as exc:
        logger.exception("Erro ao buscar gastos: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar banco de dados de gastos.")

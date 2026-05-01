import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_role
from services.expenses import fetch_dashboard
from services.forecast import fetch_forecast

router = APIRouter(prefix="/expenses", tags=["expenses"])
logger = logging.getLogger(__name__)


def _default_period() -> tuple[str, str]:
    today = date.today()
    ninety_days_ago = today - timedelta(days=90)
    return str(ninety_days_ago), str(today)


@router.get("/dashboard")
async def dashboard(
    year: int | None = Query(default=None),
    filial: str | None = Query(default=None),
    tipo: str = Query(default="todos"),
    # Legacy params kept for backwards compatibility
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(require_role("admin")),
):
    """
    Financial dashboard endpoint.

    New params: year, filial, tipo ("todos" | "contrato" | "eventual")
    Legacy params: from, to (still accepted; year is derived from `from` when year is absent)
    """
    if year is None:
        # Derive year from legacy `from` param or fall back to current year
        if from_date:
            try:
                year = int(from_date[:4])
            except (ValueError, IndexError):
                year = date.today().year
        else:
            year = date.today().year

    try:
        return fetch_dashboard(year, filial, tipo)
    except Exception as exc:
        logger.exception("Erro ao buscar gastos: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar banco de dados de gastos.")


@router.get("/forecast")
async def forecast_endpoint(
    year: int = Query(default=2026),
    _: dict = Depends(require_role("admin")),
):
    """Statistical forecast endpoint using linear regression + moving average blend."""
    try:
        return fetch_forecast(year)
    except Exception as exc:
        logger.exception("Erro ao buscar previsão: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao calcular previsão.")

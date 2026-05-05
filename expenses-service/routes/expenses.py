import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from auth import require_role
from services.expenses import fetch_dashboard
from services.forecast import fetch_forecast
from services.sync import get_cached_dashboard, get_last_updated, run_expenses_sync

router = APIRouter(prefix="/expenses", tags=["expenses"])
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def dashboard(
    year: int | None = Query(default=None),
    filial: str | None = Query(default=None),
    tipo: str = Query(default="todos"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    _: dict = Depends(require_role("admin")),
):
    if year is None:
        if from_date:
            try:
                year = int(from_date[:4])
            except (ValueError, IndexError):
                year = date.today().year
        else:
            year = date.today().year

    try:
        # Use Supabase cache for unfiltered requests (much faster than ERP)
        if not filial and tipo in ("todos", ""):
            cached = get_cached_dashboard(year)
            if cached:
                return cached
        result = fetch_dashboard(year, filial, tipo)
        result["last_updated"] = get_last_updated()
        return result
    except Exception as exc:
        logger.exception("Erro ao buscar gastos: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar banco de dados de gastos.")


@router.get("/forecast")
async def forecast_endpoint(
    year: int = Query(default=2026),
    _: dict = Depends(require_role("admin")),
):
    try:
        return fetch_forecast(year)
    except Exception as exc:
        logger.exception("Erro ao buscar previsão: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao calcular previsão.")


@router.post("/sync")
async def sync_expenses(
    background_tasks: BackgroundTasks,
    _: dict = Depends(require_role("admin")),
):
    """Dispara sincronização do cache de gastos (chamado pelo agente expenses_sync)."""
    background_tasks.add_task(_do_sync)
    return {"status": "started", "message": "Sync iniciado em background"}


def _do_sync() -> None:
    try:
        msg = run_expenses_sync()
        logger.info("Sync expenses: %s", msg)
    except Exception as exc:
        logger.exception("Sync expenses falhou: %s", exc)

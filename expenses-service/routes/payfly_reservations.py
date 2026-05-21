"""
PayFly Reservations (Vendas API V2) — CRUD + sync endpoints.
"""
import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from auth import require_role
from db import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses/payfly/reservations", tags=["payfly-reservations"])


# ── Stats (before /{id} to avoid param capture) ───────────────────────────────

@router.get("/stats")
def reservations_stats(
    start_date:   Optional[date] = Query(None),
    end_date:     Optional[date] = Query(None),
    company_name: Optional[str]  = Query(None),
    status:       Optional[str]  = Query(None),
    type:         Optional[str]  = Query(None),
    _=Depends(require_role("admin")),
):
    sb = get_supabase()
    params: dict = {}
    if start_date:   params["p_start_date"] = start_date.isoformat()
    if end_date:     params["p_end_date"]   = end_date.isoformat()
    if company_name: params["p_company"]    = company_name
    if status:       params["p_status"]     = status
    if type:         params["p_type"]       = type
    try:
        result = sb.rpc("payfly_reservation_stats", params).execute()
        return result.data
    except Exception as exc:
        logger.error("reservations_stats: %s", exc)
        raise HTTPException(502, "Erro ao buscar estatísticas")


# ── Dashboard (top-10 rankings) ───────────────────────────────────────────────

@router.get("/dashboard")
def reservations_dashboard(
    start_date:   Optional[date] = Query(None),
    end_date:     Optional[date] = Query(None),
    company_name: Optional[str]  = Query(None),
    _=Depends(require_role("admin")),
):
    sb = get_supabase()
    params: dict = {}
    if start_date:   params["p_start_date"] = start_date.isoformat()
    if end_date:     params["p_end_date"]   = end_date.isoformat()
    if company_name: params["p_company"]    = company_name
    try:
        result = sb.rpc("payfly_dashboard", params).execute()
        return result.data
    except Exception as exc:
        logger.error("reservations_dashboard: %s", exc)
        raise HTTPException(502, "Erro ao buscar dashboard")


# ── Sync (manual trigger) ─────────────────────────────────────────────────────

@router.post("/sync")
async def sync_reservations(
    background_tasks: BackgroundTasks,
    start_date: date = Query(...),
    end_date:   date = Query(...),
    _=Depends(require_role("admin")),
):
    if (end_date - start_date).days > 31:
        raise HTTPException(400, "Período máximo de 31 dias por sync manual")

    async def _task():
        from services.payfly_v2_client import sync_date_range
        ok, erros = await asyncio.to_thread(sync_date_range, start_date, end_date)
        logger.info("manual sync %s→%s: %d ok, %d erros", start_date, end_date, ok, erros)

    background_tasks.add_task(_task)
    return {"ok": True, "message": f"Sync iniciado para {start_date} → {end_date}"}


# ── Bulk historical sync ──────────────────────────────────────────────────────

@router.post("/sync/bulk")
async def sync_bulk(
    background_tasks: BackgroundTasks,
    start_date: date = Query(...),
    _=Depends(require_role("admin")),
):
    yesterday = date.today() - timedelta(days=1)
    if start_date > yesterday:
        raise HTTPException(400, "start_date deve ser anterior a hoje")

    async def _bulk():
        from services.payfly_v2_client import sync_date_range
        d = start_date
        total_ok = total_erros = 0
        while d <= yesterday:
            ok, erros = await asyncio.to_thread(sync_date_range, d, d)
            total_ok    += ok
            total_erros += erros
            d += timedelta(days=1)
        logger.info("bulk sync %s→%s: %d ok, %d erros", start_date, yesterday, total_ok, total_erros)

    background_tasks.add_task(_bulk)
    return {
        "ok": True,
        "message": f"Carga histórica iniciada desde {start_date} até {yesterday}",
    }


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/")
def list_reservations(
    start_date:   Optional[date] = Query(None),
    end_date:     Optional[date] = Query(None),
    company_name: Optional[str]  = Query(None),
    status:       Optional[str]  = Query(None),
    type:         Optional[str]  = Query(None),
    limit:        int            = Query(50, le=200),
    offset:       int            = Query(0, ge=0),
    _=Depends(require_role("admin")),
):
    sb = get_supabase()
    q = sb.table("payfly_reservations").select(
        "id,type,status,os_number,company_name,passenger_name,destination,"
        "hotel_city,origin,total_amount,choice_date,travel_start_date,solicitor_name"
    )
    if start_date:   q = q.gte("choice_date", start_date.isoformat())
    if end_date:     q = q.lte("choice_date", (end_date.isoformat() + "T23:59:59"))
    if company_name: q = q.eq("company_name", company_name)
    if status:       q = q.eq("status", status)
    if type:         q = q.eq("type", type)

    q = q.order("choice_date", desc=True).range(offset, offset + limit - 1)
    try:
        result = q.execute()
        return {"items": result.data, "offset": offset, "limit": limit}
    except Exception as exc:
        logger.error("list_reservations: %s", exc)
        raise HTTPException(502, "Erro ao listar reservas")


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{res_id}")
def get_reservation(
    res_id: str,
    _=Depends(require_role("admin")),
):
    sb = get_supabase()
    try:
        result = (
            sb.table("payfly_reservations")
            .select("*")
            .eq("id", res_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(404, "Reserva não encontrada")
        return result.data
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_reservation %s: %s", res_id, exc)
        raise HTTPException(502, "Erro ao buscar reserva")

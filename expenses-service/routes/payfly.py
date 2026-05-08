"""
PayFly — endpoints REST de investimentos (Benner Empresa = 03) e mídia (Supabase).
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import require_role
from db import get_supabase
from limiter import limiter
from services.payfly import fetch_payfly_investments, fetch_payfly_investments_detail

router = APIRouter(prefix="/expenses/payfly", tags=["payfly"])
logger = logging.getLogger(__name__)


@router.get("/investments")
@limiter.limit("10/minute")
async def get_investments(
    request: Request,
    year: int | None = Query(None, description="Ano (ex: 2026). Omitir = todos os anos."),
    _: dict = Depends(require_role("admin")),
):
    """Gastos PayFly por fornecedor + série mensal (Benner EMPRESA=03)."""
    try:
        return await asyncio.to_thread(fetch_payfly_investments, year)
    except Exception as exc:
        logger.exception("Erro ao buscar investimentos PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar investimentos PayFly no Benner.")


@router.get("/investments/detail")
@limiter.limit("10/minute")
async def get_investments_detail(
    request: Request,
    year: int | None = Query(None, description="Ano (ex: 2026). Omitir = todos os anos."),
    _: dict = Depends(require_role("admin")),
):
    """Lista detalhada de todos os documentos PayFly para drill-down por fornecedor."""
    try:
        return await asyncio.to_thread(fetch_payfly_investments_detail, year)
    except Exception as exc:
        logger.exception("Erro ao buscar detalhes PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar detalhes PayFly no Benner.")


@router.get("/media/posts")
@limiter.limit("60/minute")
async def get_media_posts(
    request: Request,
    sentiment: str | None = Query(None, description="positivo|negativo|neutro"),
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_role("admin")),
):
    """Lista publicações de mídia monitoradas (Google News RSS) para o PayFly."""
    try:
        db = get_supabase()
        q = (
            db.table("payfly_media_posts")
            .select("id,platform,title,url,snippet,source,published_at,sentiment,sentiment_score")
            .order("published_at", desc=True)
            .limit(limit)
        )
        if sentiment:
            q = q.eq("sentiment", sentiment)
        result = q.execute()
        return result.data or []
    except Exception as exc:
        logger.exception("Erro ao buscar posts de mídia PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao buscar publicações de mídia.")


@router.get("/media/metrics")
@limiter.limit("60/minute")
async def get_media_metrics(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """Métricas mensais de publicações (agregado por mês/plataforma)."""
    try:
        db = get_supabase()
        result = (
            db.table("payfly_media_metrics")
            .select("ref_month,platform,posts_count,positive_count,negative_count,neutral_count")
            .order("ref_month", desc=True)
            .limit(24)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.exception("Erro ao buscar métricas de mídia PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao buscar métricas de mídia.")

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import get_current_user
from benner_db import query_logs, query_summary
from db import get_supabase
from limiter import limiter

router = APIRouter(prefix="/monitoring/benner", tags=["benner"])
logger = logging.getLogger(__name__)

_SITUACAO_LABEL = {1: "OK", 2: "Erro", 3: "Pendente", 20: "Erro cliente"}


# ── Leitura do Supabase (snapshot comprimido) ────────────────────────────────

@router.get("/latest")
@limiter.limit("120/minute")
async def benner_latest(
    request: Request,
    _=Depends(get_current_user),
):
    """Retorna o snapshot mais recente salvo no banco."""
    try:
        resp = (
            get_supabase()
            .table("benner_snapshots")
            .select("*")
            .order("capturado_em", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.exception("Erro ao buscar snapshot Benner")
        raise HTTPException(502, f"Falha ao consultar banco: {exc}") from exc

    if not resp.data:
        raise HTTPException(404, "Nenhum snapshot disponível ainda.")

    snap = resp.data[0]

    # Descomprime por_produto: {produto: [ok, erros]} → {produto: {ok, erros}}
    por_produto = {
        prod: {"ok": v[0], "erros": v[1]}
        for prod, v in (snap.get("por_produto") or {}).items()
    }

    # Descomprime erros_recentes: chaves curtas → nomes legíveis
    erros = [
        {
            "id":       e.get("i"),
            "produto":  e.get("p"),
            "reserva":  e.get("r"),
            "situacao": e.get("s"),
            "situacao_label": _SITUACAO_LABEL.get(e.get("s"), str(e.get("s"))),
            "mensagem": e.get("m"),
            "data":     e.get("t"),
        }
        for e in (snap.get("erros_recentes") or [])
    ]

    return {
        "capturado_em":   snap["capturado_em"],
        "total":          snap["total"],
        "ok":             snap["ok"],
        "erros":          snap["erros"],
        "taxa_erro_pct":  snap["taxa_erro_pct"],
        "por_produto":    por_produto,
        "erros_recentes": erros,
    }


@router.get("/history")
@limiter.limit("60/minute")
async def benner_history(
    request: Request,
    limit: int = Query(96, ge=1, le=288),
    _=Depends(get_current_user),
):
    """Retorna série histórica de snapshots (apenas métricas, sem erros) para gráficos."""
    try:
        resp = (
            get_supabase()
            .table("benner_snapshots")
            .select("id,capturado_em,total,ok,erros,taxa_erro_pct")
            .order("capturado_em", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:
        logger.exception("Erro ao buscar histórico Benner")
        raise HTTPException(502, f"Falha ao consultar banco: {exc}") from exc

    return {"items": list(reversed(resp.data or []))}


# ── Consulta ao vivo no SQL Server (fallback / admin) ───────────────────────

@router.get("/summary")
@limiter.limit("30/minute")
async def benner_summary(
    request: Request,
    horas: int = Query(24, ge=1, le=168),
    _=Depends(get_current_user),
):
    try:
        data = await asyncio.to_thread(query_summary, horas)
    except Exception as exc:
        logger.exception("Erro ao consultar resumo Benner")
        raise HTTPException(502, f"Falha ao consultar Benner: {exc}") from exc
    return data


@router.get("/logs")
@limiter.limit("20/minute")
async def benner_logs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    situacao: int | None = Query(None),
    produto: str | None = Query(None),
    horas: int = Query(24, ge=1, le=168),
    _=Depends(get_current_user),
):
    try:
        data = await asyncio.to_thread(query_logs, page, limit, situacao, produto, horas)
    except Exception as exc:
        logger.exception("Erro ao consultar logs Benner")
        raise HTTPException(502, f"Falha ao consultar Benner: {exc}") from exc

    for item in data["items"]:
        item["situacao_label"] = _SITUACAO_LABEL.get(item["situacao"], str(item["situacao"]))

    return data

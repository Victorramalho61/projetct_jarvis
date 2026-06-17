"""Endpoints RPA Benner — dashboard de monitoramento das automações."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import get_current_user, require_role
from db import get_supabase
from limiter import limiter
from services.benner_classifier import CATEGORIA_LABEL

router = APIRouter(prefix="/monitoring/benner/rpa", tags=["benner-rpa"])
logger = logging.getLogger(__name__)

_STATUS_ORDER = ["pendente", "processando", "resolvido", "aguardando_input", "ignorado"]


# ── summary (KPIs + por categoria) ──────────────────────────────────────────

@router.get("/summary")
@limiter.limit("60/minute")
async def rpa_summary(
    request: Request,
    _=Depends(get_current_user),
):
    """KPIs gerais + distribuição por categoria."""
    sb = get_supabase()
    try:
        resp = sb.table("benner_erros").select(
            "id,rpa_status,rpa_categoria,capturado_em,rpa_ultima_acao"
        ).execute()
        rows = resp.data or []
    except Exception as exc:
        raise HTTPException(502, f"Falha ao consultar benner_erros: {exc}") from exc

    # KPIs por status
    status_count: dict[str, int] = {s: 0 for s in _STATUS_ORDER}
    for r in rows:
        s = r.get("rpa_status") or "pendente"
        status_count[s] = status_count.get(s, 0) + 1

    # Resolvidos hoje
    hoje = datetime.now(tz=timezone.utc).date().isoformat()
    resolvidos_hoje = sum(
        1 for r in rows
        if r.get("rpa_status") == "resolvido"
        and (r.get("rpa_ultima_acao") or "")[:10] == hoje
    )

    # Por categoria
    cat_stats: dict[str, dict] = {}
    for r in rows:
        cat = r.get("rpa_categoria") or "sem_categoria"
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "resolvidos": 0, "aguardando_input": 0, "pendente": 0}
        cat_stats[cat]["total"] += 1
        s = r.get("rpa_status") or "pendente"
        if s in cat_stats[cat]:
            cat_stats[cat][s] += 1

    categorias = [
        {
            "categoria": cat,
            "label": CATEGORIA_LABEL.get(cat, cat),
            **stats,
            "taxa_resolucao_pct": round(stats["resolvidos"] / stats["total"] * 100, 1) if stats["total"] else 0,
        }
        for cat, stats in sorted(cat_stats.items(), key=lambda x: -x[1]["total"])
    ]

    return {
        "total_acumulado": len(rows),
        "por_status": status_count,
        "resolvidos_hoje": resolvidos_hoje,
        "por_categoria": categorias,
        "rpa_ativo": False,  # flag explícito — executor não está agendado ainda
    }


# ── fila de erros aguardando input ──────────────────────────────────────────

@router.get("/queue")
@limiter.limit("60/minute")
async def rpa_queue(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    categoria: str | None = Query(None),
    _=Depends(get_current_user),
):
    """Erros que o RPA não conseguiu resolver automaticamente (aguardando_input)."""
    sb = get_supabase()
    try:
        q = (
            sb.table("benner_erros")
            .select("*")
            .eq("rpa_status", "aguardando_input")
            .order("capturado_em", desc=True)
        )
        if categoria:
            q = q.eq("rpa_categoria", categoria)
        resp = q.range((page - 1) * limit, page * limit - 1).execute()
    except Exception as exc:
        raise HTTPException(502, f"Falha ao consultar fila: {exc}") from exc

    items = resp.data or []
    for item in items:
        item["categoria_label"] = CATEGORIA_LABEL.get(item.get("rpa_categoria") or "", "")
    return {"items": items, "page": page, "limit": limit}


# ── histórico de execuções ───────────────────────────────────────────────────

@router.get("/history")
@limiter.limit("60/minute")
async def rpa_history(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    status: str | None = Query(None),
    _=Depends(get_current_user),
):
    """Últimas N execuções do RPA com resultado."""
    sb = get_supabase()
    try:
        q = (
            sb.table("benner_erros")
            .select("id,benner_handle,produto,sistema_origem,codigo_reserva,rpa_status,rpa_categoria,rpa_tentativas,rpa_ultima_acao,rpa_resultado,capturado_em")
            .not_.is_("rpa_ultima_acao", "null")
            .order("rpa_ultima_acao", desc=True)
            .limit(limit)
        )
        if status:
            q = q.eq("rpa_status", status)
        resp = q.execute()
    except Exception as exc:
        raise HTTPException(502, f"Falha ao buscar histórico: {exc}") from exc

    items = resp.data or []
    for item in items:
        item["categoria_label"] = CATEGORIA_LABEL.get(item.get("rpa_categoria") or "", "")
    return {"items": items}


# ── ações manuais ────────────────────────────────────────────────────────────

@router.post("/{erro_id}/resolve")
@limiter.limit("30/minute")
async def rpa_resolve(
    erro_id: int,
    request: Request,
    user=Depends(require_role("admin")),
):
    """Marca erro como resolvido manualmente."""
    sb = get_supabase()
    try:
        resp = sb.table("benner_erros").update({
            "rpa_status": "resolvido",
            "rpa_resultado": f"Resolvido manualmente por {user.get('email', 'admin')}",
            "rpa_ultima_acao": datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", erro_id).execute()
    except Exception as exc:
        raise HTTPException(502, f"Falha ao resolver: {exc}") from exc

    if not resp.data:
        raise HTTPException(404, "Erro não encontrado")
    return {"ok": True}


@router.post("/{erro_id}/ignore")
@limiter.limit("30/minute")
async def rpa_ignore(
    erro_id: int,
    request: Request,
    user=Depends(require_role("admin")),
):
    """Marca erro como ignorado."""
    sb = get_supabase()
    try:
        resp = sb.table("benner_erros").update({
            "rpa_status": "ignorado",
            "rpa_resultado": f"Ignorado por {user.get('email', 'admin')}",
            "rpa_ultima_acao": datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", erro_id).execute()
    except Exception as exc:
        raise HTTPException(502, f"Falha ao ignorar: {exc}") from exc

    if not resp.data:
        raise HTTPException(404, "Erro não encontrado")
    return {"ok": True}


@router.post("/{erro_id}/retry")
@limiter.limit("10/minute")
async def rpa_retry(
    erro_id: int,
    request: Request,
    user=Depends(require_role("admin")),
):
    """Reseta para pendente para ser reprocessado no próximo ciclo RPA."""
    sb = get_supabase()
    try:
        resp = sb.table("benner_erros").update({
            "rpa_status": "pendente",
            "rpa_tentativas": 0,
            "rpa_resultado": f"Retry manual por {user.get('email', 'admin')}",
        }).eq("id", erro_id).execute()
    except Exception as exc:
        raise HTTPException(502, f"Falha ao retentar: {exc}") from exc

    if not resp.data:
        raise HTTPException(404, "Erro não encontrado")
    return {"ok": True}

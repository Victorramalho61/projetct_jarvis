"""
PayFly — endpoints REST de investimentos (Benner Empresa = 03) e mídia (Supabase).
"""
import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import require_role
from db import get_supabase
from limiter import limiter
from services.payfly import (
    fetch_payfly_investments,
    fetch_payfly_investments_detail,
    fetch_payfly_comprometimentos,
    fetch_payfly_supplier_debug,
    fetch_dev_contracts_debug,
    invalidate_investments_cache,
)

router = APIRouter(prefix="/expenses/payfly", tags=["payfly"])
logger = logging.getLogger(__name__)

# ── Helpers de mídia ───────────────────────────────────────────────────────────

def _norm_title(title: str) -> str:
    """Normaliza título para deduplicação: lowercase, só alfanumérico, primeiros 100 chars."""
    t = re.sub(r"\W+", " ", (title or "").lower()).strip()
    return " ".join(t.split())[:100]


_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Crise", [
        "fraude", "golpe", "esquema", "scam", "vazamento", "hack", "suspen",
        "falência", "falencia", "pane", "colapso", "crise", "investigação",
        "investigacao", "indisponível", "indisponivel",
    ]),
    ("Jurídico", [
        "lgpd", "judicial", "processo", "ação civil", "acao civil", "indenização",
        "indenizacao", "multa", "senacon", "banco central", "compliance",
        "regulatório", "regulatorio", "procon", "lei ", "direito",
    ]),
    ("Reclamação", [
        "reclam", "problema", "não funciona", "nao funciona",
        "péssimo", "pessimo", "horrível", "horrivel",
        "denúncia", "denuncia", "queixa", "cobrado", "cobranc",
        "estorno", "bloqueado", "bloqueio", "cancelado", "travado",
    ]),
    ("Elogio", [
        "elogio", "parabéns", "parabens", "excelente", "ótimo", "otimo",
        "adorei", "recomendo", "satisfeito", "nota 5", "nota 10", "aprovei",
        "melhor aplicativo", "super fácil", "super facil",
    ]),
    ("Imprensa", [
        "anuncia", "lança", "lanca", "apresenta", "revela",
        "plataforma", "ceo ", "fundador", "rodada", "captação",
        "captacao", "série a", "serie a", "parceria", "expansão", "expansao",
        "crescimento", "prêmio", "premio", "destaque", "lançamento", "lancamento",
        "investimento", "inovação", "inovacao",
        "viagens corporativas", "gestão de viagens", "política de viagens",
        "travel management", "corporate travel",
    ]),
]


def _classify_category_media(title: str, snippet: str | None = None) -> str:
    """Classifica notícia por categoria via keyword matching (sem LLM)."""
    text = ((title or "") + " " + (snippet or "")).lower()
    for category, keywords in _CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "Neutro"


def _expand_sentiment(sentiment: str, score: float | None) -> str:
    """Expande sentimento de 3 para 5 classes usando o score."""
    score = score or 0.0
    if sentiment == "positivo":
        return "muito_positivo" if score >= 0.6 else "positivo"
    if sentiment == "negativo":
        return "muito_negativo" if score <= -0.6 else "negativo"
    return "neutro"


# ── Investimentos ──────────────────────────────────────────────────────────────

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


@router.get("/investments/comprometimentos")
@limiter.limit("10/minute")
async def get_comprometimentos(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """Parcelas pendentes de contratos PayFly (DATALIQUIDACAO IS NULL)."""
    try:
        return await asyncio.to_thread(fetch_payfly_comprometimentos)
    except Exception as exc:
        logger.exception("Erro ao buscar comprometimentos PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar comprometimentos PayFly no Benner.")


@router.get("/investments/debug-suppliers")
@limiter.limit("5/minute")
async def debug_suppliers(
    request: Request,
    q: str = Query(..., description="Trecho do nome (ex: NEXT SQUAD, HIPERLINK)"),
    _: dict = Depends(require_role("admin")),
):
    """Busca bruta de fornecedores no Benner sem filtros — diagnóstico de dados ausentes."""
    try:
        return await asyncio.to_thread(fetch_payfly_supplier_debug, q)
    except Exception as exc:
        logger.exception("Erro no debug de fornecedores: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar Benner.")


@router.get("/investments/debug-dev-contracts")
@limiter.limit("5/minute")
async def debug_dev_contracts(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """Diagnóstico: localiza todos os registros de Hiperlink/NextSquad no Benner sem filtros."""
    try:
        return await asyncio.to_thread(fetch_dev_contracts_debug)
    except Exception as exc:
        logger.exception("Erro no debug de contratos dev: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar Benner.")


@router.post("/investments/cache/clear")
@limiter.limit("5/minute")
async def clear_investments_cache(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """Invalida o cache de investimentos (TTL 1h), forçando nova consulta ao Benner."""
    invalidate_investments_cache()
    return {"ok": True, "message": "Cache de investimentos invalidado."}


# ── Mídia ──────────────────────────────────────────────────────────────────────

@router.get("/media/posts")
@limiter.limit("60/minute")
async def get_media_posts(
    request: Request,
    sentiment: str | None = Query(None, description="positivo|negativo|neutro|muito_positivo|muito_negativo"),
    category: str | None = Query(None, description="Reclamação|Elogio|Imprensa|Crise|Jurídico|Neutro"),
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_role("admin")),
):
    """Lista publicações de mídia com deduplicação por título, categoria e sentimento expandido."""
    try:
        db = get_supabase()
        fetch_limit = min(limit * 4, 1500)

        # Filtro de sentimento base (3-class) — o expand para 5-class é feito em Python
        base_sentiment = None
        if sentiment in ("positivo", "muito_positivo"):
            base_sentiment = "positivo"
        elif sentiment in ("negativo", "muito_negativo"):
            base_sentiment = "negativo"
        elif sentiment == "neutro":
            base_sentiment = "neutro"

        q = (
            db.table("payfly_media_posts")
            .select("id,platform,title,url,snippet,source,published_at,sentiment,sentiment_score")
            .order("published_at", desc=True)
            .limit(fetch_limit)
        )
        if base_sentiment:
            q = q.eq("sentiment", base_sentiment)
        result = q.execute()

        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        unique_posts = []

        for post in (result.data or []):
            url        = (post.get("url") or "").rstrip("/")
            norm       = _norm_title(post.get("title") or "")
            if not url or url in seen_urls or not norm or norm in seen_titles:
                continue
            seen_urls.add(url)
            seen_titles.add(norm)

            # Enriquecer com category e sentiment_label (computados on-the-fly)
            cat          = _classify_category_media(post.get("title") or "", post.get("snippet"))
            sent_label   = _expand_sentiment(post.get("sentiment") or "neutro", post.get("sentiment_score"))
            post["category"]       = cat
            post["sentiment_label"] = sent_label

            # Filtrar por categoria se solicitado
            if category and cat != category:
                continue
            # Filtrar por sentimento expandido se solicitado
            if sentiment in ("muito_positivo", "muito_negativo") and sent_label != sentiment:
                continue

            unique_posts.append(post)
            if len(unique_posts) >= limit:
                break

        return unique_posts
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


@router.get("/media/daily-metrics")
@limiter.limit("30/minute")
async def get_media_daily_metrics(
    request: Request,
    days: int = Query(30, ge=7, le=90, description="Quantidade de dias retroativos"),
    _: dict = Depends(require_role("admin")),
):
    """Série diária de publicações dos últimos N dias, agregada em Python."""
    try:
        db = get_supabase()
        # Busca posts dos últimos N dias (usa published_at)
        result = (
            db.table("payfly_media_posts")
            .select("published_at,sentiment")
            .order("published_at", desc=True)
            .limit(days * 50)  # até 50 posts/dia em buffer
            .execute()
        )

        agg: dict[str, dict] = defaultdict(lambda: {
            "posts_count": 0, "positive_count": 0,
            "negative_count": 0, "neutral_count": 0,
        })

        now = datetime.now(timezone.utc)
        for row in (result.data or []):
            pub = row.get("published_at") or ""
            if len(pub) < 10:
                continue
            date_str = pub[:10]
            # Só inclui dentro da janela de dias
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if (now - dt).days > days:
                    continue
            except Exception:
                continue
            agg[date_str]["posts_count"] += 1
            s = row.get("sentiment") or "neutro"
            if s == "positivo":
                agg[date_str]["positive_count"] += 1
            elif s == "negativo":
                agg[date_str]["negative_count"] += 1
            else:
                agg[date_str]["neutral_count"] += 1

        series = [
            {"date": d, **counts}
            for d, counts in sorted(agg.items())
        ]
        return series
    except Exception as exc:
        logger.exception("Erro ao buscar métricas diárias PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao buscar métricas diárias.")


@router.get("/media/crisis")
@limiter.limit("30/minute")
async def get_media_crisis(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """
    Status de crise: compara volume de negativos nas últimas 24h
    com a média diária dos 30 dias anteriores.
    Retorna status: ok | warning | critical.
    """
    try:
        db = get_supabase()
        result = (
            db.table("payfly_media_posts")
            .select("published_at,sentiment,title,platform")
            .order("published_at", desc=True)
            .limit(2000)
            .execute()
        )

        now = datetime.now(timezone.utc)
        neg_24h: list[dict] = []
        daily_neg: dict[str, int] = defaultdict(int)

        for row in (result.data or []):
            pub = row.get("published_at") or ""
            if len(pub) < 10:
                continue
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                continue
            age_h = (now - dt).total_seconds() / 3600
            age_d = (now - dt).days
            if age_d > 31:
                continue
            if row.get("sentiment") == "negativo":
                if age_h <= 24:
                    neg_24h.append({
                        "title":    row.get("title"),
                        "platform": row.get("platform"),
                        "published_at": pub,
                    })
                if 1 <= age_d <= 30:
                    daily_neg[pub[:10]] += 1

        avg_daily = (sum(daily_neg.values()) / len(daily_neg)) if daily_neg else 0.0
        count_24h = len(neg_24h)
        ratio     = count_24h / avg_daily if avg_daily > 0 else 0.0

        if count_24h >= 5 and ratio >= 2.5:
            status = "critical"
        elif count_24h >= 3 and ratio >= 1.8:
            status = "warning"
        else:
            status = "ok"

        return {
            "status":        status,
            "neg_24h":       count_24h,
            "avg_daily_neg": round(avg_daily, 1),
            "ratio":         round(ratio, 2),
            "recent_negative": neg_24h[:5],
        }
    except Exception as exc:
        logger.exception("Erro ao calcular status de crise PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao calcular status de crise.")


@router.get("/media/categories")
@limiter.limit("30/minute")
async def get_media_categories(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """Breakdown de posts por categoria (computado on-the-fly nos últimos 200 posts deduplicados)."""
    try:
        db = get_supabase()
        result = (
            db.table("payfly_media_posts")
            .select("title,snippet,sentiment,sentiment_score,url")
            .order("published_at", desc=True)
            .limit(600)
            .execute()
        )

        seen_titles: set[str] = set()
        counts: dict[str, int] = defaultdict(int)

        for row in (result.data or []):
            norm = _norm_title(row.get("title") or "")
            url  = (row.get("url") or "").rstrip("/")
            if not norm or norm in seen_titles:
                continue
            seen_titles.add(norm)
            cat = _classify_category_media(row.get("title") or "", row.get("snippet"))
            counts[cat] += 1

        total = sum(counts.values()) or 1
        return [
            {"category": cat, "count": cnt, "pct": round(cnt / total * 100, 1)}
            for cat, cnt in sorted(counts.items(), key=lambda x: -x[1])
        ]
    except Exception as exc:
        logger.exception("Erro ao calcular categorias PayFly: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao calcular categorias.")


# ── Pipeline de mídia — trigger manual ────────────────────────────────────────

@router.post("/media/fetch")
@limiter.limit("3/minute")
async def trigger_media_fetch(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """Dispara o pipeline completo de coleta de notícias PayFly manualmente (sem esperar 23:59)."""
    import asyncio
    from services.media_pipeline import run
    try:
        result = await run()
        return {"ok": True, "result": result}
    except Exception as exc:
        logger.exception("Erro no pipeline de mídia: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao executar pipeline de mídia.")

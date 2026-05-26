"""
Orquestração do pipeline diário de mídia PayFly.

Ordem:
  1. fetch_all()             — todas as fontes em paralelo (feedparser + httpx async)
  2. extract_full_articles() — newspaper3k/BS4 nos top 10 mais relevantes
  3. classify_articles_llm() — Gemini 2.0 Flash → category + sentiment_label
  4. embed_articles()        — text-embedding-004 → vector(768) para pgvector
  5. store()                 — bulk upsert no Supabase
  6. aggregate_metrics()     — recalcula payfly_media_metrics e payfly_media_daily_metrics
  7. detect_crisis()         — compara 24h vs baseline 30d
  8. send_crisis_webhook()   — POST se warning|critical
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_BULK_SIZE = 50


async def run() -> dict:
    from db import get_settings, get_supabase
    s = get_settings()
    google_key = s.google_api_key
    groq_key   = s.groq_api_key
    webhook    = s.crisis_webhook_url

    # 1. Fetch paralelo
    from services.media_fetcher import fetch_all
    articles = await fetch_all()
    logger.info("media_pipeline: %d artigos coletados", len(articles))
    if not articles:
        return {"fetched": 0, "inserted": 0, "metrics": 0, "crisis": None}

    # 2. Extração de texto completo (top 10 por relevância)
    from services.media_extractor import extract_full_articles
    articles = await extract_full_articles(articles, top_n=10)

    # 3. Classificação LLM (1 chamada para o batch todo)
    if google_key or groq_key:
        from services.media_classifier import classify_articles_llm
        articles = await classify_articles_llm(articles, google_key, groq_key)

    # 4. Embeddings (grátis via Gemini; skip se sem API key)
    if google_key:
        from services.media_embeddings import embed_articles
        articles = await embed_articles(articles, google_key)

    # 5. Persistir no Supabase
    db = get_supabase()
    inserted = await _store(db, articles)
    logger.info("media_pipeline: %d inseridos/atualizados", inserted)

    # 6. Agregar métricas (recomputa a partir do banco para garantir precisão)
    metrics_count = await _recompute_metrics(db, articles)

    # 7. Detecção de crise
    from services.media_crisis import detect_crisis, log_crisis, send_crisis_webhook
    crisis = detect_crisis(articles)
    if crisis:
        await log_crisis(crisis)
        await send_crisis_webhook(crisis, webhook)
        logger.warning(
            "CRISE PAYFLY detectada: %s — %d negativos 24h (ratio %.1f)",
            crisis["severity"], crisis["neg_count"], crisis["ratio"],
        )

    return {"fetched": len(articles), "inserted": inserted, "metrics": metrics_count, "crisis": crisis}


async def _store(db, posts: list[dict]) -> int:
    if not posts:
        return 0
    inserted = 0
    for i in range(0, len(posts), _BULK_SIZE):
        chunk = posts[i:i + _BULK_SIZE]
        try:
            await asyncio.to_thread(
                lambda c=chunk: db.table("payfly_media_posts").upsert(
                    c, on_conflict="url"
                ).execute()
            )
            inserted += len(chunk)
        except Exception as exc:
            logger.warning("media_pipeline _store chunk[%d]: %s", i, exc)
    return inserted


async def _recompute_metrics(db, posts: list[dict]) -> int:
    """
    Recomputa métricas mensais (payfly_media_metrics) e diárias
    (payfly_media_daily_metrics) a partir dos posts recém-armazenados.

    Sempre relê o banco para os meses/datas afetados, garantindo que o
    upsert substitua com valores corretos mesmo que o lote seja parcial.
    """
    if not posts:
        return 0

    now = datetime.now(timezone.utc)

    # Determina meses e datas afetados pelos artigos desta rodada
    affected_months: set[str] = set()
    affected_dates:  set[str] = set()
    for post in posts:
        published_at = post.get("published_at")
        try:
            dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00")) if published_at else now
        except Exception:
            dt = now
        affected_months.add(f"{dt.year}-{dt.month:02d}")
        affected_dates.add(dt.strftime("%Y-%m-%d"))

    total_rows = 0

    # ── Métricas mensais por plataforma ──────────────────────────────────────
    for ref_month in affected_months:
        year_s, month_s = ref_month.split("-")
        yr, mo = int(year_s), int(month_s)
        next_mo  = (mo % 12) + 1
        next_yr  = yr + (1 if next_mo == 1 else 0)
        from_date = f"{yr}-{mo:02d}-01"
        to_date   = f"{next_yr}-{next_mo:02d}-01"

        try:
            resp = await asyncio.to_thread(
                lambda fd=from_date, td=to_date: db.table("payfly_media_posts")
                    .select("platform,sentiment")
                    .gte("published_at", fd)
                    .lt("published_at", td)
                    .execute()
            )
            db_posts = resp.data or []

            by_platform: dict[str, dict] = defaultdict(lambda: {
                "posts_count": 0, "positive_count": 0,
                "negative_count": 0, "neutral_count": 0,
            })
            for p in db_posts:
                plt = p.get("platform") or "unknown"
                snt = p.get("sentiment") or "neutro"
                by_platform[plt]["posts_count"] += 1
                if snt == "positivo":
                    by_platform[plt]["positive_count"] += 1
                elif snt == "negativo":
                    by_platform[plt]["negative_count"] += 1
                else:
                    by_platform[plt]["neutral_count"] += 1

            rows = [
                {"platform": plt, "ref_month": ref_month, **counts}
                for plt, counts in by_platform.items()
            ]
            if rows:
                await asyncio.to_thread(
                    lambda r=rows: db.table("payfly_media_metrics").upsert(
                        r, on_conflict="platform,ref_month"
                    ).execute()
                )
                total_rows += len(rows)
                logger.info(
                    "media_pipeline: métricas mensais %s — %d plataformas (%d posts)",
                    ref_month, len(rows), len(db_posts),
                )
        except Exception as exc:
            logger.warning("media_pipeline monthly metrics [%s]: %s", ref_month, exc)

    # ── Métricas diárias (todas as plataformas combinadas) ────────────────────
    for ref_date in affected_dates:
        from_dt = f"{ref_date}T00:00:00"
        to_dt   = f"{ref_date}T23:59:59.999999"

        try:
            resp = await asyncio.to_thread(
                lambda fd=from_dt, td=to_dt: db.table("payfly_media_posts")
                    .select("sentiment")
                    .gte("published_at", fd)
                    .lte("published_at", td)
                    .execute()
            )
            db_posts = resp.data or []

            counts: dict = {
                "posts_count": 0, "positive_count": 0,
                "negative_count": 0, "neutral_count": 0,
            }
            for p in db_posts:
                snt = p.get("sentiment") or "neutro"
                counts["posts_count"] += 1
                if snt == "positivo":
                    counts["positive_count"] += 1
                elif snt == "negativo":
                    counts["negative_count"] += 1
                else:
                    counts["neutral_count"] += 1

            await asyncio.to_thread(
                lambda d=ref_date, c=counts: db.table("payfly_media_daily_metrics").upsert(
                    {"date": d, **c}, on_conflict="date"
                ).execute()
            )
            total_rows += 1
            logger.info(
                "media_pipeline: métricas diárias %s — %d posts",
                ref_date, counts["posts_count"],
            )
        except Exception as exc:
            logger.warning("media_pipeline daily metrics [%s]: %s", ref_date, exc)

    logger.info(
        "media_pipeline: %d linhas de métricas gravadas (%d meses, %d dias)",
        total_rows, len(affected_months), len(affected_dates),
    )
    return total_rows

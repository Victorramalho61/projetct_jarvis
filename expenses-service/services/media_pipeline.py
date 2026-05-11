"""
Orquestração do pipeline diário de mídia PayFly.

Ordem:
  1. fetch_all()             — todas as fontes em paralelo (feedparser + httpx async)
  2. extract_full_articles() — newspaper3k/BS4 nos top 10 mais relevantes
  3. classify_articles_llm() — Gemini 2.0 Flash → category + sentiment_label
  4. embed_articles()        — text-embedding-004 → vector(768) para pgvector
  5. store()                 — bulk upsert no Supabase
  6. detect_crisis()         — compara 24h vs baseline 30d
  7. send_crisis_webhook()   — POST se warning|critical
"""
import asyncio
import logging

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
        return {"fetched": 0, "inserted": 0, "crisis": None}

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

    # 6. Detecção de crise
    from services.media_crisis import detect_crisis, log_crisis, send_crisis_webhook
    crisis = detect_crisis(articles)
    if crisis:
        await log_crisis(crisis)
        await send_crisis_webhook(crisis, webhook)
        logger.warning(
            "CRISE PAYFLY detectada: %s — %d negativos 24h (ratio %.1f)",
            crisis["severity"], crisis["neg_count"], crisis["ratio"],
        )

    return {"fetched": len(articles), "inserted": inserted, "crisis": crisis}


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

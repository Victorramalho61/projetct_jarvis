"""
Geração de embeddings via Google text-embedding-004 (768 dimensões, grátis).
Armazena na coluna `embedding vector(768)` do Supabase (pgvector).
Permite dedup semântico futuro e busca por similaridade.
"""
import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_MODEL = "models/gemini-embedding-001"   # 768d, Google AI Studio free tier
_DIM   = 768


async def embed_text(text: str, api_key: str) -> list[float] | None:
    if not text or not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/{_MODEL}:embedContent?key={api_key}",
                json={
                    "model": _MODEL,
                    "content": {"parts": [{"text": text[:2000]}]},
                    "taskType": "RETRIEVAL_DOCUMENT",
                    "outputDimensionality": _DIM,
                },
            )
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]
    except Exception as exc:
        logger.debug("embed_text: %s", exc)
        return None


async def embed_articles(articles: list[dict], api_key: str) -> list[dict]:
    """Adiciona embedding a cada artigo. Respeita rate limit com delay entre requests."""
    if not api_key:
        return articles
    for a in articles:
        text = (a.get("title") or "") + ". " + (a.get("snippet") or "")
        emb  = await embed_text(text, api_key)
        if emb:
            a["embedding"] = emb
        await asyncio.sleep(0.06)   # ~16 req/s — abaixo do free tier limit
    return articles

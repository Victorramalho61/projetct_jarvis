"""
Extração de texto completo via newspaper3k (top N artigos por relevância).
Fallback: httpx + BeautifulSoup para sites que bloqueiam newspaper3k.
"""
import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_PAYFLY_KW = ["payfly", "pay fly"]
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Jarvis/1.0)"}

# Download NLTK punkt uma vez na importação (necessário para newspaper3k)
try:
    import nltk
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
except Exception:
    pass


def _relevance_score(article: dict) -> int:
    text = ((article.get("title") or "") + " " + (article.get("snippet") or "")).lower()
    return sum(1 for kw in _PAYFLY_KW if kw in text)


def _extract_newspaper(url: str) -> str | None:
    try:
        import newspaper
        art = newspaper.Article(url, request_timeout=10)
        art.download()
        art.parse()
        return (art.text or "")[:3000] or None
    except Exception as exc:
        logger.debug("newspaper3k[%s]: %s", url, exc)
        return None


def _extract_bs4(html: str) -> str | None:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        # Tenta seletores comuns de conteúdo editorial
        for selector in ["article", "main", "[class*='article']", "[class*='content']"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                if len(text) > 200:
                    return text[:3000]
        # Fallback: parágrafos mais longos
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text()) > 80]
        return " ".join(paras)[:3000] or None
    except Exception as exc:
        logger.debug("bs4 extract: %s", exc)
        return None


async def _extract_one(article: dict) -> dict:
    url = article.get("url", "")
    if not url:
        return article

    # 1ª tentativa: newspaper3k (roda em thread pois é síncrono)
    full_text = await asyncio.to_thread(_extract_newspaper, url)

    # Fallback: httpx + BS4
    if not full_text:
        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=_HEADERS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            full_text = await asyncio.to_thread(_extract_bs4, resp.text)
        except Exception as exc:
            logger.debug("bs4_fallback[%s]: %s", url, exc)

    if full_text:
        article["full_text"] = full_text
    return article


async def extract_full_articles(articles: list[dict], top_n: int = 10) -> list[dict]:
    """Extrai texto completo apenas dos top_n artigos mais relevantes."""
    ranked = sorted(articles, key=_relevance_score, reverse=True)
    top  = ranked[:top_n]
    rest = ranked[top_n:]

    extracted = await asyncio.gather(*[_extract_one(a) for a in top], return_exceptions=True)
    result = [item for item in extracted if isinstance(item, dict)]
    result.extend(rest)
    return result

"""
Coleta de notícias PayFly via RSS + Reclame Aqui.
Usa feedparser (robusto) + httpx async — todas as fontes em paralelo.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Jarvis/1.0; +https://jarvis.voetur.com.br)"}
_PAYFLY_KW = ["payfly", "pay fly"]

# Fontes agregadas — já filtram por query na URL, não precisam de keyword_filter
_AGGREGATED = [
    ("google_news",  "https://news.google.com/rss/search?q=payfly&hl=pt-BR&gl=BR&ceid=BR:pt"),
    ("google_news",  "https://news.google.com/rss/search?q=PayFly+viagens+corporativas&hl=pt-BR&gl=BR&ceid=BR:pt"),
    # Reclame Aqui via Google RSS (API direta retorna 403)
    ("reclame_aqui", "https://news.google.com/rss/search?q=PayFly+reclame+aqui&hl=pt-BR&gl=BR&ceid=BR:pt"),
    ("bing_news",    "https://www.bing.com/news/search?q=%22PayFly%22+viagens&format=RSS"),
]

# Fontes diretas — retornam feed completo; filtramos por keyword "payfly" em Python
_DIRECT = [
    # Reddit com aspas na query + keyword_filter — evita posts irrelevantes
    ("reddit",      "https://www.reddit.com/search.rss?q=%22PayFly%22&restrict_sr=false&limit=25&sort=new"),
    ("skift",       "https://skift.com/feed/"),
    ("panrotas",    "https://www.panrotas.com.br/feed/"),
    ("startups_br", "https://startups.com.br/feed/"),
    ("finsiders",      "https://finsiders.com.br/feed/"),
    ("brasilturis",    "https://www.brasilturis.com.br/feed/"),
    ("revistahoteis",   "https://revistahoteis.com.br/feed/"),
    ("diarioturismo",    "https://diariodoturismo.com.br/feed/"),
    ("mercadoeventos",   "https://www.mercadoeeventos.com.br/feed/"),
]

_NEG_KW = {
    "fraude", "golpe", "falha", "problema", "reclamação", "denúncia", "prejuízo",
    "erro", "crash", "instabilidade", "indisponível", "bloqueio", "suspensão",
    "não funciona", "ruim", "péssimo", "horrível", "scam", "cobrança indevida",
    "atraso", "cancelamento", "cancelado", "reembolso", "extravio", "overbooking",
    "voo cancelado", "hotel não confirmado", "reserva falhou", "reserva cancelada",
}
_POS_KW = {
    "parceria", "crescimento", "inovação", "investimento", "expansão", "lançamento",
    "prêmio", "destaque", "integração", "sucesso", "melhoria", "excelente",
    "reserva confirmada", "check-in", "economia em viagens", "gestão de viagens",
    "plataforma de viagens", "corporativo",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _sentiment(text: str) -> tuple[str, float]:
    lower = (text or "").lower()
    neg = sum(1 for kw in _NEG_KW if kw in lower)
    pos = sum(1 for kw in _POS_KW if kw in lower)
    total = neg + pos
    if total == 0:
        return "neutro", 0.0
    score = (pos - neg) / total
    if score > 0.1:
        return "positivo", round(score, 3)
    if score < -0.1:
        return "negativo", round(score, 3)
    return "neutro", round(score, 3)


def _is_relevant(title: str, snippet: str) -> bool:
    text = ((title or "") + " " + (snippet or "")).lower()
    return any(kw in text for kw in _PAYFLY_KW)


def _parse_feed(content: str, platform: str, keyword_filter: bool = False) -> list[dict]:
    feed = feedparser.parse(content)
    articles: list[dict] = []
    seen: set[str] = set()
    for entry in feed.entries:
        link = (entry.get("link") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        title   = _strip_html(entry.get("title") or "")
        snippet = _strip_html(entry.get("summary") or "")
        if keyword_filter and not _is_relevant(title, snippet):
            continue
        pub_date = None
        if getattr(entry, "published_parsed", None):
            try:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
        src = None
        if getattr(entry, "source", None):
            src = entry.source.get("title") or entry.source.get("href")
        sent, score = _sentiment(title + " " + snippet)
        articles.append({
            "platform": platform, "title": title, "url": link,
            "snippet": snippet[:500] or None, "source": src,
            "published_at": pub_date,
            "sentiment": sent, "sentiment_score": score,
            "category": "Neutro", "sentiment_label": sent,
        })
    return articles


async def _fetch_rss(platform: str, url: str, keyword_filter: bool = False) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=_HEADERS) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        return _parse_feed(resp.text, platform, keyword_filter)
    except Exception as exc:
        logger.warning("media_fetcher[%s]: %s", platform, exc)
        return []


async def _fetch_reclame_aqui() -> list[dict]:
    headers = {**_HEADERS, "Accept": "application/json",
               "Origin": "https://www.reclameaqui.com.br",
               "Referer": "https://www.reclameaqui.com.br/"}
    articles: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://iosearch.reclameaqui.com.br/raichu-io-site-search-consumer/query/complains/10/0",
                params={"q": "PayFly", "facetFilters": "created,1y"},
                headers=headers,
            )
            resp.raise_for_status()
        for item in (resp.json().get("complains") or {}).get("data") or []:
            cid  = item.get("id", "")
            link = f"https://www.reclameaqui.com.br/reclamacao/{cid}/" if cid else ""
            if not link:
                continue
            title   = (item.get("title") or item.get("description") or "")[:300]
            snippet = (item.get("description") or "")[:500]
            created = item.get("createdAt") or item.get("created_at") or item.get("date")
            pub_date = None
            if created:
                try:
                    pub_date = datetime.fromisoformat(str(created).replace("Z", "+00:00")).isoformat()
                except Exception:
                    pass
            status    = (item.get("status") or "").lower()
            sentiment = "neutro" if status in ("avaliado", "respondido") else "negativo"
            articles.append({
                "platform": "reclame_aqui", "title": title, "url": link,
                "snippet": snippet or None,
                "source": (item.get("company") or {}).get("name") or "Reclame Aqui",
                "published_at": pub_date,
                "sentiment": sentiment,
                "sentiment_score": 0.0 if sentiment == "neutro" else -0.7,
                "category": "Reclamação" if sentiment == "negativo" else "Neutro",
                "sentiment_label": sentiment,
            })
    except Exception as exc:
        logger.warning("media_fetcher[reclame_aqui]: %s", exc)
    return articles


async def fetch_all() -> list[dict]:
    """Busca todas as fontes em paralelo e deduplica por URL."""
    tasks = [
        *[_fetch_rss(p, u, keyword_filter=True) for p, u in _AGGREGATED],
        *[_fetch_rss(p, u, keyword_filter=True) for p, u in _DIRECT],
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    seen_urls: set[str] = set()
    articles: list[dict] = []
    for result in results:
        if isinstance(result, list):
            for a in result:
                url = a.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    articles.append(a)
    return articles

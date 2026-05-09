"""
Ferramentas de monitoramento de mídia para o agente PayFly.
Conectores:
  - Google News RSS (sem API key)
  - Bing News RSS (sem API key)
  - Reddit JSON API pública (sem API key)
  - Reclame Aqui API pública (sem API key)
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from db import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt"
_BING_NEWS_RSS   = "https://www.bing.com/news/search?q={query}&format=RSS"
_REDDIT_RSS    = "https://www.reddit.com/search.rss?q={query}&restrict_sr=false&limit=25&sort=new"
_RA_SEARCH     = "https://www.reclameaqui.com.br/empresa/{slug}/lista-reclamacoes/"
_RA_API        = "https://iosearch.reclameaqui.com.br/raichu-io-site-search-consumer/query/complains/10/0"

_NEGATIVE_KW = {
    "fraude", "golpe", "falha", "problema", "reclamação", "reclamacão", "denúncia",
    "denuncia", "prejuízo", "prejuizo", "erro", "bug", "vazamento", "crash",
    "instabilidade", "indisponível", "indisponivel", "bloqueio", "suspensão",
    "suspensao", "encerramento", "falência", "falencia", "processo", "irregularidade",
    "descaso", "lentidão", "lentidao", "queda", "pane", "reclamação", "não funciona",
    "nao funciona", "ruim", "péssimo", "pessimo", "horrível", "horrivel", "pirataria",
    "scam", "roubando", "cobrança indevida", "cobranca indevida",
}

_POSITIVE_KW = {
    "parceria", "crescimento", "inovação", "inovacao", "investimento", "expansão",
    "expansao", "lançamento", "lancamento", "aprovação", "aprovacao", "prêmio",
    "premio", "destaque", "integração", "integracao", "sucesso", "facilidade",
    "solução", "solucao", "melhoria", "avanço", "avanco", "novo recurso",
    "novo produto", "certificação", "certificacao", "ótimo", "otimo", "excelente",
    "recomendo", "adorei", "funciona", "aprovado", "seguro",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Jarvis/1.0; +https://jarvis.voetur.com.br)"
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def classify_sentiment(text: str) -> tuple[str, float]:
    """Classifica sentimento por contagem de palavras-chave. Retorna (label, score)."""
    lower = (text or "").lower()
    neg = sum(1 for kw in _NEGATIVE_KW if kw in lower)
    pos = sum(1 for kw in _POSITIVE_KW if kw in lower)
    total = neg + pos
    if total == 0:
        return "neutro", 0.0
    score = (pos - neg) / total
    if score > 0.1:
        return "positivo", round(score, 3)
    if score < -0.1:
        return "negativo", round(score, 3)
    return "neutro", round(score, 3)


def _parse_rss_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _fetch_rss(url: str, platform: str) -> list[dict]:
    """Faz fetch de qualquer RSS e retorna lista de posts normalizados."""
    articles = []
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=_HEADERS)
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        if channel is None:
            return []
        seen: set[str] = set()
        for item in channel.findall("item"):
            link = (item.findtext("link") or "").strip()
            if not link or link in seen:
                continue
            seen.add(link)
            title   = _strip_html(item.findtext("title") or "")
            snippet = _strip_html(item.findtext("description") or "")
            src_el  = item.find("source")
            source  = (src_el.text or src_el.get("url", "") if src_el is not None else "") or None
            pub_date = _parse_rss_date(item.findtext("pubDate"))
            sentiment, score = classify_sentiment(title + " " + snippet)
            articles.append({
                "platform": platform, "title": title, "url": link,
                "snippet": snippet[:500] or None, "source": source,
                "published_at": pub_date, "sentiment": sentiment, "sentiment_score": score,
            })
    except Exception as exc:
        logger.warning("_fetch_rss(%s): %s", platform, exc)
    return articles


def fetch_google_news(keywords: list[str] | None = None) -> list[dict]:
    """Google News RSS — sem API key."""
    keywords = keywords or ["payfly", "PayFly Brasil", "PayFly pagamento", "PayFly fintech"]
    articles: list[dict] = []
    seen: set[str] = set()
    for kw in keywords:
        url = _GOOGLE_NEWS_RSS.format(query=kw.replace(" ", "+"))
        for a in _fetch_rss(url, "google_news"):
            if a["url"] not in seen:
                seen.add(a["url"])
                articles.append(a)
    return articles


def fetch_bing_news(keywords: list[str] | None = None) -> list[dict]:
    """Bing News RSS — sem API key, complementa Google News."""
    keywords = keywords or ["PayFly", "PayFly Brasil"]
    articles: list[dict] = []
    seen: set[str] = set()
    for kw in keywords:
        url = _BING_NEWS_RSS.format(query=kw.replace(" ", "+"))
        for a in _fetch_rss(url, "bing_news"):
            if a["url"] not in seen:
                seen.add(a["url"])
                articles.append(a)
    return articles


def fetch_reddit(keywords: list[str] | None = None) -> list[dict]:
    """Reddit via RSS público — não requer autenticação."""
    keywords = keywords or ["PayFly", "PayFly pagamento"]
    articles: list[dict] = []
    seen: set[str] = set()
    for kw in keywords:
        url = _REDDIT_RSS.format(query=kw.replace(" ", "+"))
        for a in _fetch_rss(url, "reddit"):
            if a["url"] not in seen:
                seen.add(a["url"])
                articles.append(a)
    return articles


def fetch_reclame_aqui(query: str = "PayFly") -> list[dict]:
    """Reclame Aqui — API de busca com headers de browser para evitar bloqueio."""
    articles: list[dict] = []
    ra_headers = {
        **_HEADERS,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.reclameaqui.com.br",
        "Referer": "https://www.reclameaqui.com.br/",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        params = {"q": query, "facetFilters": "created,1y"}
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(_RA_API, params=params, headers=ra_headers)
            resp.raise_for_status()
        data = resp.json()
        complains = (data.get("complains") or {}).get("data") or []
        for item in complains:
            complain_id = item.get("id", "")
            title = (item.get("title") or item.get("description") or "")[:300]
            snippet = (item.get("description") or "")[:500]
            company = (item.get("company") or {}).get("name", "")
            link = f"https://www.reclameaqui.com.br/reclamacao/{complain_id}/" if complain_id else ""
            if not link:
                continue
            created = item.get("createdAt") or item.get("created_at") or item.get("date")
            pub_date = None
            if created:
                try:
                    pub_date = datetime.fromisoformat(str(created).replace("Z", "+00:00")).isoformat()
                except Exception:
                    pass
            status = (item.get("status") or "").lower()
            sentiment = "neutro" if status in ("avaliado", "respondido") else "negativo"
            score = 0.0 if sentiment == "neutro" else -0.7
            articles.append({
                "platform": "reclame_aqui", "title": title, "url": link,
                "snippet": snippet or None, "source": company or "Reclame Aqui",
                "published_at": pub_date, "sentiment": sentiment, "sentiment_score": score,
            })
    except Exception as exc:
        logger.warning("fetch_reclame_aqui: %s", exc)
    return articles


def store_media_posts(posts: list[dict]) -> int:
    """Persiste posts no Supabase — ignora duplicatas por URL. Retorna qtd inserida."""
    if not posts:
        return 0
    db = _get_supabase()
    inserted = 0
    for post in posts:
        try:
            db.table("payfly_media_posts").upsert(post, on_conflict="url").execute()
            inserted += 1
        except Exception as exc:
            logger.warning("store_media_posts: erro ao inserir '%s': %s", post.get("url", "?"), exc)
    return inserted


def compute_monthly_metrics() -> list[dict]:
    """Agrega payfly_media_posts por mês e plataforma. Faz upsert em payfly_media_metrics."""
    db = _get_supabase()
    rows = db.table("payfly_media_posts").select("platform,published_at,sentiment").execute().data or []

    agg: dict[tuple[str, str], dict] = {}
    for r in rows:
        pub = r.get("published_at") or ""
        month = pub[:7] if len(pub) >= 7 else "unknown"
        platform = r.get("platform") or "google_news"
        key = (month, platform)
        if key not in agg:
            agg[key] = {"ref_month": month, "platform": platform,
                        "posts_count": 0, "positive_count": 0,
                        "negative_count": 0, "neutral_count": 0}
        agg[key]["posts_count"] += 1
        s = r.get("sentiment") or "neutro"
        if s == "positivo":
            agg[key]["positive_count"] += 1
        elif s == "negativo":
            agg[key]["negative_count"] += 1
        else:
            agg[key]["neutral_count"] += 1

    results = []
    for metrics in agg.values():
        try:
            db.table("payfly_media_metrics").upsert(
                metrics, on_conflict="ref_month,platform"
            ).execute()
            results.append(metrics)
        except Exception as exc:
            logger.warning("compute_monthly_metrics: upsert error: %s", exc)
    return results

"""
PayFly Media Monitor — coleta menções em múltiplas plataformas:
  - Google News RSS
  - Bing News RSS
  - Reddit (API pública)
  - Reclame Aqui (API pública)
"""
import logging

logger = logging.getLogger(__name__)

_KEYWORDS_NEWS   = ["payfly", "PayFly Brasil", "PayFly viagens", "PayFly viagens corporativas"]
_KEYWORDS_REDDIT = ["PayFly", "PayFly Brasil", "PayFly viagens"]


def run(state: dict) -> dict:
    from graph_engine.tools.media_tools import (
        fetch_google_news,
        fetch_bing_news,
        fetch_reddit,
        fetch_reclame_aqui,
        store_media_posts,
        compute_monthly_metrics,
    )

    findings  = []
    decisions = []
    all_articles: list[dict] = []

    sources = [
        ("Google News",   lambda: fetch_google_news(_KEYWORDS_NEWS)),
        ("Bing News",     lambda: fetch_bing_news()),
        ("Reddit",        lambda: fetch_reddit(_KEYWORDS_REDDIT)),
        ("Reclame Aqui",  lambda: fetch_reclame_aqui("PayFly")),
    ]

    for source_name, fetcher in sources:
        try:
            articles = fetcher()
            all_articles.extend(articles)
            decisions.append(f"{source_name}: {len(articles)} item(ns) coletado(s)")
        except Exception as exc:
            logger.warning("payfly_media_monitor [%s]: %s", source_name, exc)
            findings.append({
                "type": "connector_error", "severity": "low",
                "title": f"Falha ao coletar de {source_name}: {exc}",
            })

    inserted = store_media_posts(all_articles)
    metrics  = compute_monthly_metrics()

    decisions.append(f"Total: {len(all_articles)} coletados, {inserted} novos inseridos no banco")

    neg_recent = [a for a in all_articles if a.get("sentiment") == "negativo"]
    ra_items   = [a for a in all_articles if a.get("platform") == "reclame_aqui"]

    if neg_recent:
        findings.append({
            "type":     "media_negative_coverage",
            "severity": "medium" if len(neg_recent) < 5 else "high",
            "title":    f"PayFly: {len(neg_recent)} publicações negativas detectadas",
            "details":  [f"[{a['platform']}] {a['title']}" for a in neg_recent[:5]],
        })

    if ra_items:
        findings.append({
            "type":     "reclame_aqui_complaints",
            "severity": "high" if len(ra_items) >= 3 else "medium",
            "title":    f"Reclame Aqui: {len(ra_items)} reclamação(ões) encontrada(s)",
            "details":  [a["title"] for a in ra_items[:5]],
        })

    if metrics:
        decisions.append(f"Métricas mensais atualizadas: {len(metrics)} mês(es)/plataforma(s)")

    return {
        "findings":  findings,
        "decisions": decisions,
        "context":   {
            "articles_fetched": len(all_articles),
            "inserted":         inserted,
            "platforms":        list({a["platform"] for a in all_articles}),
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

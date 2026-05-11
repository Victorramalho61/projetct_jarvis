"""
Detecção de crise de mídia: compara volume de negativos nas últimas 24h
contra a média diária dos 30 dias anteriores.
Se severity warning|critical → salva em payfly_crisis_log + dispara webhook.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


def detect_crisis(articles: list[dict]) -> dict | None:
    now = datetime.now(timezone.utc)
    neg_24h: list[dict] = []
    daily_neg: dict[str, int] = defaultdict(int)

    for a in articles:
        pub = a.get("published_at") or ""
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
        if a.get("sentiment") == "negativo":
            if age_h <= 24:
                neg_24h.append(a)
            if 1 <= age_d <= 30:
                daily_neg[pub[:10]] += 1

    avg_daily = sum(daily_neg.values()) / len(daily_neg) if daily_neg else 0.0
    count_24h = len(neg_24h)
    ratio     = count_24h / avg_daily if avg_daily > 0 else 0.0

    if count_24h >= 5 and ratio >= 2.5:
        severity = "critical"
    elif count_24h >= 3 and ratio >= 1.8:
        severity = "warning"
    else:
        return None

    return {
        "severity":     severity,
        "neg_count":    count_24h,
        "avg_baseline": round(avg_daily, 2),
        "ratio":        round(ratio, 2),
        "recent": [
            {"title": a.get("title"), "platform": a.get("platform")}
            for a in neg_24h[:5]
        ],
    }


async def log_crisis(crisis: dict) -> None:
    from db import get_supabase
    db = get_supabase()
    try:
        await asyncio.to_thread(
            lambda: db.table("payfly_crisis_log").insert({
                "severity":     crisis["severity"],
                "neg_count":    crisis["neg_count"],
                "avg_baseline": crisis["avg_baseline"],
            }).execute()
        )
    except Exception as exc:
        logger.warning("log_crisis: %s", exc)


async def send_crisis_webhook(crisis: dict, webhook_url: str) -> None:
    if not webhook_url:
        return
    payload = {
        "event":             "payfly_media_crisis",
        "severity":          crisis["severity"],
        "neg_count_24h":     crisis["neg_count"],
        "avg_daily_baseline": crisis["avg_baseline"],
        "ratio":             crisis["ratio"],
        "top_articles":      crisis["recent"],
        "timestamp":         datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json=payload)
        logger.info("crisis_webhook enviado: %s", crisis["severity"])
    except Exception as exc:
        logger.warning("crisis_webhook error: %s", exc)

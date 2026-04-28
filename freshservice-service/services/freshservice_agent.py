import logging

logger = logging.getLogger(__name__)


def generate_daily_summary_sync(stats: dict) -> dict:
    date = stats.get("date", "")
    total = stats.get("total_closed", 0)
    csat = stats.get("csat_avg")
    sla_pct = stats.get("sla_breach_pct") or 0.0
    avg_res = stats.get("avg_resolution_min")

    parts = [f"{total} chamados fechados em {date}."]

    if avg_res is not None:
        h = int(avg_res) // 60
        m = int(avg_res) % 60
        tempo = f"{h}h {m}m" if h else f"{m}m"
        parts.append(f"Tempo médio de resolução: {tempo}.")

    if sla_pct > 0:
        parts.append(f"SLA breach: {sla_pct:.1f}%.")

    if csat is not None:
        parts.append(f"CSAT médio: {csat:.1f}/3.")

    summary = " ".join(parts)
    if len(summary) > 280:
        summary = summary[:277] + "..."

    anomaly = False
    anomaly_detail = ""

    if total == 0:
        anomaly = True
        anomaly_detail = f"Nenhum chamado fechado em {date}."
    elif sla_pct > 25:
        anomaly = True
        anomaly_detail = f"SLA breach acima do limite: {sla_pct:.1f}% (limite 25%)."

    return {"summary": summary, "anomaly": anomaly, "anomaly_detail": anomaly_detail}


async def generate_daily_summary(stats: dict) -> dict:
    import asyncio
    return await asyncio.to_thread(generate_daily_summary_sync, stats)

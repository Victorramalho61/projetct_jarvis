import asyncio
import logging

logger = logging.getLogger(__name__)


async def sync_benner_snapshot() -> None:
    """Captura resumo do Benner e salva snapshot comprimido no Supabase."""
    from benner_db import query_summary
    from db import get_supabase

    try:
        raw = await asyncio.to_thread(query_summary, 24)
    except Exception as exc:
        logger.warning("benner_monitor: falha ao consultar SQL Server: %s", exc)
        return

    # por_produto comprimido: {produto: [ok, erros]}
    por_produto = {
        prod: [v["ok"], v["erros"]]
        for prod, v in raw["por_produto"].items()
    }

    # erros_recentes comprimido: chaves de 1 char
    erros_recentes = [
        {
            "i": e["id"],
            "p": (e["produto"] or "")[:30],
            "r": (e["reserva"] or "")[:20],
            "s": e["situacao"],
            "m": (e["mensagem"] or "")[:200],
            "t": e["data"],
            "o": (e.get("sistema") or "")[:20],
            "c": (e.get("cliente") or "")[:35],
        }
        for e in raw["ultimos_erros"]
    ]

    payload = {
        "total":          raw["total"],
        "ok":             raw["ok"],
        "erros":          raw["erros"],
        "taxa_erro_pct":  float(raw["taxa_erro_pct"]),
        "por_produto":    por_produto,
        "erros_recentes": erros_recentes,
    }

    try:
        get_supabase().table("benner_snapshots").insert(payload).execute()
        logger.info(
            "benner_monitor: snapshot salvo — total=%d ok=%d erros=%d",
            raw["total"], raw["ok"], raw["erros"],
        )
    except Exception as exc:
        logger.error("benner_monitor: falha ao salvar snapshot: %s", exc)

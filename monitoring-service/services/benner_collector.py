"""Coleta TODOS os erros do Benner SQL Server → tabela benner_erros (Supabase).

Diferente do benner_monitor (snapshots comprimidos TOP 50), este coletor persiste
cada erro individualmente. benner_handle é UNIQUE → idempotente, seguro reexecutar.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_BATCH = 500


async def collect_benner_erros(horas: int = 48) -> int:
    """Retorna quantidade de novos erros inseridos."""
    from benner_db import get_benner_conn, _map_sistema_origem
    from db import get_supabase

    # 1. Busca erros no SQL Server
    try:
        rows = await asyncio.to_thread(_fetch_errors_from_sqlserver, horas)
    except Exception as exc:
        logger.error("benner_collector: falha SQL Server: %s", exc)
        return 0

    if not rows:
        logger.info("benner_collector: nenhum erro nas últimas %dh", horas)
        return 0

    # 2. Quais handles já existem no Supabase?
    sb = get_supabase()
    try:
        existing_resp = await asyncio.to_thread(
            lambda: sb.table("benner_erros").select("benner_handle").execute()
        )
        existing_handles: set[int] = {r["benner_handle"] for r in (existing_resp.data or [])}
    except Exception as exc:
        logger.error("benner_collector: falha ao buscar handles existentes: %s", exc)
        return 0

    # 3. Filtra só os novos + classifica
    from services.benner_classifier import classify
    new_rows = []
    for r in rows:
        if r["benner_handle"] not in existing_handles:
            r["rpa_categoria"] = classify(r.get("mensagem"), r.get("tipo_erro"))
            new_rows.append(r)
    if not new_rows:
        logger.info("benner_collector: %d erros consultados, nenhum novo", len(rows))
        return 0

    # 4. Insere em lotes
    inserted = 0
    for i in range(0, len(new_rows), _BATCH):
        batch = new_rows[i : i + _BATCH]
        try:
            await asyncio.to_thread(
                lambda b=batch: sb.table("benner_erros").upsert(b, on_conflict="benner_handle").execute()
            )
            inserted += len(batch)
        except Exception as exc:
            logger.error("benner_collector: falha ao inserir lote %d: %s", i // _BATCH, exc)

    logger.info(
        "benner_collector: %d consultados, %d novos inseridos (horas=%d)",
        len(rows), inserted, horas,
    )
    return inserted


def _fetch_errors_from_sqlserver(horas: int) -> list[dict]:
    from benner_db import get_benner_conn, _map_sistema_origem

    conn = get_benner_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            l.HANDLE, l.SITUACAO, l.TIPOERRO, l.PRODUTO,
            l.CODIGORESERVA, l.DATAREENVIO, l.MENSAGEM,
            l.ORIGEMFORNECEDOR,
            COALESCE(e.NOMEFANTASIA, CAST(l.EMPRESA AS VARCHAR(20))) AS CLIENTE
        FROM BB_LOGINTEGRACOES l
        LEFT JOIN EMPRESAS e ON e.HANDLE = l.EMPRESA
        WHERE l.SITUACAO != 1
          AND l.DATAREENVIO >= DATEADD(HOUR, ?, GETDATE())
        ORDER BY l.DATAREENVIO DESC
        """,
        (-horas,),
    )
    rows = []
    for r in cur.fetchall():
        rows.append({
            "benner_handle":  r[0],
            "situacao":       r[1],
            "tipo_erro":      r[2],
            "produto":        r[3],
            "sistema_origem": _map_sistema_origem(r[3], r[7]),
            "codigo_reserva": r[4],
            "data_registro":  r[5].isoformat() if r[5] else None,
            "mensagem":       r[6],
            "cliente":        r[8],
        })
    conn.close()
    return rows

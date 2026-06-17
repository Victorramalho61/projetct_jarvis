"""
Freshdesk → SQL Server BI  |  Sync de requisições por empresa e período
Uso:
    python freshdesk_sync.py --empresa "Voetur" --from 2026-01-01 --to 2026-06-30
    python freshdesk_sync.py --empresa "Voetur" "Empresa B" --from 2026-01-01 --to 2026-06-30
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

import httpx
import pyodbc

# ── Configuração ──────────────────────────────────────────────
FRESHDESK_API_KEY = "1D8QeHt9G6wHzNtSHAmB"
FRESHDESK_DOMAIN  = "voeturomni.freshdesk.com"
FRESHDESK_BASE    = f"https://{FRESHDESK_DOMAIN}/api/v2"

SQL_SERVER   = "10.141.0.111,1444"
SQL_DATABASE = "BI"
SQL_USER     = ""       # << preencher
SQL_PASSWORD = ""       # << preencher

CONCURRENCY    = 5      # chamadas paralelas para buscar stats
RATE_DELAY_S   = 0.3    # delay entre requests na search API
SEARCH_MAX_PG  = 10     # máximo de páginas por chunk (300 tickets)

# Palavras-chave para detectar Cotação especial na descrição
KEYWORDS_ESPECIAL = [
    "infant", "abaixo de 2 anos", "abaixo de dois anos",
    "comparativo", "múltiplos", "sistema externo", "externo ao gds",
]
# ─────────────────────────────────────────────────────────────


def _fd_auth():
    return (FRESHDESK_API_KEY, "X")


def _fd_get(path: str, params: dict = None) -> dict | list:
    url = f"{FRESHDESK_BASE}/{path}"
    resp = httpx.get(url, auth=_fd_auth(), params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _search_chunk(empresa: str, start: date, end: date) -> list[dict]:
    """Busca tickets de um chunk mensal via Search API."""
    query = (
        f"cf_empresa:'{empresa}' "
        f"AND created_at:>'{start.isoformat()}' "
        f"AND created_at:<'{end.isoformat()}'"
    )
    tickets = []
    for page in range(1, SEARCH_MAX_PG + 1):
        data = _fd_get("search/tickets", {"query": f'"{query}"', "page": page})
        batch = data.get("results") or []
        tickets.extend(batch)
        if len(batch) < 30:
            break
        if page == SEARCH_MAX_PG and len(batch) == 30:
            print(f"  WARN: chunk {start}→{end} atingiu limite de 300 tickets — "
                  "considere período menor para cobertura total.")
        time.sleep(RATE_DELAY_S)
    return tickets


def _get_ticket_stats(ticket_id: int) -> dict:
    """Busca stats (resolved_at, etc.) de um ticket individual."""
    try:
        data = _fd_get(f"tickets/{ticket_id}", {"include": "stats"})
        stats = data.get("stats") or {}
        desc  = data.get("description_text") or ""
        return {
            "id":                  ticket_id,
            "resolved_at":         stats.get("resolved_at"),
            "closed_at":           stats.get("closed_at"),
            "first_responded_at":  stats.get("first_responded_at"),
            "description_text":    desc,
        }
    except Exception as exc:
        print(f"  WARN: falha ao buscar stats do ticket {ticket_id}: {exc}")
        return {"id": ticket_id}


def _is_cotacao_especial(tipo: str, description: str) -> bool:
    if (tipo or "").lower().strip() != "cotação":
        return False
    text = (description or "").lower()
    return any(kw in text for kw in KEYWORDS_ESPECIAL)


def _map_row(ticket: dict, stats: dict) -> dict:
    cf = ticket.get("custom_fields") or {}
    tipo_raw = cf.get("cf_ipo_de_servio") or ""
    tipo     = tipo_raw.lower().strip()
    desc     = stats.get("description_text") or ""
    return {
        "id":                  ticket["id"],
        "empresa":             cf.get("cf_empresa"),
        "subject":             ticket.get("subject"),
        "status":              ticket.get("status"),
        "created_at":          ticket.get("created_at"),
        "resolved_at":         stats.get("resolved_at"),
        "closed_at":           stats.get("closed_at"),
        "first_responded_at":  stats.get("first_responded_at"),
        "tipo_servico_raw":    tipo_raw,
        "tipo_servico":        tipo,
        "tipo_servico2":       cf.get("cf_tipo_de_servio763654"),
        "tipo_demanda":        cf.get("cf_tipo_de_demanda"),
        "mercado":             cf.get("cf_mercado"),
        "produtos":            cf.get("cf_produtos"),
        "localizador":         cf.get("cf_localizador"),
        "nome_passageiro":     cf.get("cf_nome_do_passageiro"),
        "nome_solicitante":    cf.get("cf_nome_do_solicitante"),
        "cotacao_especial":    1 if _is_cotacao_especial(tipo, desc) else 0,
    }


def _get_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


_MERGE_SQL = """
MERGE dbo.freshdesk_tickets AS tgt
USING (SELECT
    ? AS id, ? AS empresa, ? AS subject, ? AS status,
    ? AS created_at, ? AS resolved_at, ? AS closed_at, ? AS first_responded_at,
    ? AS tipo_servico_raw, ? AS tipo_servico, ? AS tipo_servico2,
    ? AS tipo_demanda, ? AS mercado, ? AS produtos,
    ? AS localizador, ? AS nome_passageiro, ? AS nome_solicitante,
    ? AS cotacao_especial
) AS src ON tgt.id = src.id
WHEN MATCHED THEN UPDATE SET
    empresa            = src.empresa,
    subject            = src.subject,
    status             = src.status,
    created_at         = src.created_at,
    resolved_at        = src.resolved_at,
    closed_at          = src.closed_at,
    first_responded_at = src.first_responded_at,
    tipo_servico_raw   = src.tipo_servico_raw,
    tipo_servico       = src.tipo_servico,
    tipo_servico2      = src.tipo_servico2,
    tipo_demanda       = src.tipo_demanda,
    mercado            = src.mercado,
    produtos           = src.produtos,
    localizador        = src.localizador,
    nome_passageiro    = src.nome_passageiro,
    nome_solicitante   = src.nome_solicitante,
    cotacao_especial   = src.cotacao_especial,
    synced_at          = GETUTCDATE()
WHEN NOT MATCHED THEN INSERT (
    id, empresa, subject, status,
    created_at, resolved_at, closed_at, first_responded_at,
    tipo_servico_raw, tipo_servico, tipo_servico2,
    tipo_demanda, mercado, produtos,
    localizador, nome_passageiro, nome_solicitante,
    cotacao_especial, synced_at
) VALUES (
    src.id, src.empresa, src.subject, src.status,
    src.created_at, src.resolved_at, src.closed_at, src.first_responded_at,
    src.tipo_servico_raw, src.tipo_servico, src.tipo_servico2,
    src.tipo_demanda, src.mercado, src.produtos,
    src.localizador, src.nome_passageiro, src.nome_solicitante,
    src.cotacao_especial, GETUTCDATE()
);
"""


def _upsert_rows(rows: list[dict], conn):
    cur = conn.cursor()
    fields = [
        "id", "empresa", "subject", "status",
        "created_at", "resolved_at", "closed_at", "first_responded_at",
        "tipo_servico_raw", "tipo_servico", "tipo_servico2",
        "tipo_demanda", "mercado", "produtos",
        "localizador", "nome_passageiro", "nome_solicitante",
        "cotacao_especial",
    ]
    for row in rows:
        values = [row.get(f) for f in fields]
        cur.execute(_MERGE_SQL, values)
    conn.commit()
    cur.close()


def _month_chunks(from_date: date, to_date: date) -> list[tuple[date, date]]:
    chunks = []
    cursor = from_date.replace(day=1)
    while cursor <= to_date:
        chunk_end = cursor + relativedelta(months=1)
        chunks.append((max(cursor, from_date), min(chunk_end, to_date + timedelta(days=1))))
        cursor = chunk_end
    return chunks


def sync_empresa(empresa: str, from_date: date, to_date: date, conn):
    chunks = _month_chunks(from_date, to_date)
    print(f"\n{'='*60}")
    print(f"Empresa: {empresa} | {from_date} → {to_date} | {len(chunks)} chunk(s)")
    print(f"{'='*60}")

    total_synced = 0
    for i, (start, end) in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] buscando {start} → {end} ...", end=" ", flush=True)
        tickets = _search_chunk(empresa, start, end)
        print(f"{len(tickets)} tickets encontrados", end=" ", flush=True)

        # Buscar stats apenas para resolvidos/fechados
        resolved = [t for t in tickets if t.get("status") in (4, 5)]
        open_count = len(tickets) - len(resolved)

        stats_map: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(_get_ticket_stats, t["id"]): t["id"] for t in resolved}
            for fut in as_completed(futures):
                s = fut.result()
                stats_map[s["id"]] = s
                time.sleep(RATE_DELAY_S / CONCURRENCY)

        rows = []
        for t in tickets:
            s = stats_map.get(t["id"], {"id": t["id"]})
            rows.append(_map_row(t, s))

        _upsert_rows(rows, conn)
        total_synced += len(rows)
        print(f"→ {len(resolved)} resolvidos | {open_count} abertos | upserted OK")

    print(f"  Total upserted para '{empresa}': {total_synced}\n")


def main():
    parser = argparse.ArgumentParser(description="Sync Freshdesk → SQL Server BI")
    parser.add_argument("--empresa", nargs="+", required=True,
                        help='Nome(s) da empresa. Ex: --empresa "Voetur" "Empresa B"')
    parser.add_argument("--from",  dest="from_date", required=True,
                        help="Data início YYYY-MM-DD")
    parser.add_argument("--to",    dest="to_date",   required=True,
                        help="Data fim YYYY-MM-DD (inclusive)")
    args = parser.parse_args()

    from_date = date.fromisoformat(args.from_date)
    to_date   = date.fromisoformat(args.to_date)

    conn = _get_connection()
    try:
        for empresa in args.empresa:
            sync_empresa(empresa, from_date, to_date, conn)
    finally:
        conn.close()
    print("Sync concluído.")


if __name__ == "__main__":
    main()

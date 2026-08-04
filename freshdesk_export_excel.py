"""
Freshdesk -> Excel  |  Relatorio de tickets por empresa e periodo, no padrao
"Relatorio <Mes> <Ano> <Empresa> EMAIL.xlsx" (colunas: ID do ticket, Assunto, Tipo,
Agente, Hora da criacao, Tempo ate a primeira resposta (em horas),
Tempo de resolucao (em horas), Hora da resolucao, Hora do fechamento, Tipo de demanda)

Uso:
    python freshdesk_export_excel.py --empresa "ACCIONA" --from 2026-07-01 --to 2026-07-31 --out "C:\\Users\\victor.ramalho\\Desktop\\Relatorio Julho 26 Acciona EMAIL.xlsx"
"""

import argparse
from datetime import date, datetime, timedelta

import pandas as pd

import freshdesk_sync as fs

_BRT_OFFSET = timedelta(hours=-3)

COLUMNS = [
    "ID do ticket", "Assunto", "Tipo", "Agente", "Hora da criação",
    "Tempo até a primeira resposta (em horas)", "Tempo de resolução (em horas)",
    "Hora da resolução", "Hora do fechamento", "Tipo de demanda",
]


def _parse_utc(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fmt_dt_brt(dt):
    if dt is None:
        return ""
    return (dt + _BRT_OFFSET).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_duration(start, end):
    if start is None or end is None:
        return ""
    total_seconds = int((end - start).total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _week_chunks(from_date: date, to_date: date) -> list[tuple[date, date]]:
    chunks = []
    cursor = from_date
    while cursor <= to_date:
        chunk_end = min(cursor + timedelta(days=7), to_date + timedelta(days=1))
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks


def _fetch_agent_names() -> dict[int, str]:
    names: dict[int, str] = {}
    page = 1
    while True:
        agents = fs._fd_get("agents", {"per_page": 100, "page": page})
        if not agents:
            break
        for a in agents:
            names[a["id"]] = (a.get("contact") or {}).get("name") or ""
        if len(agents) < 100:
            break
        page += 1
    return names


def extract_empresa(empresa: str, from_date: date, to_date: date) -> list[dict]:
    chunks = _week_chunks(from_date, to_date)
    print(f"\n{'='*60}")
    print(f"Empresa: {empresa} | {from_date} -> {to_date} | {len(chunks)} chunk(s) semanal(is)")
    print(f"{'='*60}")

    tickets_by_id: dict[int, dict] = {}
    stats_by_id: dict[int, dict] = {}
    for i, (start, end) in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] buscando {start} -> {end} ...", end=" ", flush=True)
        tickets = fs._search_chunk(empresa, start, end)
        print(f"{len(tickets)} tickets encontrados", end=" ", flush=True)

        resolved = [t for t in tickets if t.get("status") in (4, 5)]
        open_count = len(tickets) - len(resolved)

        with fs.ThreadPoolExecutor(max_workers=fs.CONCURRENCY) as pool:
            futures = {pool.submit(fs._get_ticket_stats, t["id"]): t["id"] for t in resolved}
            for fut in fs.as_completed(futures):
                s = fut.result()
                stats_by_id[s["id"]] = s
                fs.time.sleep(fs.RATE_DELAY_S / fs.CONCURRENCY)

        for t in tickets:
            tickets_by_id[t["id"]] = t

        print(f"-> {len(resolved)} resolvidos | {open_count} abertos")

    print(f"  Total (dedup por id) para '{empresa}': {len(tickets_by_id)}")
    print("  Buscando lista de agentes...")
    agent_names = _fetch_agent_names()

    rows = []
    for ticket_id, t in tickets_by_id.items():
        cf = t.get("custom_fields") or {}
        stats = stats_by_id.get(ticket_id, {})
        created = _parse_utc(t.get("created_at"))
        first_resp = _parse_utc(stats.get("first_responded_at"))
        resolved_at = _parse_utc(stats.get("resolved_at"))
        closed_at = _parse_utc(stats.get("closed_at"))
        responder_id = t.get("responder_id")

        rows.append({
            "ID do ticket": ticket_id,
            "Assunto": t.get("subject") or "",
            "Tipo": cf.get("cf_mercado") or "",
            "Agente": agent_names.get(responder_id, "No Agent") if responder_id else "No Agent",
            "Hora da criação": _fmt_dt_brt(created),
            "Tempo até a primeira resposta (em horas)": _fmt_duration(created, first_resp),
            "Tempo de resolução (em horas)": _fmt_duration(created, resolved_at),
            "Hora da resolução": _fmt_dt_brt(resolved_at),
            "Hora do fechamento": _fmt_dt_brt(closed_at),
            "Tipo de demanda": cf.get("cf_tipo_de_demanda") or "",
        })

    return rows


def main():
    parser = argparse.ArgumentParser(description="Extrai tickets Freshdesk para Excel (padrao relatorio EMAIL)")
    parser.add_argument("--empresa", nargs="+", required=True,
                         help='Nome(s) da empresa (cf_empresa). Ex: --empresa "ACCIONA"')
    parser.add_argument("--from", dest="from_date", required=True, help="Data inicio YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="Data fim YYYY-MM-DD (inclusive)")
    parser.add_argument("--out", required=True, help="Caminho do arquivo .xlsx de saida")
    args = parser.parse_args()

    from_date = date.fromisoformat(args.from_date)
    to_date = date.fromisoformat(args.to_date)

    all_rows = []
    for empresa in args.empresa:
        all_rows.extend(extract_empresa(empresa, from_date, to_date))

    df = pd.DataFrame(all_rows, columns=COLUMNS)
    df.to_excel(args.out, index=False, sheet_name="Sheet1")
    print(f"Excel gerado: {args.out} ({len(df)} linhas)")


if __name__ == "__main__":
    main()

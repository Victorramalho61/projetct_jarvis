"""Sobe os dumps de backup (e o secrets_*.zip.enc, se presente) do Jarvis pro OneDrive do Victor (grupovoetur-my.sharepoint.com).

Uso: python scripts/upload_backup_onedrive.py <pasta_do_backup_local> <YYYYMMDD_HHMMSS>

Estrutura no OneDrive:
  Backup/jarvis_dump_{YYYYMMDD}/            — diario, retencao de 30 dias (pastas mais antigas sao apagadas)
  Backup/jarvis_dump_mensal_{YYYYMM}/        — copia extra no dia 1 de cada mes, sem rotacao automatica
"""
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from db import get_supabase
from services.microsoft_graph import GraphClient, get_access_token

_DAILY_RE = re.compile(r"^jarvis_dump_(\d{8})$")
_RETENTION_DAYS = 30


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    if len(sys.argv) < 3:
        _log("uso: upload_backup_onedrive.py <pasta_local> <timestamp YYYYMMDD_HHMMSS>")
        return 1

    backup_dir = Path(sys.argv[1])
    timestamp = sys.argv[2]
    day_str = timestamp.split("_")[0]  # YYYYMMDD

    if not backup_dir.is_dir():
        _log(f"ERRO: pasta nao encontrada: {backup_dir}")
        return 1

    dump_files = sorted(backup_dir.glob("*.dump"))
    if not dump_files:
        _log(f"ERRO: nenhum .dump encontrado em {backup_dir}")
        return 1
    files = dump_files + sorted(backup_dir.glob("*.enc"))

    db = get_supabase()
    acc_res = db.table("connected_accounts").select("*").eq("provider", "microsoft").execute()
    if not acc_res.data:
        _log("ERRO: nenhuma conta Microsoft conectada (connected_accounts)")
        return 1
    account = acc_res.data[0]

    try:
        token = get_access_token(account, db)
    except Exception as exc:
        _log(f"ERRO ao obter access token: {exc}")
        return 1

    graph = GraphClient(token)

    daily_folder = f"Backup/jarvis_dump_{day_str}"
    _log(f"Upload diario -> {daily_folder} ({len(files)} arquivo(s))")
    for f in files:
        size_mb = f.stat().st_size / 1024 / 1024
        _log(f"  {f.name} ({size_mb:.1f}MB)...")
        try:
            graph.upload_large_file(daily_folder, f.name, str(f))
            _log(f"  {f.name} — ok")
        except Exception as exc:
            _log(f"  ERRO ao subir {f.name}: {exc}")
            return 1

    # Copia mensal no dia 1
    day_num = int(day_str[6:8])
    if day_num == 1:
        month_str = day_str[:6]  # YYYYMM
        monthly_folder = f"Backup/jarvis_dump_mensal_{month_str}"
        _log(f"Dia 1 do mes — copia mensal -> {monthly_folder}")
        for f in files:
            try:
                graph.upload_large_file(monthly_folder, f.name, str(f))
                _log(f"  {f.name} — ok (mensal)")
            except Exception as exc:
                _log(f"  ERRO ao subir {f.name} (mensal): {exc}")

    # Rotacao: apaga pastas diarias com mais de 30 dias
    _log(f"Rotacao: removendo pastas diarias com mais de {_RETENTION_DAYS} dias...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    children = graph.list_children("Backup")
    removed = 0
    for item in children:
        if not item.get("folder"):
            continue
        m = _DAILY_RE.match(item.get("name", ""))
        if not m:
            continue
        try:
            folder_date = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if folder_date < cutoff:
            _log(f"  removendo {item['name']} (mais de {_RETENTION_DAYS} dias)")
            graph.delete_item_by_path(f"Backup/{item['name']}")
            removed += 1
    _log(f"Rotacao concluida — {removed} pasta(s) removida(s)")
    _log("Upload OneDrive concluido com sucesso")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import logging
from datetime import datetime, timedelta, timezone

from db import get_supabase

logger = logging.getLogger(__name__)

_RETENTION_DAYS: dict[str, int] = {
    "app_logs":       90,
    "system_checks":  30,
    "quality_metrics": 60,
    "security_alerts": 90,
    "agent_runs":     30,
}

# Coluna de timestamp varia por tabela — system_checks usa checked_at,
# quality_metrics usa measured_at, agent_runs usa started_at.
_TIMESTAMP_COLUMN: dict[str, str] = {
    "app_logs":       "created_at",
    "system_checks":  "checked_at",
    "quality_metrics": "measured_at",
    "security_alerts": "created_at",
    "agent_runs":     "started_at",
}


async def run_data_retention() -> None:
    """Remove registros antigos das tabelas de dados temporais."""
    db = get_supabase()
    now = datetime.now(timezone.utc)
    total_deleted = 0

    for table, days in _RETENTION_DAYS.items():
        cutoff = (now - timedelta(days=days)).isoformat()
        ts_col = _TIMESTAMP_COLUMN[table]
        try:
            db.table(table).delete().lt(ts_col, cutoff).execute()
            logger.info("Retention %s: removed rows older than %d days", table, days)
            total_deleted += 1
        except Exception as exc:
            logger.warning("Retention %s: falhou — %s", table, exc)

    logger.info("Data retention concluída: %d tabelas processadas", total_deleted)

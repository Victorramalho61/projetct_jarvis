"""
Ferramentas de acesso direto ao PostgreSQL para o db_dba_agent.
Usa psycopg2 para acessar views de sistema (pg_stat_*) n�o dispon�veis via REST.
"""
import logging

logger = logging.getLogger(__name__)


def _get_conn():
    import psycopg2
    from db import get_settings
    url = get_settings().postgres_direct_url
    if not url:
        raise RuntimeError("POSTGRES_DIRECT_URL n�o configurado")
    return psycopg2.connect(url, connect_timeout=10)


def get_table_sizes() -> list[dict]:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                schemaname,
                tablename,
                pg_total_relation_size(schemaname||'.'||tablename) AS total_bytes,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)
                    - pg_relation_size(schemaname||'.'||tablename)) AS index_size
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY total_bytes DESC
            LIMIT 30
        """)
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.error("get_table_sizes: %s", exc)
        return []


def get_missing_indexes() -> list[dict]:
    """Tabelas com muitos seq_scans e poucas varreduras de �ndice � candidatas a novos �ndices."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                schemaname,
                tablename,
                seq_scan,
                idx_scan,
                n_live_tup,
                CASE WHEN idx_scan = 0 THEN 'sem_indice'
                     WHEN seq_scan > idx_scan * 2 THEN 'seq_dominante'
                     ELSE 'ok' END AS status
            FROM pg_stat_user_tables
            WHERE n_live_tup > 500
              AND seq_scan > 100
            ORDER BY seq_scan DESC
            LIMIT 20
        """)
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.error("get_missing_indexes: %s", exc)
        return []


def get_slow_queries() -> list[dict]:
    """Top queries por tempo m�dio de execu��o (requer pg_stat_statements)."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                LEFT(query, 200) AS query_preview,
                calls,
                ROUND(mean_exec_time::numeric, 2) AS mean_ms,
                ROUND(total_exec_time::numeric, 2) AS total_ms,
                ROUND(stddev_exec_time::numeric, 2) AS stddev_ms,
                rows
            FROM pg_stat_statements
            WHERE calls > 10
            ORDER BY mean_exec_time DESC
            LIMIT 20
        """)
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.warning("get_slow_queries: pg_stat_statements indispon�vel � %s", exc)
        return []


def get_index_usage() -> list[dict]:
    """�ndices nunca ou raramente usados (candidatos a remo��o)."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan,
                pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
            FROM pg_stat_user_indexes
            WHERE idx_scan < 10
            ORDER BY pg_relation_size(indexrelid) DESC
            LIMIT 20
        """)
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.error("get_index_usage: %s", exc)
        return []


def get_table_bloat() -> list[dict]:
    """Tabelas com alto percentual de dead tuples (candidatas a VACUUM)."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                schemaname,
                tablename,
                n_live_tup,
                n_dead_tup,
                CASE WHEN n_live_tup + n_dead_tup = 0 THEN 0
                     ELSE ROUND(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
                END AS dead_ratio_pct,
                last_vacuum,
                last_autovacuum
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 100
            ORDER BY dead_ratio_pct DESC
            LIMIT 20
        """)
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.error("get_table_bloat: %s", exc)
        return []


def get_connection_stats() -> dict:
    """Conex�es ativas por estado."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT state, COUNT(*) as count
            FROM pg_stat_activity
            WHERE pid <> pg_backend_pid()
            GROUP BY state
        """)
        result = {row[0] or "unknown": row[1] for row in cur.fetchall()}
        cur.execute("SHOW max_connections")
        result["max_connections"] = int(cur.fetchone()[0])
        conn.close()
        return result
    except Exception as exc:
        logger.error("get_connection_stats: %s", exc)
        return {}


def get_vacuum_status() -> list[dict]:
    """Status de VACUUM por tabela."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                schemaname,
                tablename,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                vacuum_count,
                autovacuum_count
            FROM pg_stat_user_tables
            ORDER BY COALESCE(last_autovacuum, last_vacuum, '1970-01-01') ASC
            LIMIT 20
        """)
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.error("get_vacuum_status: %s", exc)
        return []


def get_blocking_queries() -> list[dict]:
    """Queries que estão bloqueando outras (locks)."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                blocking.pid AS blocking_pid,
                blocking.query AS blocking_query,
                ROUND(EXTRACT(EPOCH FROM (NOW() - blocking.query_start))::numeric, 1) AS blocking_secs,
                blocked.pid AS blocked_pid,
                blocked.query AS blocked_query,
                ROUND(EXTRACT(EPOCH FROM (NOW() - blocked.query_start))::numeric, 1) AS blocked_secs
            FROM pg_stat_activity blocked
            JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
            WHERE blocked.cardinality(pg_blocking_pids(blocked.pid)) > 0
            ORDER BY blocking_secs DESC
            LIMIT 20
        """)
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.warning("get_blocking_queries: %s", exc)
        return []


def get_long_running_queries(threshold_secs: int = 60) -> list[dict]:
    """Queries rodando há mais de threshold_secs segundos."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                pid,
                usename,
                state,
                LEFT(query, 300) AS query_preview,
                ROUND(EXTRACT(EPOCH FROM (NOW() - query_start))::numeric, 1) AS running_secs,
                wait_event_type,
                wait_event
            FROM pg_stat_activity
            WHERE state != 'idle'
              AND query_start < NOW() - interval '%s seconds'
              AND pid <> pg_backend_pid()
            ORDER BY running_secs DESC
            LIMIT 20
        """, (threshold_secs,))
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return result
    except Exception as exc:
        logger.error("get_long_running_queries: %s", exc)
        return []


def terminate_query(pid: int, force: bool = False) -> str:
    """Termina query travada. force=True usa pg_terminate_backend (kill), False usa pg_cancel_backend."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        if force:
            cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        else:
            cur.execute("SELECT pg_cancel_backend(%s)", (pid,))
        result = cur.fetchone()[0]
        conn.close()
        action = "terminado" if force else "cancelado"
        return f"PID {pid} {action}: {result}"
    except Exception as exc:
        logger.error("terminate_query pid=%s: %s", pid, exc)
        raise


def run_vacuum_analyze(table: str | None = None) -> str:
    """Executa VACUUM ANALYZE em tabela específica ou em todas as user tables."""
    try:
        conn = _get_conn()
        conn.autocommit = True
        cur = conn.cursor()
        if table:
            cur.execute(f"VACUUM ANALYZE {table}")
            result = f"VACUUM ANALYZE executado em {table}"
        else:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            tables = [r[0] for r in cur.fetchall()]
            for t in tables:
                try:
                    cur.execute(f"VACUUM ANALYZE public.{t}")
                except Exception as e:
                    logger.warning("VACUUM ANALYZE public.%s: %s", t, e)
            result = f"VACUUM ANALYZE executado em {len(tables)} tabelas"
        conn.close()
        return result
    except Exception as exc:
        logger.error("run_vacuum_analyze: %s", exc)
        raise


def purge_old_app_logs(days: int = 90) -> str:
    """Remove app_logs mais antigos que X dias para controle de tamanho."""
    try:
        conn = _get_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM app_logs WHERE created_at < NOW() - interval '%s days'", (days,)
        )
        deleted = cur.rowcount
        conn.close()
        return f"Expurgo: {deleted} logs removidos (>{days} dias)"
    except Exception as exc:
        logger.error("purge_old_app_logs: %s", exc)
        raise


def purge_old_agent_runs(days: int = 30) -> str:
    """Remove agent_runs mais antigos que X dias (status=success)."""
    try:
        conn = _get_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM agent_runs WHERE status = 'success' AND started_at < NOW() - interval '%s days'",
            (days,)
        )
        deleted = cur.rowcount
        conn.close()
        return f"Expurgo: {deleted} agent_runs de sucesso removidos (>{days} dias)"
    except Exception as exc:
        logger.error("purge_old_agent_runs: %s", exc)
        raise


def run_pg_dump_backup() -> dict:
    """Executa pg_dump e salva em /tmp/backup_<timestamp>.sql. Retorna path e tamanho."""
    import os
    import subprocess
    from db import get_settings
    try:
        url = get_settings().postgres_direct_url
        if not url:
            raise RuntimeError("POSTGRES_DIRECT_URL não configurado")
        ts = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = f"/tmp/backup_{ts}.sql"
        result = subprocess.run(
            ["pg_dump", "--no-password", url, "-f", path],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump falhou: {result.stderr[:300]}")
        size = os.path.getsize(path)
        return {"path": path, "size_bytes": size, "timestamp": ts, "ok": True}
    except Exception as exc:
        logger.error("run_pg_dump_backup: %s", exc)
        return {"ok": False, "error": str(exc)}


def validate_backup(path: str) -> dict:
    """Valida arquivo de backup verificando se é SQL válido (grep por CREATE/INSERT)."""
    import os
    try:
        if not os.path.exists(path):
            return {"valid": False, "error": f"Arquivo não encontrado: {path}"}
        size = os.path.getsize(path)
        if size < 1000:
            return {"valid": False, "error": f"Arquivo muito pequeno ({size} bytes)"}
        with open(path, "r", errors="ignore") as f:
            head = f.read(4096)
        has_pg_dump = "PostgreSQL database dump" in head
        has_create = "CREATE TABLE" in head or "CREATE INDEX" in head
        valid = has_pg_dump or has_create
        return {"valid": valid, "size_bytes": size, "path": path, "has_pg_header": has_pg_dump}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


def execute_safe_sql(sql: str) -> str:
    """Executa SQL seguro (apenas ANALYZE, CREATE INDEX CONCURRENTLY, REINDEX CONCURRENTLY)."""
    sql_upper = sql.strip().upper()
    allowed_prefixes = ("ANALYZE", "CREATE INDEX CONCURRENTLY", "REINDEX CONCURRENTLY")
    if not any(sql_upper.startswith(p) for p in allowed_prefixes):
        raise ValueError(f"SQL n�o permitido para execu��o autom�tica: {sql[:80]}")
    try:
        conn = _get_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        conn.close()
        return f"Executado com sucesso: {sql[:100]}"
    except Exception as exc:
        logger.error("execute_safe_sql: %s", exc)
        raise

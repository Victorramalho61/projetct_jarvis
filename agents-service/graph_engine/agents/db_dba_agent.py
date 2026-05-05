"""
DBA Agent — age como DBA PostgreSQL sênior: analisa saúde do banco,
detecta gargalos, executa ações seguras automaticamente (ANALYZE, CREATE INDEX CONCURRENTLY)
e propõe para o CTO ações que exigem revisão humana.
"""
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_AUTO_SAFE_PREFIXES = ("ANALYZE", "CREATE INDEX CONCURRENTLY", "REINDEX CONCURRENTLY")


def _collect_snapshot() -> dict:
    from graph_engine.tools.db_admin_tools import (
        get_table_sizes,
        get_missing_indexes,
        get_slow_queries,
        get_index_usage,
        get_table_bloat,
        get_connection_stats,
        get_vacuum_status,
        get_blocking_queries,
        get_long_running_queries,
    )
    return {
        "table_sizes":      get_table_sizes(),
        "missing_indexes":  get_missing_indexes(),
        "slow_queries":     get_slow_queries(),
        "index_usage":      get_index_usage(),
        "table_bloat":      get_table_bloat(),
        "connection_stats": get_connection_stats(),
        "vacuum_status":    get_vacuum_status(),
        "blocking_queries": get_blocking_queries(),
        "long_running":     get_long_running_queries(threshold_secs=120),
        "captured_at":      datetime.now(timezone.utc).isoformat(),
    }


def _save_snapshot(snapshot: dict) -> None:
    try:
        from db import get_supabase
        db = get_supabase()
        db.table("db_health_snapshots").insert({
            "table_sizes":     snapshot.get("table_sizes", {}),
            "index_usage":     snapshot.get("index_usage", []),
            "slow_queries":    snapshot.get("slow_queries", []),
            "table_bloat":     snapshot.get("table_bloat", {}),
            "connection_stats": snapshot.get("connection_stats", {}),
            "vacuum_status":   snapshot.get("vacuum_status", {}),
            "missing_indexes": snapshot.get("missing_indexes", []),
            "summary":         f"Snapshot DBA {snapshot['captured_at']}",
        }).execute()
    except Exception as exc:
        logger.warning("db_dba_agent: erro ao salvar snapshot: %s", exc)


def _parse_proposals(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except Exception:
        return []


def _handle_blocking_queries(blocking: list[dict], decisions: list) -> None:
    """Cancela queries bloqueando por mais de 5 minutos."""
    from graph_engine.tools.db_admin_tools import terminate_query
    for b in blocking:
        secs = b.get("blocking_secs", 0) or 0
        if secs > 300:
            pid = b.get("blocking_pid")
            if pid:
                try:
                    result = terminate_query(pid, force=False)
                    decisions.append(f"Query bloqueante cancelada (PID {pid}, {secs:.0f}s): {result}")
                    logger.info("db_dba_agent: %s", result)
                except Exception as exc:
                    logger.warning("db_dba_agent: falha ao cancelar PID %s: %s", pid, exc)


def _run_maintenance(snapshot: dict, decisions: list, findings: list) -> None:
    """Executa VACUUM ANALYZE em tabelas com bloat alto, purge de dados antigos e backup periódico."""
    from graph_engine.tools.db_admin_tools import (
        run_vacuum_analyze, purge_old_app_logs, purge_old_agent_runs,
        run_pg_dump_backup, validate_backup,
    )
    from db import get_supabase

    db = get_supabase()

    # VACUUM ANALYZE para tabelas com >30% dead tuples
    bloat_tables = [t for t in snapshot.get("table_bloat", []) if t.get("dead_ratio_pct", 0) > 30]
    for t in bloat_tables[:3]:
        table = f"{t.get('schemaname','public')}.{t.get('tablename','')}"
        try:
            result = run_vacuum_analyze(table)
            decisions.append(f"VACUUM ANALYZE: {result}")
        except Exception as exc:
            logger.warning("db_dba_agent: vacuum %s: %s", table, exc)

    # Expurgo de logs antigos (> 90 dias)
    try:
        purge_result = purge_old_app_logs(days=90)
        decisions.append(purge_result)
    except Exception as exc:
        logger.warning("db_dba_agent: expurgo logs: %s", exc)

    # Expurgo de agent_runs de sucesso (> 30 dias)
    try:
        purge_runs = purge_old_agent_runs(days=30)
        decisions.append(purge_runs)
    except Exception as exc:
        logger.warning("db_dba_agent: expurgo agent_runs: %s", exc)

    # Backup (apenas se último backup foi há mais de 12h)
    try:
        last_backup = (
            db.table("db_health_snapshots")
            .select("created_at")
            .not_.is_("summary", "null")
            .ilike("summary", "%backup%")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        do_backup = True
        if last_backup:
            from datetime import datetime, timezone
            last_ts = datetime.fromisoformat(last_backup[0]["created_at"].replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
            do_backup = age_h > 12

        if do_backup:
            backup = run_pg_dump_backup()
            if backup.get("ok"):
                validation = validate_backup(backup["path"])
                if validation.get("valid"):
                    decisions.append(f"Backup realizado e validado: {backup['path']} ({backup['size_bytes']//1024}KB)")
                    db.table("db_health_snapshots").insert({
                        "summary": f"backup: {backup['path']} ({backup['size_bytes']//1024}KB)",
                        "table_sizes": {}, "index_usage": [], "slow_queries": [],
                        "table_bloat": {}, "connection_stats": {}, "vacuum_status": {},
                        "missing_indexes": [],
                    }).execute()
                else:
                    findings.append({"type": "backup_invalid", "detail": validation})
                    logger.error("db_dba_agent: backup inválido: %s", validation)
            else:
                findings.append({"type": "backup_failed", "error": backup.get("error")})
                logger.error("db_dba_agent: backup falhou: %s", backup.get("error"))
    except Exception as exc:
        logger.warning("db_dba_agent: rotina de backup: %s", exc)


def _handle_proposal(proposal: dict, _msg: dict) -> tuple[bool, str]:
    """Executa SQL seguro de proposals DBA aprovadas por humanos."""
    from graph_engine.tools.db_admin_tools import execute_safe_sql

    sql = proposal.get("sql_proposal") or proposal.get("proposed_fix") or ""
    if not sql or not sql.strip():
        return False, "Proposal DBA sem SQL definido — implementação manual necessária"

    sql_upper = sql.strip().upper()
    if any(sql_upper.startswith(p) for p in _AUTO_SAFE_PREFIXES):
        try:
            result = execute_safe_sql(sql)
            return True, f"SQL executado: {result[:200]}"
        except Exception as exc:
            return False, f"Falha ao executar SQL: {exc}"

    action = proposal.get("proposed_action", "")[:200] or proposal.get("title", "")[:100]
    return False, f"SQL requer revisão manual do DBA (não é ANALYZE/INDEX CONCURRENTLY): {action}"


def run(state: dict) -> dict:
    from graph_engine.llm import get_reasoning_llm
    from graph_engine.tools.supabase_tools import insert_improvement_proposal, insert_agent_event, send_agent_message
    from graph_engine.tools.db_admin_tools import execute_safe_sql
    from graph_engine.tools.proposal_executor import process_inbox_proposals
    from db import get_supabase
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []

    db = get_supabase()
    processed = process_inbox_proposals("db_dba_agent", db, _handle_proposal, decisions)
    if processed:
        logger.info("db_dba_agent: %d proposals da inbox processadas", processed)

    try:
        snapshot = _collect_snapshot()
    except Exception as exc:
        logger.error("db_dba_agent: falha ao coletar snapshot: %s", exc)
        findings.append({"agent": "db_dba_agent", "error": str(exc)})
        return {"findings": findings, "decisions": decisions, "next_agent": "END"}

    _save_snapshot(snapshot)

    bloat_tables = [t for t in snapshot.get("table_bloat", []) if t.get("dead_ratio_pct", 0) > 20]
    missing = snapshot.get("missing_indexes", [])
    connections = snapshot.get("connection_stats", {})

    blocking = snapshot.get("blocking_queries", [])
    long_running = snapshot.get("long_running", [])

    findings.append({
        "agent": "db_dba_agent",
        "tables_with_bloat": len(bloat_tables),
        "tables_missing_index": len(missing),
        "active_connections": connections.get("active", 0),
        "max_connections": connections.get("max_connections", "?"),
        "blocking_queries": len(blocking),
        "long_running_queries": len(long_running),
    })

    # Cancelar queries bloqueantes há mais de 5 min
    if blocking:
        _handle_blocking_queries(blocking, decisions)
        findings.append({"type": "blocking_queries", "count": len(blocking), "sample": blocking[:2]})

    # Queries longas (> 2 min)
    if long_running:
        findings.append({"type": "long_running_queries", "count": len(long_running), "sample": long_running[:3]})

    # Manutenção: VACUUM, expurgo, backup
    _run_maintenance(snapshot, decisions, findings)

    system_prompt = (
        "Você é um DBA PostgreSQL sênior com 15 anos de experiência em bancos de alta disponibilidade. "
        "Analise os dados de saúde do banco de dados PostgreSQL do sistema Jarvis e identifique problemas. "
        "Retorne SOMENTE um array JSON com propostas de melhoria:\n"
        '[{"type": "index|vacuum|rewrite|partition|config", "table": str, '
        '"problem": str, "sql_proposal": str, '
        '"expected_gain": str, "risk": "low|medium|high", '
        '"auto_applicable": bool, "priority": "critical|high|medium|low"}]\n'
        "auto_applicable=true APENAS para ANALYZE e CREATE INDEX CONCURRENTLY. "
        "Nunca auto_applicable=true para DROP, ALTER TABLE, ou particionamento."
    )

    snapshot_summary = json.dumps({
        "missing_indexes": snapshot.get("missing_indexes", [])[:5],
        "table_bloat": bloat_tables[:5],
        "slow_queries": snapshot.get("slow_queries", [])[:5],
        "index_usage_low": [i for i in snapshot.get("index_usage", []) if i.get("idx_scan", 99) < 5][:5],
        "connections": connections,
    }, ensure_ascii=False, default=str)

    proposals_data = []
    try:
        llm = get_reasoning_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Dados do banco:\n{snapshot_summary}"),
        ])
        proposals_data = _parse_proposals(response.content)
    except Exception as exc:
        logger.error("db_dba_agent: erro LLM: %s", exc)

    for p in proposals_data:
        sql = p.get("sql_proposal", "")
        auto = p.get("auto_applicable", False)

        if auto and sql:
            sql_upper = sql.strip().upper()
            if any(sql_upper.startswith(prefix) for prefix in _AUTO_SAFE_PREFIXES):
                try:
                    result = execute_safe_sql(sql)
                    decisions.append(f"SQL executado automaticamente: {result[:100]}")
                    continue
                except Exception as exc:
                    logger.error("db_dba_agent: falha ao executar SQL auto: %s", exc)
                    p["auto_applicable"] = False

        try:
            insert_improvement_proposal(
                source_agent="db_dba_agent",
                proposal_type=p.get("type", "index"),
                title=f"DBA: {p.get('problem', 'Melhoria de banco')[:80]}",
                description=p.get("problem", ""),
                sql_proposal=sql,
                priority=p.get("priority", "medium"),
                risk=p.get("risk", "medium"),
                auto_implementable=False,
                expected_gain=p.get("expected_gain", ""),
            )
            decisions.append(f"Proposal DBA inserida: {p.get('problem', '')[:60]}")
        except Exception as exc:
            logger.error("db_dba_agent: erro ao inserir proposal: %s", exc)

    if len(bloat_tables) > 3 or connections.get("active", 0) > connections.get("max_connections", 100) * 0.8:
        try:
            insert_agent_event(
                event_type="db_health_alert",
                source="db_dba_agent",
                payload={"bloat_tables": len(bloat_tables), "connections": connections},
                priority="high",
            )
        except Exception as exc:
            logger.warning("db_dba_agent: erro ao inserir evento: %s", exc)

    try:
        send_agent_message(
            from_agent="db_dba_agent",
            to_agent="log_strategic_advisor",
            message=(
                f"Snapshot DBA: {len(bloat_tables)} tabelas com bloat, "
                f"{len(missing)} candidatas a índice, "
                f"{len(blocking)} queries bloqueantes, "
                f"{len(long_running)} queries longas. "
                f"Ações executadas: {len(decisions)}."
            ),
            context={"snapshot_summary": snapshot_summary[:500]},
        )
    except Exception:
        pass

    # Handoff para infrastructure se bloat crítico ou conexões altas
    conn_pct = connections.get("active", 0) / max(connections.get("max_connections", 100), 1)
    if len(bloat_tables) > 5 or conn_pct > 0.7:
        try:
            insert_agent_event(
                event_type="db_health_alert",
                source="db_dba_agent",
                payload={
                    "bloat_tables": len(bloat_tables),
                    "connections": connections,
                    "blocking": len(blocking),
                    "long_running": len(long_running),
                },
                priority="high",
            )
        except Exception:
            pass

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "db_dba_run": datetime.now(timezone.utc).isoformat(),
            "proposals_count": len(proposals_data),
            "blocking_terminated": sum(1 for d in decisions if "bloqueante cancelada" in d),
            "backups_done": sum(1 for d in decisions if "Backup realizado" in d),
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

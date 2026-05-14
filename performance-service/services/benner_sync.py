import logging

from apscheduler.schedulers.background import BackgroundScheduler

_logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def sync_benner() -> dict:
    """Sincroniza employees e departments do Benner RH para o Supabase."""
    from db import get_supabase, get_settings, get_sql_connection
    from services.resilience import CircuitOpenError

    s = get_settings()
    if not s.sql_server_host:
        return {"synced_employees": 0, "synced_departments": 0, "skipped": True, "reason": "SQL_SERVER_HOST not configured"}

    try:
        conn = get_sql_connection()
    except CircuitOpenError as exc:
        _logger.warning("Benner sync skipped — circuit open: %s", exc)
        return {"synced_employees": 0, "synced_departments": 0, "error": str(exc)}
    except Exception as exc:
        _logger.error("Benner sync connection failed: %s", exc)
        return {"synced_employees": 0, "synced_departments": 0, "error": str(exc)}

    db = get_supabase()
    dept_count = 0
    emp_count = 0

    try:
        cursor = conn.cursor()

        # Sync departments
        cursor.execute("""
            SELECT DISTINCT
                CAST(d.CodigoCentro AS NVARCHAR(50)) AS benner_id,
                d.DescricaoCentro AS name,
                NULL AS parent_id,
                NULL AS director,
                CAST(d.CodigoCentro AS NVARCHAR(50)) AS cost_center,
                e.Empresa AS company_id
            FROM RHFuncionarios e
            INNER JOIN RHCentrosCusto d ON d.CodigoCentro = e.CodigoCentro
            WHERE e.Situacao = 'A'
        """)
        departments = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        for dept in departments:
            db.table("performance_departments").upsert({
                "name": dept["name"],
                "cost_center": dept.get("cost_center"),
                "company_id": dept.get("company_id"),
                "synced_at": "now()",
            }, on_conflict="cost_center").execute()
            dept_count += 1

        # Sync employees
        cursor.execute("""
            SELECT
                CAST(e.Matricula AS NVARCHAR(50)) AS benner_id,
                e.NomeFuncionario AS name,
                e.Email AS email,
                CAST(d.CodigoCentro AS NVARCHAR(50)) AS dept_cost_center,
                e.Cargo AS cargo
            FROM RHFuncionarios e
            LEFT JOIN RHCentrosCusto d ON d.CodigoCentro = e.CodigoCentro
            WHERE e.Situacao = 'A'
        """)
        employees = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        for emp in employees:
            dept_result = db.table("performance_departments").select("id").eq("cost_center", emp.get("dept_cost_center") or "").execute()
            dept_id = dept_result.data[0]["id"] if dept_result.data else None
            db.table("performance_employees").upsert({
                "benner_id": emp["benner_id"],
                "name": emp["name"],
                "email": emp.get("email"),
                "department_id": dept_id,
                "active": True,
                "synced_at": "now()",
            }, on_conflict="benner_id").execute()
            emp_count += 1

        cursor.close()
        conn.close()
        _logger.info("Benner sync complete: %d departments, %d employees", dept_count, emp_count)
        return {"synced_employees": emp_count, "synced_departments": dept_count}

    except Exception as exc:
        _logger.error("Benner sync error: %s", exc)
        return {"synced_employees": emp_count, "synced_departments": dept_count, "error": str(exc)}


def start() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(sync_benner, "cron", hour=2, minute=0, id="benner_sync")
    _scheduler.start()
    _logger.info("Benner sync scheduler started (daily at 02:00)")


def stop() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)

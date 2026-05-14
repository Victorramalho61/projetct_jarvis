import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_logger = logging.getLogger(__name__)
_scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

_PHASE_TO_STATUS = {
    "goal_signing": "draft",
    "self_assessment": "pending_self",
    "manager_review": "pending_manager",
    "acknowledgment": "pending_ack",
}

_PHASE_LABELS = {
    "goal_signing": "Assinatura de Metas",
    "self_assessment": "Autoavaliação",
    "manager_review": "Avaliação do Gestor",
    "acknowledgment": "Ciência do Resultado",
}

_DEFAULT_MAX_DAYS = {
    "goal_signing": 5,
    "self_assessment": 10,
    "manager_review": 7,
    "acknowledgment": 5,
}

_WARN_DAYS_BEFORE = 3


def _run_sla_check() -> None:
    try:
        from db import get_supabase, get_settings
        from services.email import send_email

        db = get_supabase()
        s = get_settings()

        open_cycles = (
            db.table("performance_cycles")
            .select("id,name")
            .in_("status", ["open", "evaluation"])
            .execute()
            .data
        )

        now = datetime.now(tz=timezone.utc)
        today_str = now.date().isoformat()
        frontend_url = s.allowed_origins.split(",")[0].strip().rstrip("/")

        for cycle in open_cycles:
            cycle_id = cycle["id"]
            cycle_name = cycle["name"]

            sla_rows = (
                db.table("performance_sla_configs")
                .select("phase,max_days")
                .eq("cycle_id", cycle_id)
                .execute()
                .data
            )
            config_map = {r["phase"]: r["max_days"] for r in sla_rows}

            employees = db.table("performance_employees").select("*").eq("active", True).execute().data
            emp_map = {e["id"]: e for e in employees}

            for phase, status in _PHASE_TO_STATUS.items():
                max_days = config_map.get(phase, _DEFAULT_MAX_DAYS[phase])
                warn_at = max_days - _WARN_DAYS_BEFORE

                if status == "draft":
                    pending = db.table("performance_goals").select("*").eq("status", "draft").execute().data
                else:
                    pending = (
                        db.table("performance_reviews")
                        .select("*")
                        .eq("cycle_id", cycle_id)
                        .eq("status", status)
                        .execute()
                        .data
                    )

                for item in pending:
                    emp_id = item.get("employee_id") or item.get("owner_id")
                    if not emp_id:
                        continue
                    emp = emp_map.get(emp_id)
                    if not emp or not emp.get("email"):
                        continue

                    ref_dt = item.get("updated_at") or item.get("created_at")
                    if not ref_dt:
                        continue
                    if isinstance(ref_dt, str):
                        ref_dt = datetime.fromisoformat(ref_dt.replace("Z", "+00:00"))
                    days_elapsed = (now - ref_dt).days

                    if days_elapsed < warn_at:
                        continue

                    already_sent = (
                        db.table("performance_sla_reminder_log")
                        .select("id")
                        .eq("cycle_id", cycle_id)
                        .eq("employee_id", emp_id)
                        .eq("phase", phase)
                        .gte("sent_at", f"{today_str}T00:00:00+00:00")
                        .execute()
                        .data
                    )
                    if already_sent:
                        continue

                    days_remaining = max(0, max_days - days_elapsed)
                    days_overdue = max(0, days_elapsed - max_days)
                    phase_label = _PHASE_LABELS[phase]

                    if days_overdue > 0:
                        timing = f"{days_overdue} dia(s) em atraso"
                    else:
                        timing = f"vence em {days_remaining} dia(s)"

                    html = f"""
                    <p>Olá, {emp.get('name', 'Colaborador')}!</p>
                    <p>Você possui uma pendência em aberto no ciclo <strong>{cycle_name}</strong>:</p>
                    <p><strong>Fase:</strong> {phase_label}<br>
                    <strong>Prazo:</strong> {timing}</p>
                    <p><a href="{frontend_url}/desempenho">Acessar Gestão de Desempenho</a></p>
                    """
                    success = send_email(
                        to_email=emp["email"],
                        display_name=emp.get("name", ""),
                        subject=f"Lembrete de SLA — {phase_label} | {cycle_name}",
                        html=html,
                    )
                    if success:
                        db.table("performance_sla_reminder_log").insert({
                            "cycle_id": cycle_id,
                            "employee_id": emp_id,
                            "phase": phase,
                            "sent_by": None,
                        }).execute()

    except Exception as exc:
        _logger.error("SLA scheduler error: %s", exc)


def start() -> None:
    _scheduler.add_job(
        _run_sla_check,
        CronTrigger(hour=8, minute=0, timezone="America/Sao_Paulo"),
        id="sla_daily_check",
        replace_existing=True,
    )
    _scheduler.start()
    _logger.info("SLA scheduler started")


def stop() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)

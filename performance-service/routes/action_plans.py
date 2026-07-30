"""Plano de Ação - Feedback — painel do RH.

Feature aditiva: identifica competências com nota final 1 ou 2 (pós Análise RH,
se houve — a autoavaliação nunca entra nessa conta) após a ciência do
colaborador, permite ao RH disparar manualmente um plano de ação por
competência para o gestor preencher, e depois monitorar 4 checkpoints
trimestrais (12 meses), também disparados manualmente pelo RH.

Não importa nada de routes/public.py, services/ciencia.py nem toca na lógica
de calibração de routes/admin.py — só leitura (SELECT) das tabelas legadas.
"""
import csv
import io
import logging
import time
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import require_role
from db import get_supabase, get_settings
from services.audit import log_action

router = APIRouter(prefix="/api/performance/action-plans")
_logger = logging.getLogger(__name__)

_RH_ADMIN = ("admin", "rh")

# Pausa entre envios em massa — evita rajada que o Office 365 trata como abuso.
EMAIL_PACING_SECONDS = 1.5

# Fase 'sent' sem resposta há mais desse tanto de dias -> aparece como lembrete sugerido.
REMINDER_AFTER_DAYS = 15

_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    max_day = _DAYS_IN_MONTH[month - 1]
    if month == 2 and _is_leap(year):
        max_day = 29
    return date(year, month, min(d.day, max_day))


def _frontend_url() -> str:
    s = get_settings()
    return s.allowed_origins.split(",")[0].strip().rstrip("/")


def _resolve_employees(db, ids: list[str]) -> dict[str, dict]:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    rows = (
        db.table("performance_employees")
        .select("id,name,cargo,email,has_corporate_email,company_id,branch_id,manager_id")
        .in_("id", ids)
        .execute()
        .data
    ) or []
    return {r["id"]: r for r in rows}


# ── Candidatos ao plano inicial ────────────────────────────────────────────────

def _build_candidates(db, cycle_id: str) -> list[dict]:
    reviews = (
        db.table("performance_reviews")
        .select("id,employee_id")
        .eq("cycle_id", cycle_id)
        .eq("is_self_evaluation", False)
        .in_("status", ["completed", "calibrated"])
        .execute()
        .data
    ) or []
    if not reviews:
        return []
    review_ids = [r["id"] for r in reviews]
    review_by_id = {r["id"]: r for r in reviews}

    acks = (
        db.table("performance_review_acknowledgments")
        .select("review_id")
        .in_("review_id", review_ids)
        .execute()
        .data
    ) or []
    acked_review_ids = {a["review_id"] for a in acks}
    if not acked_review_ids:
        return []

    all_scores = (
        db.table("performance_indicator_scores")
        .select("review_id,indicator_id,score,performance_indicators(name)")
        .in_("review_id", list(acked_review_ids))
        .execute()
        .data
    ) or []
    # Filtra em Python (não via .in_) para não depender de coerção int/float do driver.
    # Estritamente 1 ou 2 (não "<=2"): evita violar o CHECK (original_score IN (1,2))
    # de performance_action_plan_items caso algum score não-inteiro apareça.
    low_scores = [s for s in all_scores if float(s.get("score") or 0) in (1.0, 2.0)]
    if not low_scores:
        return []

    existing_plans = (
        db.table("performance_action_plans")
        .select("employee_id")
        .eq("cycle_id", cycle_id)
        .execute()
        .data
    ) or []
    already_has_plan = {p["employee_id"] for p in existing_plans}

    by_review: dict[str, list[dict]] = {}
    for s in low_scores:
        by_review.setdefault(s["review_id"], []).append(s)

    employee_ids = []
    for rid in by_review:
        rev = review_by_id.get(rid)
        if rev and rev["employee_id"] not in already_has_plan:
            employee_ids.append(rev["employee_id"])
    employee_ids = list(set(employee_ids))
    if not employee_ids:
        return []

    emp_map = _resolve_employees(db, employee_ids)
    manager_ids = [e.get("manager_id") for e in emp_map.values() if e.get("manager_id")]
    managers_map = _resolve_employees(db, manager_ids)

    result = []
    for rid, scores in by_review.items():
        rev = review_by_id.get(rid)
        if not rev or rev["employee_id"] not in emp_map:
            continue
        emp = emp_map[rev["employee_id"]]
        mgr = managers_map.get(emp.get("manager_id") or "")
        indicators = [
            {
                "indicator_id": s["indicator_id"],
                "name": (s.get("performance_indicators") or {}).get("name", "")
                if isinstance(s.get("performance_indicators"), dict) else "",
                "score": s["score"],
            }
            for s in scores
        ]
        result.append({
            "employee_id": emp["id"],
            "name": emp["name"],
            "cargo": emp.get("cargo", ""),
            "review_id": rid,
            "manager_id": emp.get("manager_id"),
            "manager_name": mgr.get("name", "") if mgr else "",
            "manager_email": mgr.get("email") if mgr else None,
            "manager_has_corporate_email": bool(mgr.get("has_corporate_email")) if mgr else False,
            "indicators": indicators,
        })
    return sorted(result, key=lambda r: r["name"])


@router.get("/candidates")
def list_candidates(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str,
) -> list[dict]:
    return _build_candidates(get_supabase(), cycle_id)


# ── Config do ciclo (data-base do acompanhamento trimestral) ──────────────────

@router.get("/cycle-config")
def get_cycle_config(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str,
) -> dict:
    db = get_supabase()
    cycle = db.table("performance_cycles").select("id,name,action_plan_start_date").eq("id", cycle_id).execute()
    if not cycle.data:
        raise HTTPException(404, detail="Ciclo não encontrado")
    base = cycle.data[0].get("action_plan_start_date")
    phase_due_dates = []
    if base:
        base_date = date.fromisoformat(base)
        phase_due_dates = [
            {"phase_number": n, "due_date": _add_months(base_date, 3 * n).isoformat()}
            for n in range(1, 5)
        ]
    return {"cycle_id": cycle_id, "action_plan_start_date": base, "phase_due_dates": phase_due_dates}


class CycleConfigBody(BaseModel):
    cycle_id: str
    action_plan_start_date: str  # ISO date (AAAA-MM-DD)


@router.put("/cycle-config")
def set_cycle_config(
    body: CycleConfigBody,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    try:
        parsed = date.fromisoformat(body.action_plan_start_date)
    except ValueError:
        raise HTTPException(400, detail="Data inválida. Use o formato AAAA-MM-DD.")
    db = get_supabase()
    cycle = db.table("performance_cycles").select("id").eq("id", body.cycle_id).execute()
    if not cycle.data:
        raise HTTPException(404, detail="Ciclo não encontrado")
    db.table("performance_cycles").update(
        {"action_plan_start_date": parsed.isoformat()}
    ).eq("id", body.cycle_id).execute()
    log_action("cycle", body.cycle_id, "set_action_plan_start_date", None,
               {"action_plan_start_date": parsed.isoformat()}, current_user["username"], request)
    return {"ok": True, "action_plan_start_date": parsed.isoformat()}


# ── Geração dos planos (disparo inicial manual) ────────────────────────────────

def _create_action_plan(db, cycle_id: str, cand: dict, phase_base_date: date, actor: str) -> dict | None:
    plan_res = db.table("performance_action_plans").insert({
        "cycle_id": cycle_id,
        "employee_id": cand["employee_id"],
        "review_id": cand["review_id"],
        "manager_id": cand["manager_id"],
        "phase_base_date": phase_base_date.isoformat(),
        "generated_by": actor,
    }).execute()
    if not plan_res.data:
        return None
    plan = plan_res.data[0]

    items_payload = [
        {
            "action_plan_id": plan["id"],
            "indicator_id": ind["indicator_id"],
            "original_score": ind["score"],
        }
        for ind in cand["indicators"]
    ]
    db.table("performance_action_plan_items").insert(items_payload).execute()

    phases_payload = [
        {
            "action_plan_id": plan["id"],
            "phase_number": n,
            "due_date": _add_months(phase_base_date, 3 * n).isoformat(),
        }
        for n in range(1, 5)
    ]
    db.table("performance_action_plan_phases").insert(phases_payload).execute()
    return plan


def _send_initial_emails_background(plans: list[dict], cycle_name: str, frontend_url: str, actor: str) -> None:
    from services.action_plan_email import send_action_plan_initial_email

    db = get_supabase()
    sent = 0
    for i, p in enumerate(plans):
        if i > 0:
            time.sleep(EMAIL_PACING_SECONDS)
        ok = send_action_plan_initial_email(
            manager_name=p["manager_name"], manager_email=p["manager_email"],
            employee_name=p["employee_name"], cycle_name=cycle_name,
            items=p["items"], token=p["token"], frontend_url=frontend_url,
            company_name=p.get("company_name", ""),
        )
        if ok:
            sent += 1
            db.table("performance_action_plans").update(
                {"initial_token_sent_at": "now()"}
            ).eq("id", p["plan_id"]).execute()
    log_action("action_plan", "batch", "send_initial_background", None,
               {"sent": sent, "total": len(plans)}, actor, None)


class GenerateBody(BaseModel):
    cycle_id: str
    employee_ids: list[str] | None = None


@router.post("/generate")
def generate_action_plans(
    body: GenerateBody,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    cycle = db.table("performance_cycles").select("id,name,action_plan_start_date").eq("id", body.cycle_id).execute()
    if not cycle.data:
        raise HTTPException(404, detail="Ciclo não encontrado")
    cycle_data = cycle.data[0]
    base = cycle_data.get("action_plan_start_date")
    if not base:
        raise HTTPException(400, detail="Defina a data-base de acompanhamento do ciclo antes de gerar planos (aba Config).")
    phase_base_date = date.fromisoformat(base)

    candidates = _build_candidates(db, body.cycle_id)
    if body.employee_ids:
        wanted = set(body.employee_ids)
        candidates = [c for c in candidates if c["employee_id"] in wanted]
    if not candidates:
        return {"created": 0, "skipped_no_manager_email": 0, "errors": []}

    companies = db.table("performance_companies").select("id,name").execute().data or []
    company_map = {c["id"]: c["name"] for c in companies}
    emp_rows = db.table("performance_employees").select("id,company_id").in_(
        "id", [c["employee_id"] for c in candidates]
    ).execute().data or []
    emp_company_map = {e["id"]: e.get("company_id") for e in emp_rows}

    created = 0
    skipped_no_manager_email = 0
    errors: list[str] = []
    to_email: list[dict] = []

    for cand in candidates:
        if not cand.get("manager_email") or not cand.get("manager_has_corporate_email"):
            skipped_no_manager_email += 1
            continue
        try:
            plan = _create_action_plan(db, body.cycle_id, cand, phase_base_date, current_user["username"])
        except Exception:
            _logger.exception("Falha ao criar plano de ação para employee_id=%s", cand["employee_id"])
            errors.append(cand["employee_id"])
            continue
        if not plan:
            errors.append(cand["employee_id"])
            continue
        created += 1
        to_email.append({
            "plan_id": plan["id"],
            "manager_name": cand["manager_name"],
            "manager_email": cand["manager_email"],
            "employee_name": cand["name"],
            "company_name": company_map.get(emp_company_map.get(cand["employee_id"]), ""),
            "items": [{"indicator_name": i["name"]} for i in cand["indicators"]],
            "token": str(plan["initial_token"]),
        })

    if to_email:
        background_tasks.add_task(
            _send_initial_emails_background, to_email, cycle_data["name"], _frontend_url(), current_user["username"],
        )

    log_action("cycle", body.cycle_id, "generate_action_plans", None,
               {"created": created, "skipped_no_manager_email": skipped_no_manager_email},
               current_user["username"], request)

    return {"created": created, "skipped_no_manager_email": skipped_no_manager_email, "errors": errors}


@router.post("/{action_plan_id}/resend-initial")
def resend_initial(
    action_plan_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    from services.action_plan_email import send_action_plan_initial_email

    db = get_supabase()
    plan = db.table("performance_action_plans").select("*").eq("id", action_plan_id).execute()
    if not plan.data:
        raise HTTPException(404, detail="Plano não encontrado")
    p = plan.data[0]
    if p.get("initial_token_used_at"):
        raise HTTPException(400, detail="O gestor já preencheu o plano inicial.")
    if p.get("initial_token_invalidated_at"):
        raise HTTPException(400, detail="Este plano foi invalidado.")

    emp_map = _resolve_employees(db, [p["employee_id"], p["manager_id"]])
    emp = emp_map.get(p["employee_id"])
    mgr = emp_map.get(p["manager_id"])
    if not emp:
        raise HTTPException(404, detail="Colaborador não encontrado")
    if not mgr or not mgr.get("has_corporate_email") or not mgr.get("email"):
        raise HTTPException(400, detail="Gestor não possui e-mail corporativo")

    items = db.table("performance_action_plan_items").select(
        "performance_indicators(name)"
    ).eq("action_plan_id", action_plan_id).execute().data or []
    item_names = [
        {"indicator_name": (i.get("performance_indicators") or {}).get("name", "")}
        for i in items
    ]

    company_name = ""
    if emp.get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", emp["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""

    cycle = db.table("performance_cycles").select("name").eq("id", p["cycle_id"]).execute()
    cycle_name = cycle.data[0]["name"] if cycle.data else ""

    ok = send_action_plan_initial_email(
        manager_name=mgr["name"], manager_email=mgr["email"],
        employee_name=emp["name"], cycle_name=cycle_name,
        items=item_names, token=str(p["initial_token"]), frontend_url=_frontend_url(),
        company_name=company_name,
    )
    if ok:
        db.table("performance_action_plans").update({"initial_token_sent_at": "now()"}).eq("id", action_plan_id).execute()
    log_action("action_plan", action_plan_id, "resend_initial", None, {"ok": ok}, current_user["username"], request)
    return {"ok": ok}


# ── Central de Alertas (candidatos + fases trimestrais pendentes de envio) ────

def _build_alerts(db, cycle_id: str | None) -> dict:
    candidates = _build_candidates(db, cycle_id) if cycle_id else []

    phases = (
        db.table("performance_action_plan_phases")
        .select("id,action_plan_id,phase_number,due_date,status,sent_at,reminder_count")
        .in_("status", ["pending_rh_send", "sent"])
        .execute()
        .data
    ) or []
    if not phases:
        return {"initial_candidates": candidates, "pending_phase_send": [], "suggested_reminders": []}

    plan_ids = list({p["action_plan_id"] for p in phases})
    plans = db.table("performance_action_plans").select(
        "id,employee_id,manager_id,cycle_id"
    ).in_("id", plan_ids).execute().data or []
    if cycle_id:
        plans = [p for p in plans if p["cycle_id"] == cycle_id]
    plans_map = {p["id"]: p for p in plans}

    emp_ids = [p["employee_id"] for p in plans_map.values()] + [p["manager_id"] for p in plans_map.values()]
    emp_map = _resolve_employees(db, emp_ids)

    pending_send = []
    reminders = []
    today = datetime.now(tz=timezone.utc).date()
    for ph in phases:
        plan = plans_map.get(ph["action_plan_id"])
        if not plan:
            continue
        emp = emp_map.get(plan["employee_id"], {})
        mgr = emp_map.get(plan["manager_id"], {})
        row = {
            "action_plan_id": plan["id"],
            "phase_id": ph["id"],
            "phase_number": ph["phase_number"],
            "due_date": ph["due_date"],
            "employee_name": emp.get("name", ""),
            "manager_name": mgr.get("name", ""),
        }
        if ph["status"] == "pending_rh_send":
            due = date.fromisoformat(ph["due_date"]) if isinstance(ph["due_date"], str) else ph["due_date"]
            row["days_overdue"] = (today - due).days
            pending_send.append(row)
        elif ph["status"] == "sent" and ph.get("sent_at"):
            sent_at = datetime.fromisoformat(ph["sent_at"].replace("Z", "+00:00"))
            days_waiting = (datetime.now(tz=timezone.utc) - sent_at).days
            if days_waiting >= REMINDER_AFTER_DAYS:
                row["days_waiting"] = days_waiting
                row["reminder_count"] = ph.get("reminder_count", 0)
                reminders.append(row)

    return {
        "initial_candidates": candidates,
        "pending_phase_send": sorted(pending_send, key=lambda r: -r["days_overdue"]),
        "suggested_reminders": sorted(reminders, key=lambda r: -r["days_waiting"]),
    }


@router.get("/alerts")
def get_alerts(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str | None = None,
) -> dict:
    return _build_alerts(get_supabase(), cycle_id)


@router.get("/notifications-summary")
def notifications_summary(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str | None = None,
) -> dict:
    db = get_supabase()
    candidates = _build_candidates(db, cycle_id) if cycle_id else []
    pending_phases = (
        db.table("performance_action_plan_phases").select("id").eq("status", "pending_rh_send").execute().data
    ) or []
    return {
        "pending_initial_candidates": len(candidates),
        "pending_phase_alerts": len(pending_phases),
        "total": len(candidates) + len(pending_phases),
    }


# ── Disparo trimestral manual ──────────────────────────────────────────────────

def _send_one_phase(db, action_plan_id: str, phase_number: int, frontend_url: str) -> bool:
    from services.action_plan_email import send_action_plan_checkin_email

    phase = (
        db.table("performance_action_plan_phases").select("*")
        .eq("action_plan_id", action_plan_id).eq("phase_number", phase_number).execute()
    )
    if not phase.data:
        raise HTTPException(404, detail="Fase não encontrada")
    ph = phase.data[0]
    if ph["status"] not in ("scheduled", "pending_rh_send"):
        raise HTTPException(400, detail="Esta fase já foi enviada ou concluída.")

    plan = db.table("performance_action_plans").select("*").eq("id", action_plan_id).execute()
    if not plan.data:
        raise HTTPException(404, detail="Plano não encontrado")
    p = plan.data[0]
    if p["status"] != "active":
        raise HTTPException(400, detail="O gestor ainda não preencheu o plano inicial.")

    items = (
        db.table("performance_action_plan_items")
        .select("id,plan_text,cumulative_pct,performance_indicators(name)")
        .eq("action_plan_id", action_plan_id).execute().data
    ) or []

    existing_pi = (
        db.table("performance_action_plan_phase_items").select("action_plan_item_id")
        .eq("phase_id", ph["id"]).execute().data
    ) or []
    existing_ids = {r["action_plan_item_id"] for r in existing_pi}
    to_create = [
        {"phase_id": ph["id"], "action_plan_item_id": it["id"]}
        for it in items if it["id"] not in existing_ids
    ]
    if to_create:
        db.table("performance_action_plan_phase_items").insert(to_create).execute()

    emp_map = _resolve_employees(db, [p["employee_id"], p["manager_id"]])
    employee_name = emp_map.get(p["employee_id"], {}).get("name", "")
    mgr = emp_map.get(p["manager_id"])
    if not mgr or not mgr.get("has_corporate_email") or not mgr.get("email"):
        raise HTTPException(400, detail="Gestor não possui e-mail corporativo")

    cycle = db.table("performance_cycles").select("name").eq("id", p["cycle_id"]).execute()
    cycle_name = cycle.data[0]["name"] if cycle.data else ""

    email_items = [
        {
            "indicator_name": (it.get("performance_indicators") or {}).get("name", ""),
            "plan_text": it.get("plan_text") or "",
            "cumulative_pct_before": it.get("cumulative_pct", 0),
        }
        for it in items
    ]

    ok = send_action_plan_checkin_email(
        manager_name=mgr["name"], manager_email=mgr["email"],
        employee_name=employee_name, cycle_name=cycle_name,
        phase_number=phase_number, is_final_phase=(phase_number == 4),
        items=email_items, token=str(ph["token"]), frontend_url=frontend_url,
    )
    if ok:
        db.table("performance_action_plan_phases").update(
            {"status": "sent", "sent_at": "now()"}
        ).eq("id", ph["id"]).execute()
        db.table("performance_action_plans").update(
            {"current_phase": phase_number}
        ).eq("id", action_plan_id).execute()
    return ok


@router.post("/{action_plan_id}/phases/{phase_number}/send")
def send_phase(
    action_plan_id: str,
    phase_number: int,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    ok = _send_one_phase(get_supabase(), action_plan_id, phase_number, _frontend_url())
    log_action("action_plan_phase", f"{action_plan_id}:{phase_number}", "send", None,
               {"ok": ok}, current_user["username"], request)
    return {"ok": ok}


class SendBatchBody(BaseModel):
    phase_ids: list[str]


@router.post("/phases/send-batch")
def send_phases_batch(
    body: SendBatchBody,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    if not body.phase_ids:
        raise HTTPException(400, detail="Nenhuma fase selecionada.")
    db = get_supabase()
    phases = (
        db.table("performance_action_plan_phases").select("id,action_plan_id,phase_number")
        .in_("id", body.phase_ids).execute().data
    ) or []
    if not phases:
        raise HTTPException(404, detail="Fases não encontradas.")

    frontend_url = _frontend_url()
    actor = current_user["username"]

    def _run() -> None:
        db2 = get_supabase()
        sent = 0
        for i, ph in enumerate(phases):
            if i > 0:
                time.sleep(EMAIL_PACING_SECONDS)
            try:
                if _send_one_phase(db2, ph["action_plan_id"], ph["phase_number"], frontend_url):
                    sent += 1
            except HTTPException:
                continue
        log_action("action_plan_phase", "batch", "send_batch_background", None,
                   {"sent": sent, "total": len(phases)}, actor, None)

    background_tasks.add_task(_run)
    return {"queued": len(phases)}


@router.post("/{action_plan_id}/phases/{phase_number}/resend")
def resend_phase(
    action_plan_id: str,
    phase_number: int,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    from services.action_plan_email import send_action_plan_checkin_reminder_email

    db = get_supabase()
    phase = (
        db.table("performance_action_plan_phases").select("*")
        .eq("action_plan_id", action_plan_id).eq("phase_number", phase_number).execute()
    )
    if not phase.data:
        raise HTTPException(404, detail="Fase não encontrada")
    ph = phase.data[0]
    if ph["status"] != "sent":
        raise HTTPException(400, detail="Só é possível reenviar lembrete de uma fase já enviada e sem resposta.")

    plan = db.table("performance_action_plans").select("*").eq("id", action_plan_id).execute()
    if not plan.data:
        raise HTTPException(404, detail="Plano não encontrado")
    p = plan.data[0]

    items = (
        db.table("performance_action_plan_items")
        .select("plan_text,cumulative_pct,performance_indicators(name)")
        .eq("action_plan_id", action_plan_id).execute().data
    ) or []
    emp_map = _resolve_employees(db, [p["employee_id"], p["manager_id"]])
    employee_name = emp_map.get(p["employee_id"], {}).get("name", "")
    mgr = emp_map.get(p["manager_id"])
    if not mgr or not mgr.get("email"):
        raise HTTPException(400, detail="Gestor não possui e-mail corporativo")

    cycle = db.table("performance_cycles").select("name").eq("id", p["cycle_id"]).execute()
    cycle_name = cycle.data[0]["name"] if cycle.data else ""

    email_items = [
        {
            "indicator_name": (it.get("performance_indicators") or {}).get("name", ""),
            "plan_text": it.get("plan_text") or "",
            "cumulative_pct_before": it.get("cumulative_pct", 0),
        }
        for it in items
    ]

    ok = send_action_plan_checkin_reminder_email(
        manager_name=mgr["name"], manager_email=mgr["email"],
        employee_name=employee_name, cycle_name=cycle_name,
        phase_number=phase_number, is_final_phase=(phase_number == 4),
        items=email_items, token=str(ph["token"]), frontend_url=_frontend_url(),
    )
    if ok:
        db.table("performance_action_plan_phases").update({
            "reminder_count": (ph.get("reminder_count") or 0) + 1,
            "last_reminder_at": "now()",
        }).eq("id", ph["id"]).execute()
    log_action("action_plan_phase", f"{action_plan_id}:{phase_number}", "resend_reminder", None,
               {"ok": ok}, current_user["username"], request)
    return {"ok": ok}


# ── Monitoramento / relatórios (RH) ────────────────────────────────────────────

def _build_overview(db, filters: dict) -> list[dict]:
    q = db.table("performance_action_plans").select("*")
    if filters.get("cycle_id"):
        q = q.eq("cycle_id", filters["cycle_id"])
    if filters.get("manager_id"):
        q = q.eq("manager_id", filters["manager_id"])
    if filters.get("status"):
        q = q.eq("status", filters["status"])
    plans = q.execute().data or []
    if not plans:
        return []

    emp_ids = [p["employee_id"] for p in plans] + [p["manager_id"] for p in plans]
    emp_map = _resolve_employees(db, emp_ids)

    if filters.get("employee_search"):
        needle = filters["employee_search"].strip().lower()
        plans = [p for p in plans if needle in emp_map.get(p["employee_id"], {}).get("name", "").lower()]

    if filters.get("company_id") or filters.get("branch_id"):
        def _loc_match(p: dict) -> bool:
            emp = emp_map.get(p["employee_id"], {})
            if filters.get("company_id") and emp.get("company_id") != filters["company_id"]:
                return False
            if filters.get("branch_id") and emp.get("branch_id") != filters["branch_id"]:
                return False
            return True
        plans = [p for p in plans if _loc_match(p)]

    plan_ids = [p["id"] for p in plans]
    if not plan_ids:
        return []

    items = (
        db.table("performance_action_plan_items")
        .select("id,action_plan_id,indicator_id,plan_text,cumulative_pct,performance_indicators(name)")
        .in_("action_plan_id", plan_ids).execute().data
    ) or []
    items_by_plan: dict[str, list[dict]] = {}
    for it in items:
        items_by_plan.setdefault(it["action_plan_id"], []).append(it)

    if filters.get("indicator_id"):
        wanted_plan_ids = {it["action_plan_id"] for it in items if it["indicator_id"] == filters["indicator_id"]}
        plans = [p for p in plans if p["id"] in wanted_plan_ids]

    phases = (
        db.table("performance_action_plan_phases")
        .select("id,action_plan_id,phase_number,due_date,status,sent_at,completed_at")
        .in_("action_plan_id", plan_ids).execute().data
    ) or []
    phases_by_plan: dict[str, list[dict]] = {}
    for ph in phases:
        phases_by_plan.setdefault(ph["action_plan_id"], []).append(ph)

    if filters.get("phase_number") or filters.get("phase_status"):
        def _phase_match(p: dict) -> bool:
            for ph in phases_by_plan.get(p["id"], []):
                if filters.get("phase_number") and ph["phase_number"] != filters["phase_number"]:
                    continue
                if filters.get("phase_status") and ph["status"] != filters["phase_status"]:
                    continue
                return True
            return False
        plans = [p for p in plans if _phase_match(p)]

    result = []
    for p in plans:
        plan_items = items_by_plan.get(p["id"], [])
        avg_pct = round(sum(i.get("cumulative_pct", 0) for i in plan_items) / len(plan_items), 1) if plan_items else 0.0
        if filters.get("min_progress") is not None and avg_pct < filters["min_progress"]:
            continue
        if filters.get("max_progress") is not None and avg_pct > filters["max_progress"]:
            continue
        emp = emp_map.get(p["employee_id"], {})
        mgr = emp_map.get(p["manager_id"], {})
        result.append({
            "action_plan_id": p["id"],
            "employee_id": p["employee_id"],
            "employee_name": emp.get("name", ""),
            "manager_id": p["manager_id"],
            "manager_name": mgr.get("name", ""),
            "status": p["status"],
            "current_phase": p.get("current_phase", 0),
            "progress_pct": avg_pct,
            "indicators": [
                {
                    "indicator_id": i["indicator_id"],
                    "name": (i.get("performance_indicators") or {}).get("name", ""),
                    "cumulative_pct": i.get("cumulative_pct", 0),
                }
                for i in plan_items
            ],
            "phases": [
                {"phase_number": ph["phase_number"], "due_date": ph["due_date"], "status": ph["status"]}
                for ph in sorted(phases_by_plan.get(p["id"], []), key=lambda x: x["phase_number"])
            ],
        })
    return sorted(result, key=lambda r: r["employee_name"])


@router.get("/overview")
def get_overview(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str | None = None,
    manager_id: str | None = None,
    employee_search: str | None = None,
    indicator_id: str | None = None,
    status: str | None = None,
    phase_number: int | None = None,
    phase_status: str | None = None,
    company_id: str | None = None,
    branch_id: str | None = None,
    min_progress: float | None = None,
    max_progress: float | None = None,
) -> list[dict]:
    filters = {
        "cycle_id": cycle_id, "manager_id": manager_id, "employee_search": employee_search,
        "indicator_id": indicator_id, "status": status, "phase_number": phase_number,
        "phase_status": phase_status, "company_id": company_id, "branch_id": branch_id,
        "min_progress": min_progress, "max_progress": max_progress,
    }
    return _build_overview(get_supabase(), filters)


@router.get("/overview/export")
def export_overview(
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
    cycle_id: str | None = None,
    manager_id: str | None = None,
    employee_search: str | None = None,
    indicator_id: str | None = None,
    status: str | None = None,
    phase_number: int | None = None,
    phase_status: str | None = None,
    company_id: str | None = None,
    branch_id: str | None = None,
    min_progress: float | None = None,
    max_progress: float | None = None,
):
    filters = {
        "cycle_id": cycle_id, "manager_id": manager_id, "employee_search": employee_search,
        "indicator_id": indicator_id, "status": status, "phase_number": phase_number,
        "phase_status": phase_status, "company_id": company_id, "branch_id": branch_id,
        "min_progress": min_progress, "max_progress": max_progress,
    }
    rows = _build_overview(get_supabase(), filters)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Colaborador", "Gestor", "Status", "Fase Atual", "% Progresso"])
    for r in rows:
        w.writerow([r["employee_name"], r["manager_name"], r["status"], r["current_phase"], r["progress_pct"]])
    out.seek(0)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plano_acao_feedback.csv"},
    )


@router.get("/{action_plan_id}/detail")
def get_plan_detail(
    action_plan_id: str,
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    db = get_supabase()
    plan = db.table("performance_action_plans").select("*").eq("id", action_plan_id).execute()
    if not plan.data:
        raise HTTPException(404, detail="Plano não encontrado")
    p = plan.data[0]
    emp_map = _resolve_employees(db, [p["employee_id"], p["manager_id"]])

    items = (
        db.table("performance_action_plan_items")
        .select("id,indicator_id,original_score,plan_text,cumulative_pct,performance_indicators(name)")
        .eq("action_plan_id", action_plan_id).execute().data
    ) or []
    item_name = {i["id"]: (i.get("performance_indicators") or {}).get("name", "") for i in items}

    phases = (
        db.table("performance_action_plan_phases").select("*")
        .eq("action_plan_id", action_plan_id).order("phase_number").execute().data
    ) or []
    phase_ids = [ph["id"] for ph in phases]
    phase_items = (
        db.table("performance_action_plan_phase_items").select("*").in_("phase_id", phase_ids).execute().data
        if phase_ids else []
    ) or []
    phase_items_by_phase: dict[str, list[dict]] = {}
    for pi in phase_items:
        phase_items_by_phase.setdefault(pi["phase_id"], []).append(pi)

    return {
        "action_plan_id": p["id"],
        "status": p["status"],
        "employee_name": emp_map.get(p["employee_id"], {}).get("name", ""),
        "manager_name": emp_map.get(p["manager_id"], {}).get("name", ""),
        "current_phase": p.get("current_phase", 0),
        "items": [
            {
                "indicator_id": i["indicator_id"],
                "indicator_name": (i.get("performance_indicators") or {}).get("name", ""),
                "original_score": i["original_score"],
                "plan_text": i.get("plan_text"),
                "cumulative_pct": i.get("cumulative_pct", 0),
            }
            for i in items
        ],
        "phases": [
            {
                "phase_number": ph["phase_number"], "due_date": ph["due_date"], "status": ph["status"],
                "sent_at": ph.get("sent_at"), "completed_at": ph.get("completed_at"),
                "answers": [
                    {
                        "indicator_name": item_name.get(pi["action_plan_item_id"], ""),
                        "result": pi.get("result"),
                        "pct_awarded": pi.get("pct_awarded"),
                        "justification": pi.get("justification"),
                        "phase4_override_100": pi.get("phase4_override_100"),
                        "phase4_final_justification": pi.get("phase4_final_justification"),
                    }
                    for pi in phase_items_by_phase.get(ph["id"], [])
                ],
            }
            for ph in phases
        ],
    }

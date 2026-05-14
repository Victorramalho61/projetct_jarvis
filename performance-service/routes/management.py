import csv
import io
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import require_role
from db import get_supabase, get_settings
from services.audit import log_action

router = APIRouter(prefix="/api/performance/management")
_logger = logging.getLogger(__name__)

_CYCLE_MGMT = ("admin", "rh", "gestor_ciclo")
_RH_ADMIN = ("admin", "rh")

_PHASE_LABELS = {
    "goal_signing": "Assinatura de Metas",
    "self_assessment": "Autoavaliação",
    "manager_review": "Avaliação do Gestor",
    "acknowledgment": "Ciência do Resultado",
}

_PHASE_TO_STATUS = {
    "goal_signing": "draft",
    "self_assessment": "pending_self",
    "manager_review": "pending_manager",
    "acknowledgment": "pending_ack",
}

_DEFAULT_MAX_DAYS = {
    "goal_signing": 5,
    "self_assessment": 10,
    "manager_review": 7,
    "acknowledgment": 5,
}

_ADVANCE = {
    "pending_self": "pending_manager",
    "pending_manager": "pending_ack",
    "disputed": "pending_ack",
}

_REVERT = {
    "pending_manager": "pending_self",
    "pending_ack": "pending_manager",
    "completed": "pending_ack",
}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _summary(reviews: list[dict]) -> dict:
    total = len(reviews)
    by_status: dict[str, int] = {}
    for r in reviews:
        s = r.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    completed = by_status.get("completed", 0)
    return {
        "total": total,
        "by_status": by_status,
        "completion_rate": round(completed / total * 100, 1) if total else 0.0,
    }


def _build_overview(cycle_id: str) -> dict:
    db = get_supabase()
    reviews = db.table("performance_reviews").select("*").eq("cycle_id", cycle_id).execute().data
    employees = db.table("performance_employees").select("*").execute().data
    departments = db.table("performance_departments").select("*").execute().data

    emp_map = {e["id"]: e for e in employees}
    dept_map = {d["id"]: d for d in departments}

    by_company: dict[str, list] = {}
    by_branch: dict[str, list] = {}
    by_manager: dict[str, list] = {}
    company_names: dict[str, str] = {}
    branch_names: dict[str, str] = {}
    manager_names: dict[str, str] = {}

    for r in reviews:
        emp = emp_map.get(r.get("employee_id", ""))
        if not emp:
            continue

        dept = dept_map.get(emp.get("department_id", "")) if emp.get("department_id") else None

        company_id = str(dept.get("company_id", "sem-empresa")) if dept and dept.get("company_id") else "sem-empresa"
        company_names.setdefault(company_id, company_id)
        by_company.setdefault(company_id, []).append(r)

        branch_id, branch_name = "sem-filial", "Sem Filial"
        if dept:
            if dept.get("parent_id") is None:
                branch_id = dept["id"]
                branch_name = dept.get("name", branch_id)
            else:
                parent = dept_map.get(dept.get("parent_id", ""))
                if parent:
                    branch_id = parent["id"]
                    branch_name = parent.get("name", branch_id)
        branch_names[branch_id] = branch_name
        by_branch.setdefault(branch_id, []).append(r)

        manager_id = emp.get("manager_id") or "sem-gestor"
        if manager_id != "sem-gestor":
            mgr = emp_map.get(manager_id)
            manager_names[manager_id] = mgr.get("name", manager_id) if mgr else manager_id
        else:
            manager_names[manager_id] = "Sem Gestor"
        by_manager.setdefault(manager_id, []).append(r)

    def build(groups: dict, names: dict) -> list[dict]:
        result = []
        for gid, group_reviews in groups.items():
            row = _summary(group_reviews)
            row["id"] = gid
            row["name"] = names.get(gid, gid)
            result.append(row)
        return sorted(result, key=lambda x: x["total"], reverse=True)

    return {
        "cycle_id": cycle_id,
        "total_reviews": len(reviews),
        "by_company": build(by_company, company_names),
        "by_branch": build(by_branch, branch_names),
        "by_manager": build(by_manager, manager_names),
    }


def _build_sla(cycle_id: str) -> dict:
    db = get_supabase()
    configs = db.table("performance_sla_configs").select("*").eq("cycle_id", cycle_id).execute().data
    config_map = {c["phase"]: c["max_days"] for c in configs}
    now = _now()
    violations: list[dict] = []

    for phase, status in _PHASE_TO_STATUS.items():
        max_days = config_map.get(phase, _DEFAULT_MAX_DAYS[phase])
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
            ref_dt = item.get("updated_at") or item.get("created_at")
            if not ref_dt:
                continue
            if isinstance(ref_dt, str):
                ref_dt = datetime.fromisoformat(ref_dt.replace("Z", "+00:00"))
            days_elapsed = (now - ref_dt).days
            if days_elapsed > max_days:
                violations.append({
                    "phase": phase,
                    "phase_label": _PHASE_LABELS[phase],
                    "item_id": item["id"],
                    "days_overdue": days_elapsed - max_days,
                    "max_days": max_days,
                    "employee_id": item.get("employee_id") or item.get("owner_id"),
                })

    total_reviews = len(
        db.table("performance_reviews").select("id").eq("cycle_id", cycle_id).execute().data
    )
    compliance_pct = round((1 - len(violations) / max(total_reviews, 1)) * 100, 1)

    return {
        "cycle_id": cycle_id,
        "configs": configs,
        "violations": violations,
        "total_violations": len(violations),
        "compliance_pct": compliance_pct,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────────

@router.get("/overview")
def get_overview(
    cycle_id: str,
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))],
) -> dict:
    return _build_overview(cycle_id)


@router.get("/sla")
def get_sla(
    cycle_id: str,
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))],
) -> dict:
    return _build_sla(cycle_id)


@router.get("/sla-configs")
def list_sla_configs(
    cycle_id: str,
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))],
) -> list[dict]:
    db = get_supabase()
    return db.table("performance_sla_configs").select("*").eq("cycle_id", cycle_id).execute().data


class SlaConfigUpsert(BaseModel):
    cycle_id: str
    phase: str
    max_days: int


@router.post("/sla-configs")
def upsert_sla_config(
    body: SlaConfigUpsert,
    current_user: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    if body.phase not in _PHASE_LABELS:
        raise HTTPException(400, detail=f"phase inválida. Aceitas: {list(_PHASE_LABELS.keys())}")
    if body.max_days < 1:
        raise HTTPException(400, detail="max_days deve ser >= 1")

    db = get_supabase()
    existing = (
        db.table("performance_sla_configs")
        .select("id")
        .eq("cycle_id", body.cycle_id)
        .eq("phase", body.phase)
        .execute()
        .data
    )
    if existing:
        result = (
            db.table("performance_sla_configs")
            .update({"max_days": body.max_days})
            .eq("id", existing[0]["id"])
            .execute()
        )
    else:
        result = db.table("performance_sla_configs").insert({
            "cycle_id": body.cycle_id,
            "phase": body.phase,
            "max_days": body.max_days,
            "created_by": current_user["username"],
        }).execute()
    return result.data[0] if result.data else {}


class NotifyPendingRequest(BaseModel):
    cycle_id: str
    phase: str
    dimension_type: str | None = None
    dimension_id: str | None = None
    dry_run: bool = False


@router.post("/notify-pending")
def notify_pending(
    body: NotifyPendingRequest,
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))],
) -> dict:
    from services.email import send_email

    if body.phase not in _PHASE_TO_STATUS:
        raise HTTPException(400, detail=f"phase inválida. Aceitas: {list(_PHASE_TO_STATUS.keys())}")

    db = get_supabase()
    s = get_settings()
    status = _PHASE_TO_STATUS[body.phase]
    phase_label = _PHASE_LABELS[body.phase]

    cycle = db.table("performance_cycles").select("name").eq("id", body.cycle_id).execute().data
    cycle_name = cycle[0]["name"] if cycle else body.cycle_id

    if status == "draft":
        pending_items = db.table("performance_goals").select("*").eq("status", "draft").execute().data
    else:
        pending_items = (
            db.table("performance_reviews")
            .select("*")
            .eq("cycle_id", body.cycle_id)
            .eq("status", status)
            .execute()
            .data
        )

    employees = db.table("performance_employees").select("*").execute().data
    emp_map = {e["id"]: e for e in employees}

    frontend_url = s.allowed_origins.split(",")[0].strip().rstrip("/")
    today_str = _now().date().isoformat()
    sent, skipped = 0, 0
    dry_run_list: list[dict] = []

    for item in pending_items:
        emp_id = item.get("employee_id") or item.get("owner_id")
        if not emp_id:
            skipped += 1
            continue
        emp = emp_map.get(emp_id)
        if not emp or not emp.get("email"):
            skipped += 1
            continue

        already = (
            db.table("performance_sla_reminder_log")
            .select("id")
            .eq("cycle_id", body.cycle_id)
            .eq("employee_id", emp_id)
            .eq("phase", body.phase)
            .gte("sent_at", f"{today_str}T00:00:00+00:00")
            .execute()
            .data
        )
        if already:
            skipped += 1
            continue

        if body.dry_run:
            dry_run_list.append({
                "employee_id": emp_id,
                "name": emp.get("name"),
                "email": emp.get("email"),
            })
        else:
            html = (
                f"<p>Olá, {emp.get('name', 'Colaborador')}!</p>"
                f"<p>Você possui uma pendência em aberto no ciclo <strong>{cycle_name}</strong>:</p>"
                f"<p><strong>Fase:</strong> {phase_label}</p>"
                f"<p><a href='{frontend_url}/desempenho'>Acessar Gestão de Desempenho</a></p>"
            )
            ok = send_email(
                to_email=emp["email"],
                display_name=emp.get("name", ""),
                subject=f"Pendência em aberto — {phase_label} | {cycle_name}",
                html=html,
            )
            if ok:
                db.table("performance_sla_reminder_log").insert({
                    "cycle_id": body.cycle_id,
                    "employee_id": emp_id,
                    "phase": body.phase,
                    "sent_by": current_user["username"],
                }).execute()
                sent += 1
            else:
                skipped += 1

    result: dict = {"sent": sent, "skipped": skipped, "dry_run": body.dry_run}
    if body.dry_run:
        result["dry_run_list"] = dry_run_list
    return result


@router.get("/notify-history")
def notify_history(
    cycle_id: str,
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))],
) -> list[dict]:
    db = get_supabase()
    return (
        db.table("performance_sla_reminder_log")
        .select("*")
        .eq("cycle_id", cycle_id)
        .order("sent_at", desc=True)
        .limit(50)
        .execute()
        .data
    )


@router.get("/reports/completion")
def report_completion(
    cycle_id: str,
    dimension: str = "company",
    format: str = "json",
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))] = None,
):
    overview = _build_overview(cycle_id)
    dim_map = {
        "company": overview["by_company"],
        "branch": overview["by_branch"],
        "manager": overview["by_manager"],
    }
    rows = dim_map.get(dimension, overview["by_company"])

    if format == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Dimensão", "ID", "Total", "Concluída", "Autoaval.", "Ag.Gestor", "Ag.Ciência", "%Completude"])
        for row in rows:
            bs = row.get("by_status", {})
            w.writerow([
                row.get("name", row.get("id")), row.get("id"), row.get("total"),
                bs.get("completed", 0), bs.get("pending_self", 0),
                bs.get("pending_manager", 0), bs.get("pending_ack", 0),
                row.get("completion_rate"),
            ])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=completude_{cycle_id[:8]}_{dimension}.csv"},
        )
    return rows


@router.get("/reports/sla")
def report_sla(
    cycle_id: str,
    format: str = "json",
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))] = None,
):
    data = _build_sla(cycle_id)
    if format == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Fase", "Item ID", "Colaborador ID", "Dias em Atraso", "Prazo (dias)"])
        for v in data["violations"]:
            w.writerow([v["phase_label"], v["item_id"], v.get("employee_id"), v["days_overdue"], v["max_days"]])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=sla_{cycle_id[:8]}.csv"},
        )
    return data


@router.get("/reports/scores")
def report_scores(
    cycle_id: str,
    format: str = "json",
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))] = None,
):
    db = get_supabase()
    reviews = (
        db.table("performance_reviews")
        .select("*")
        .eq("cycle_id", cycle_id)
        .eq("status", "completed")
        .execute()
        .data
    )
    rows = [
        {
            "review_id": r["id"],
            "employee_id": r.get("employee_id"),
            "final_score": r.get("final_score"),
            "goals_score": r.get("goals_score"),
            "competencies_score": r.get("competencies_score"),
            "behavior_score": r.get("behavior_score"),
            "compliance_score": r.get("compliance_score"),
        }
        for r in reviews
    ]

    if format == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Review ID", "Colaborador ID", "Score Final", "Metas", "Competências", "Comportamento", "Compliance"])
        for row in rows:
            w.writerow([row["review_id"], row["employee_id"], row["final_score"],
                        row["goals_score"], row["competencies_score"],
                        row["behavior_score"], row["compliance_score"]])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=scores_{cycle_id[:8]}.csv"},
        )
    return rows


class TransitionBody(BaseModel):
    reason: str


@router.patch("/reviews/{review_id}/advance")
def advance_review(
    review_id: str,
    body: TransitionBody,
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))],
) -> dict:
    if not body.reason.strip():
        raise HTTPException(400, detail="reason é obrigatório")
    db = get_supabase()
    review = db.table("performance_reviews").select("*").eq("id", review_id).execute().data
    if not review:
        raise HTTPException(404, detail="Review não encontrada")
    current_status = review[0]["status"]
    next_status = _ADVANCE.get(current_status)
    if not next_status:
        raise HTTPException(400, detail=f"Status '{current_status}' não pode ser avançado")
    result = db.table("performance_reviews").update({"status": next_status}).eq("id", review_id).execute()
    log_action("review", review_id, "advance", {"status": current_status}, {"status": next_status},
               current_user["username"])
    return result.data[0] if result.data else {}


@router.patch("/reviews/{review_id}/revert")
def revert_review(
    review_id: str,
    body: TransitionBody,
    current_user: Annotated[dict, Depends(require_role(*_CYCLE_MGMT))],
) -> dict:
    if not body.reason.strip():
        raise HTTPException(400, detail="reason é obrigatório")
    db = get_supabase()
    review = db.table("performance_reviews").select("*").eq("id", review_id).execute().data
    if not review:
        raise HTTPException(404, detail="Review não encontrada")
    current_status = review[0]["status"]
    prev_status = _REVERT.get(current_status)
    if not prev_status:
        raise HTTPException(400, detail=f"Status '{current_status}' não pode ser revertido")
    if current_status == "completed" and current_user.get("role") not in _RH_ADMIN:
        raise HTTPException(403, detail="Apenas rh/admin podem reverter reviews concluídas")
    result = db.table("performance_reviews").update({"status": prev_status}).eq("id", review_id).execute()
    log_action("review", review_id, "revert", {"status": current_status}, {"status": prev_status},
               current_user["username"])
    return result.data[0] if result.data else {}

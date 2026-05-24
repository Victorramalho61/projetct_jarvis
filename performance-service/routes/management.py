import csv
import io
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/performance/management")
_logger = logging.getLogger(__name__)

_RH_ADMIN = ("admin", "rh")


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
    branches = db.table("performance_branches").select("*").execute().data
    companies = db.table("performance_companies").select("*").execute().data

    emp_map = {e["id"]: e for e in employees}
    branch_map = {b["id"]: b for b in branches}
    company_map = {c["id"]: c for c in companies}

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

        company_id = emp.get("company_id") or "sem-empresa"
        company = company_map.get(company_id)
        company_names[company_id] = company["name"] if company else company_id
        by_company.setdefault(company_id, []).append(r)

        branch_id = emp.get("branch_id") or "sem-filial"
        branch = branch_map.get(branch_id)
        branch_names[branch_id] = branch["name"] if branch else "Sem Filial"
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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/overview")
def get_overview(
    cycle_id: str,
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))],
) -> dict:
    return _build_overview(cycle_id)


@router.get("/reports/completion")
def report_completion(
    cycle_id: str,
    dimension: str = "company",
    format: str = "json",
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))] = None,
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
        w.writerow(["Dimensão", "ID", "Total", "Concluída", "%Completude"])
        for row in rows:
            bs = row.get("by_status", {})
            w.writerow([
                row.get("name", row.get("id")), row.get("id"), row.get("total"),
                bs.get("completed", 0),
                row.get("completion_rate"),
            ])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=completude_{cycle_id[:8]}_{dimension}.csv"},
        )
    return rows


@router.get("/reports/scores")
def report_scores(
    cycle_id: str,
    format: str = "json",
    _: Annotated[dict, Depends(require_role(*_RH_ADMIN))] = None,
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
            "evaluator_id": r.get("evaluator_id"),
            "final_score": r.get("final_score"),
            "submitted_at": r.get("submitted_at"),
        }
        for r in reviews
    ]

    if format == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Review ID", "Colaborador ID", "Avaliador ID", "Score Final", "Data Submissão"])
        for row in rows:
            w.writerow([row["review_id"], row["employee_id"], row["evaluator_id"],
                        row["final_score"], row["submitted_at"]])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=scores_{cycle_id[:8]}.csv"},
        )
    return rows

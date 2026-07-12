import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import require_role
from db import get_supabase, get_settings

router = APIRouter(prefix="/api/performance/my")
_logger = logging.getLogger(__name__)

_MANAGER_ROLES = ("admin", "rh", "gerente", "coordenador_supervisor")


def _get_open_cycle(db) -> dict | None:
    res = db.table("performance_cycles").select("*").eq("status", "open").limit(1).execute()
    return res.data[0] if res.data else None


@router.get("/subordinates")
def list_my_subordinates(
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> list[dict]:
    db = get_supabase()
    username = current_user.get("username")

    emp = db.table("performance_employees").select("id").eq("jarvis_username", username).eq("active", True).execute()
    if not emp.data:
        return []
    manager_id = emp.data[0]["id"]

    subordinates = (
        db.table("performance_employees")
        .select("id,name,cargo,email,has_corporate_email,hierarchy_level,perfil")
        .eq("manager_id", manager_id)
        .eq("active", True)
        .order("name")
        .execute()
        .data
    )
    if not subordinates:
        return []

    cycle = _get_open_cycle(db)
    reviews_by_emp: dict[str, dict] = {}
    token_by_emp: dict[str, str] = {}
    if cycle:
        sub_ids = [s["id"] for s in subordinates]
        reviews = (
            db.table("performance_reviews")
            .select("id,employee_id,status")
            .eq("cycle_id", cycle["id"])
            .in_("employee_id", sub_ids)
            .execute()
            .data
        )
        acked_ids: set[str] = set()
        if reviews:
            rev_ids = [r["id"] for r in reviews]
            acks = db.table("performance_review_acknowledgments").select("review_id").in_("review_id", rev_ids).execute().data
            acked_ids = {a["review_id"] for a in acks}
        for r in reviews:
            rid = r["id"]
            st = "acknowledged" if rid in acked_ids else r.get("status", "pending")
            reviews_by_emp[r["employee_id"]] = {"review_id": rid, "status": st}

        # Buscar tokens de avaliação pendentes para o gestor logado
        tok_rows = (
            db.table("performance_evaluation_tokens")
            .select("employee_id,token")
            .eq("cycle_id", cycle["id"])
            .eq("evaluator_id", manager_id)
            .eq("is_used", False)
            .is_("invalidated_at", "null")
            .execute()
            .data
        ) or []
        token_by_emp = {t["employee_id"]: t["token"] for t in tok_rows}

    result = []
    for sub in subordinates:
        rev_info = reviews_by_emp.get(sub["id"], {})
        result.append({
            "employee_id": sub["id"],
            "name": sub["name"],
            "cargo": sub.get("cargo", ""),
            "email": sub.get("email"),
            "has_corporate_email": sub.get("has_corporate_email", False),
            "cycle_status": rev_info.get("status", "pending"),
            "review_id": rev_info.get("review_id"),
            "evaluation_token": token_by_emp.get(sub["id"]),
        })
    return result


@router.post("/subordinates/{employee_id}/resend-ciencia")
def resend_ciencia(
    employee_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(require_role(*_MANAGER_ROLES))],
) -> dict:
    from services.email import send_ciencia_email

    db = get_supabase()
    s = get_settings()
    frontend_url = s.allowed_origins.split(",")[0].strip().rstrip("/")

    username = current_user.get("username")
    mgr_emp = db.table("performance_employees").select("id").eq("jarvis_username", username).eq("active", True).execute()
    if not mgr_emp.data:
        raise HTTPException(403, detail="Gestor não encontrado no cadastro de colaboradores")
    manager_id = mgr_emp.data[0]["id"]

    sub = db.table("performance_employees").select("*").eq("id", employee_id).eq("manager_id", manager_id).eq("active", True).execute()
    if not sub.data:
        raise HTTPException(403, detail="Colaborador não é subordinado direto")
    emp = sub.data[0]

    if not emp.get("has_corporate_email") or not emp.get("email"):
        raise HTTPException(400, detail="Colaborador não possui e-mail corporativo")

    cycle = _get_open_cycle(db)
    if not cycle:
        raise HTTPException(400, detail="Nenhum ciclo aberto no momento")

    review = (
        db.table("performance_reviews")
        .select("id,evaluator_id,status")
        .eq("employee_id", employee_id)
        .eq("cycle_id", cycle["id"])
        .eq("is_self_evaluation", False)
        .execute()
    )
    if not review.data:
        raise HTTPException(404, detail="Colaborador ainda não foi avaliado neste ciclo")
    rev = review.data[0]

    existing_ack = (
        db.table("performance_review_acknowledgments")
        .select("id")
        .eq("review_id", rev["id"])
        .eq("employee_id", employee_id)
        .execute()
    )
    if existing_ack.data:
        raise HTTPException(400, detail="Colaborador já registrou ciência desta avaliação")

    existing_token = (
        db.table("performance_acknowledgment_tokens")
        .select("*")
        .eq("review_id", rev["id"])
        .eq("employee_id", employee_id)
        .is_("used_at", "null")
        .execute()
    )

    if existing_token.data:
        ack_token = str(existing_token.data[0]["token"])
    else:
        tok_res = db.table("performance_acknowledgment_tokens").insert({
            "review_id": rev["id"],
            "employee_id": employee_id,
            "sent_at": "now()",
            "expires_at": (datetime.now(tz=timezone.utc) + timedelta(days=30)).isoformat(),
        }).execute()
        if not tok_res.data:
            raise HTTPException(500, detail="Erro ao criar token de ciência")
        ack_token = str(tok_res.data[0]["token"])

    evaluator = db.table("performance_employees").select("name").eq("id", rev.get("evaluator_id", "")).execute()
    evaluator_name = evaluator.data[0]["name"] if evaluator.data else "seu gestor"

    company_name = ""
    if emp.get("company_id"):
        co = db.table("performance_companies").select("name").eq("id", emp["company_id"]).execute()
        company_name = co.data[0]["name"] if co.data else ""
    ok = send_ciencia_email(
        employee_name=emp["name"],
        employee_email=emp["email"],
        evaluator_name=evaluator_name,
        cycle_name=cycle["name"],
        token=ack_token,
        frontend_url=frontend_url,
        company_name=company_name,
    )
    return {"ok": ok, "employee_id": employee_id}

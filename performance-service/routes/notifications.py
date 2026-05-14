import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/performance/notifications")
_logger = logging.getLogger(__name__)

_PERF_ROLES = ("admin", "rh", "gestor", "coordenador", "supervisor", "colaborador")


@router.get("/summary")
def notifications_summary(
    current_user: Annotated[dict, Depends(require_role(*_PERF_ROLES))],
) -> dict:
    db = get_supabase()
    role = current_user.get("role")
    email = current_user.get("email", "")

    emp = db.table("performance_employees").select("id").eq("email", email).execute()
    emp_id = emp.data[0]["id"] if emp.data else None

    pending_goal_acks = 0
    pending_self_review = 0
    pending_manager_review = 0
    pending_ack_result = 0

    if role in ("admin", "rh"):
        pending_goal_acks = len(
            db.table("performance_goals").select("id").eq("status", "draft").execute().data
        )
        pending_ack_result = len(
            db.table("performance_reviews").select("id").eq("status", "pending_ack").execute().data
        )
        pending_manager_review = len(
            db.table("performance_reviews").select("id").eq("status", "pending_manager").execute().data
        )
        pending_self_review = len(
            db.table("performance_reviews").select("id").eq("status", "pending_self").execute().data
        )
    elif emp_id:
        pending_goal_acks = len(
            db.table("performance_goals").select("id").eq("owner_id", emp_id).eq("status", "draft").execute().data
        )
        pending_ack_result = len(
            db.table("performance_reviews").select("id").eq("employee_id", emp_id).eq("status", "pending_ack").execute().data
        )
        pending_self_review = len(
            db.table("performance_reviews").select("id").eq("employee_id", emp_id).eq("status", "pending_self").execute().data
        )
        if role in ("gestor", "coordenador", "supervisor"):
            pending_manager_review = len(
                db.table("performance_reviews").select("id").eq("reviewer_id", emp_id).eq("status", "pending_manager").execute().data
            )

    total = pending_goal_acks + pending_self_review + pending_manager_review + pending_ack_result
    return {
        "pending_goal_acks": pending_goal_acks,
        "pending_self_review": pending_self_review,
        "pending_manager_review": pending_manager_review,
        "pending_ack_result": pending_ack_result,
        "total_pending": total,
    }

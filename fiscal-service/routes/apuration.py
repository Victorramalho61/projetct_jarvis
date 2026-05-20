import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from auth import get_current_user, require_role
from db import get_supabase

router = APIRouter(prefix="/api/fiscal")
_logger = logging.getLogger(__name__)


@router.post("/{company_id}/periods/{period_id}/apuration/run")
async def run_apuration(
    company_id: str,
    period_id: str,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(require_role("admin")),
):
    sb = get_supabase()
    period = sb.table("fiscal_periods").select("id,ano,mes").eq(
        "id", period_id
    ).eq("company_id", company_id).execute()
    if not period.data:
        raise HTTPException(status_code=404, detail="Período não encontrado")

    background_tasks.add_task(_run_apuration_background, company_id, period_id)
    return {"ok": True, "message": "Apuração iniciada em background"}


@router.get("/{company_id}/periods/{period_id}/apuration")
def get_apuration(
    company_id: str,
    period_id: str,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    period = sb.table("fiscal_periods").select("id").eq(
        "id", period_id
    ).eq("company_id", company_id).execute()
    if not period.data:
        raise HTTPException(status_code=404, detail="Período não encontrado")

    result = sb.table("fiscal_apurations").select("*").eq(
        "period_id", period_id
    ).order("tipo_tributo").execute()
    return result.data


@router.get("/{company_id}/apuration/history")
def apuration_history(
    company_id: str,
    limit: int = 12,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    periods = sb.table("fiscal_periods").select("id,ano,mes").eq(
        "company_id", company_id
    ).order("ano", desc=True).order("mes", desc=True).limit(limit).execute()

    if not periods.data:
        return []

    period_ids = [p["id"] for p in periods.data]
    apurations = sb.table("fiscal_apurations").select("*").in_(
        "period_id", period_ids
    ).execute()

    period_map = {p["id"]: p for p in periods.data}
    result = []
    for ap in apurations.data:
        p = period_map.get(ap["period_id"], {})
        result.append({**ap, "ano": p.get("ano"), "mes": p.get("mes")})
    return result


async def _run_apuration_background(company_id: str, period_id: str):
    from services.apuration_engine import ApurationEngine
    from db import get_supabase

    sb = get_supabase()
    try:
        engine = ApurationEngine(sb)
        engine.run(company_id, period_id)
    except Exception:
        _logger.exception("Apuração falhou para period %s", period_id)

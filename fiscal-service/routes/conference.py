import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from auth import get_current_user, require_role
from db import get_supabase

router = APIRouter(prefix="/api/fiscal")
_logger = logging.getLogger(__name__)


@router.post("/{company_id}/periods/{period_id}/conference/run")
async def run_conference(
    company_id: str,
    period_id: str,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(require_role("admin")),
):
    sb = get_supabase()
    period = sb.table("fiscal_periods").select("id,ano,mes,status").eq(
        "id", period_id
    ).eq("company_id", company_id).execute()
    if not period.data:
        raise HTTPException(status_code=404, detail="Período não encontrado")

    background_tasks.add_task(_run_conference_background, company_id, period_id)
    return {"ok": True, "message": "Conferência iniciada em background"}


@router.get("/{company_id}/periods/{period_id}/conference/report")
def conference_report(
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

    result = sb.table("fiscal_conference_reports").select("*").eq(
        "period_id", period_id
    ).order("created_at", desc=True).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Relatório não encontrado — execute a conferência primeiro")
    return result.data[0]


@router.get("/{company_id}/periods")
def list_periods(
    company_id: str,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    result = sb.table("fiscal_periods").select(
        "id,ano,mes,status,fechado_em,created_at"
    ).eq("company_id", company_id).order("ano", desc=True).order("mes", desc=True).execute()
    return result.data


async def _run_conference_background(company_id: str, period_id: str):
    from services.conference_engine import ConferenceEngine
    from services.claude_analyzer import analyze_conference
    from db import get_supabase

    sb = get_supabase()
    try:
        engine = ConferenceEngine(sb)
        report = engine.run(company_id, period_id)

        claude_text = ""
        try:
            claude_text = await analyze_conference(report)
        except Exception as e:
            _logger.warning("Claude analysis falhou: %s", e)

        sb.table("fiscal_conference_reports").insert({
            "period_id": period_id,
            "total_documentos": report["total"],
            "documentos_ok": report["ok"],
            "documentos_divergencia": report["divergencias"],
            "divergencias_resumo": report["resumo"],
            "claude_analysis": claude_text,
        }).execute()
    except Exception:
        _logger.exception("Conferência falhou para period %s", period_id)

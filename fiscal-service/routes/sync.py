import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from auth import require_role, get_current_user
from db import get_supabase

router = APIRouter(prefix="/api/fiscal")
_logger = logging.getLogger(__name__)


@router.post("/{company_id}/sync/run")
async def run_sync(
    company_id: str,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(require_role("admin")),
):
    sb = get_supabase()
    result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,"
        "cert_pfx_encrypted,cert_password_encrypted,ultimo_nsu_nfe,ultimo_nsu_cte"
    ).eq("id", company_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    company = result.data[0]
    background_tasks.add_task(_run_sync_background, company, janela="manual")
    return {"ok": True, "message": "Sync iniciado em background"}


@router.get("/{company_id}/sync/logs")
def sync_logs(
    company_id: str,
    limit: int = 30,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    result = sb.table("fiscal_sync_logs").select("*").eq(
        "company_id", company_id
    ).order("executado_em", desc=True).limit(limit).execute()
    return result.data


@router.get("/{company_id}/sync/status")
def sync_status(
    company_id: str,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    company = sb.table("fiscal_companies").select(
        "cnpj,nome,ultimo_nsu_nfe,ultimo_nsu_cte,ultima_sync,sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo"
    ).eq("id", company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    total_docs = sb.table("fiscal_documents").select(
        "id", count="exact"
    ).eq("company_id", company_id).execute()

    pending_mun = sb.table("fiscal_nfse_municipalities").select(
        "id", count="exact"
    ).eq("company_id", company_id).eq("status", "pendente").execute()

    row = company.data[0]
    return {
        **row,
        "total_documentos": total_docs.count or 0,
        "municipios_pendentes": pending_mun.count or 0,
    }


async def _run_sync_background(company: dict, janela: str = "manual"):
    from services.scheduler import _run_sync
    await _run_sync(company, janela=janela)

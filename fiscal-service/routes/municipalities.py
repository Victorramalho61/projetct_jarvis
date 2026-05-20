import logging

from fastapi import APIRouter, Depends, HTTPException

from auth import require_role, get_current_user
from db import get_supabase

router = APIRouter(prefix="/api/fiscal")
_logger = logging.getLogger(__name__)


@router.get("/{company_id}/municipalities")
def list_municipalities(
    company_id: str,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    result = sb.table("fiscal_nfse_municipalities").select("*").eq(
        "company_id", company_id
    ).order("uf").execute()
    return result.data


@router.post("/{company_id}/municipalities/seed")
def seed_municipalities(
    company_id: str,
    _user: dict = Depends(require_role("admin")),
):
    from services.nfse_city_registry import NFSE_CITY_REGISTRY
    sb = get_supabase()

    company = sb.table("fiscal_companies").select("id").eq("id", company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    rows = []
    for ibge, info in NFSE_CITY_REGISTRY.items():
        rows.append({
            "company_id": company_id,
            "municipio_ibge": ibge,
            "municipio_nome": info["nome"],
            "uf": info["uf"],
            "sistema_tipo": info["tipo"],
            "status": "pendente",
            "ativo": False,
        })

    # upsert — não sobrescreve status de municípios já cadastrados
    sb.table("fiscal_nfse_municipalities").upsert(
        rows, on_conflict="company_id,municipio_ibge", ignore_duplicates=True
    ).execute()

    return {"ok": True, "municipios_inseridos": len(rows)}


@router.patch("/{company_id}/municipalities/{ibge}/activate")
def activate_municipality(
    company_id: str,
    ibge: str,
    _user: dict = Depends(require_role("admin")),
):
    sb = get_supabase()
    result = sb.table("fiscal_nfse_municipalities").update({
        "status": "cadastrado",
        "ativo": True,
    }).eq("company_id", company_id).eq("municipio_ibge", ibge).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return {"ok": True, "municipio": ibge, "status": "cadastrado"}


@router.patch("/{company_id}/municipalities/{ibge}/deactivate")
def deactivate_municipality(
    company_id: str,
    ibge: str,
    _user: dict = Depends(require_role("admin")),
):
    sb = get_supabase()
    result = sb.table("fiscal_nfse_municipalities").update({
        "ativo": False,
    }).eq("company_id", company_id).eq("municipio_ibge", ibge).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return {"ok": True, "municipio": ibge, "ativo": False}

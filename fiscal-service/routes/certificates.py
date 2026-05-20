import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from auth import require_role, get_current_user
from db import get_supabase, get_settings

router = APIRouter(prefix="/api/fiscal")
_logger = logging.getLogger(__name__)


@router.post("/{company_id}/certificates")
async def upload_certificate(
    company_id: str,
    arquivo: UploadFile = File(...),
    senha: str = Form(...),
    _user: dict = Depends(require_role("admin")),
):
    settings = get_settings()
    if not settings.cert_encryption_key:
        raise HTTPException(status_code=500, detail="CERT_ENCRYPTION_KEY não configurado")

    pfx_bytes = await arquivo.read()
    if len(pfx_bytes) == 0:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    from services.cert_manager import encrypt_cert, get_cert_expiry
    try:
        pfx_enc, pass_enc = encrypt_cert(pfx_bytes, senha, settings.cert_encryption_key)
        expiry = get_cert_expiry(pfx_bytes, senha)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Certificado inválido: {e}")

    sb = get_supabase()
    result = sb.table("fiscal_companies").select("id").eq("id", company_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    sb.table("fiscal_companies").update({
        "cert_pfx_encrypted": pfx_enc,
        "cert_password_encrypted": pass_enc,
        "cert_expiry": expiry.isoformat() if expiry else None,
    }).eq("id", company_id).execute()

    return {"ok": True, "cert_expiry": expiry.isoformat() if expiry else None}


@router.get("/{company_id}/certificates/status")
def certificate_status(
    company_id: str,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    result = sb.table("fiscal_companies").select(
        "cert_expiry,cert_pfx_encrypted"
    ).eq("id", company_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    row = result.data[0]
    expiry = row.get("cert_expiry")
    has_cert = bool(row.get("cert_pfx_encrypted"))
    dias = None
    if expiry and has_cert:
        dias = (date.fromisoformat(expiry) - date.today()).days

    return {
        "has_certificate": has_cert,
        "cert_expiry": expiry,
        "dias_para_vencer": dias,
        "status": (
            "ok" if dias and dias > 30 else
            "expirando" if dias and dias > 0 else
            "expirado" if dias is not None and dias <= 0 else
            "sem_certificado"
        ),
    }


@router.delete("/{company_id}/certificates")
def delete_certificate(
    company_id: str,
    _user: dict = Depends(require_role("admin")),
):
    sb = get_supabase()
    sb.table("fiscal_companies").update({
        "cert_pfx_encrypted": None,
        "cert_password_encrypted": None,
        "cert_expiry": None,
    }).eq("id", company_id).execute()
    return {"ok": True}

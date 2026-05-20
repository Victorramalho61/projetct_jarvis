import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from auth import get_current_user, require_role
from db import get_supabase

router = APIRouter(prefix="/api/fiscal")
_logger = logging.getLogger(__name__)


@router.post("/{company_id}/documents/upload")
async def upload_document(
    company_id: str,
    arquivo: UploadFile = File(...),
    _user: dict = Depends(require_role("admin")),
):
    xml_bytes = await arquivo.read()
    if not xml_bytes:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    from services.xml_parser import parse_xml_auto
    try:
        doc = parse_xml_auto(xml_bytes.decode("utf-8", errors="replace"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"XML inválido: {e}")

    sb = get_supabase()
    company = sb.table("fiscal_companies").select("id").eq("id", company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    # resolve period
    emissao = doc.get("data_emissao")
    period_id = None
    if emissao:
        d = date.fromisoformat(emissao) if isinstance(emissao, str) else emissao
        period_res = sb.table("fiscal_periods").upsert({
            "company_id": company_id,
            "ano": d.year,
            "mes": d.month,
            "status": "aberto",
        }, on_conflict="company_id,ano,mes").execute()
        if period_res.data:
            period_id = period_res.data[0]["id"]

    doc["company_id"] = company_id
    doc["period_id"] = period_id
    doc["xml_content"] = xml_bytes.decode("utf-8", errors="replace")

    try:
        result = sb.table("fiscal_documents").upsert(
            doc, on_conflict="chave_acesso"
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=409, detail=f"Erro ao salvar documento: {e}")

    return {"ok": True, "document_id": result.data[0]["id"] if result.data else None}


@router.get("/{company_id}/documents")
def list_documents(
    company_id: str,
    tipo: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    ano: Optional[int] = Query(None),
    mes: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    q = sb.table("fiscal_documents").select(
        "id,tipo,chave_acesso,numero,serie,emitente_cnpj,emitente_nome,"
        "destinatario_cnpj,destinatario_nome,data_emissao,valor_total,"
        "valor_icms,valor_pis,valor_cofins,status,created_at"
    ).eq("company_id", company_id)

    if tipo:
        q = q.eq("tipo", tipo)
    if status:
        q = q.eq("status", status)
    if ano and mes:
        q = q.gte("data_emissao", f"{ano}-{mes:02d}-01").lt(
            "data_emissao",
            f"{ano}-{mes+1:02d}-01" if mes < 12 else f"{ano+1}-01-01"
        )

    result = q.order("data_emissao", desc=True).range(offset, offset + limit - 1).execute()
    return result.data


@router.get("/{company_id}/documents/{document_id}")
def get_document(
    company_id: str,
    document_id: str,
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()
    result = sb.table("fiscal_documents").select("*").eq(
        "id", document_id
    ).eq("company_id", company_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return result.data[0]

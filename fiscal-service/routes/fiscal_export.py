"""
Exportação de documentos fiscais: CSV (dados estruturados) e ZIP de XMLs.
Respeita os mesmos filtros da busca: company_id, data_inicio, data_fim, fonte, status, tipo.
"""
import csv
import io
import zipfile
import logging
from typing import Optional

from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse

from auth import get_current_user
from db import get_supabase

router = APIRouter(prefix="/api/fiscal", tags=["export"])

_logger = logging.getLogger(__name__)

_CSV_FIELDS = [
    "chave_acesso", "tipo", "numero", "serie", "data_emissao",
    "emitente_cnpj", "emitente_nome",
    "destinatario_cnpj", "destinatario_nome",
    "valor_total", "valor_produtos", "valor_icms",
    "valor_pis", "valor_cofins", "valor_iss", "valor_iss_retido",
    "municipio_nome", "status", "fonte", "tipo_schema",
    "natureza_operacao", "created_at",
]


@router.get("/nfse/export/csv")
def export_csv(
    company_id:  str            = Query(..., description="UUID da empresa"),
    data_inicio: Optional[str]  = Query(None, description="YYYY-MM-DD"),
    data_fim:    Optional[str]  = Query(None, description="YYYY-MM-DD"),
    fonte:       Optional[str]  = Query(None, description="ndd | portal_nacional | sefaz"),
    status:      Optional[str]  = Query(None, description="pendente | conferido | divergencia | cancelado"),
    tipo:        Optional[str]  = Query(None, description="NFSe | NFe | CTe — padrão: todos"),
    _user: dict = Depends(get_current_user),
):
    """
    Exporta documentos em CSV (UTF-8 BOM para Excel).
    Sem limite de paginação — retorna tudo que satisfaça os filtros.
    """
    sb = get_supabase()
    q  = (
        sb.table("fiscal_documents")
        .select(",".join(_CSV_FIELDS))
        .eq("company_id", company_id)
        .order("data_emissao", desc=True)
    )
    if tipo and "," in tipo:
        q = q.in_("tipo", [t.strip() for t in tipo.split(",")])
    elif tipo:
        q = q.eq("tipo", tipo)
    if data_inicio: q = q.gte("data_emissao", data_inicio)
    if data_fim:    q = q.lte("data_emissao", data_fim)
    if fonte:       q = q.eq("fonte", fonte)
    if status:      q = q.eq("status", status)

    rows = q.execute().data or []
    _logger.info("export_csv: %d linhas para company_id=%s", len(rows), company_id[:8])

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    filename = _build_filename(company_id, data_inicio, data_fim, tipo, "csv")
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),  # BOM para Excel abrir direto
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/nfse/export/xml")
def export_xml_zip(
    company_id:  str            = Query(..., description="UUID da empresa"),
    data_inicio: Optional[str]  = Query(None, description="YYYY-MM-DD"),
    data_fim:    Optional[str]  = Query(None, description="YYYY-MM-DD"),
    fonte:       Optional[str]  = Query(None, description="ndd | portal_nacional | sefaz"),
    tipo:        Optional[str]  = Query(None, description="NFSe | NFe | CTe — padrão: todos"),
    _user: dict = Depends(get_current_user),
):
    """
    Exporta XMLs originais em arquivo ZIP (um .xml por documento).
    Inclui apenas documentos com xml_content preenchido.
    """
    sb = get_supabase()
    q  = (
        sb.table("fiscal_documents")
        .select("chave_acesso,tipo,numero,data_emissao,xml_content")
        .eq("company_id", company_id)
        .not_.is_("xml_content", "null")
        .order("data_emissao", desc=True)
    )
    if tipo and "," in tipo:
        q = q.in_("tipo", [t.strip() for t in tipo.split(",")])
    elif tipo:
        q = q.eq("tipo", tipo)
    if data_inicio: q = q.gte("data_emissao", data_inicio)
    if data_fim:    q = q.lte("data_emissao", data_fim)
    if fonte:       q = q.eq("fonte", fonte)

    rows = q.execute().data or []
    _logger.info("export_xml_zip: %d XMLs para company_id=%s", len(rows), company_id[:8])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            xml = row.get("xml_content") or ""
            if not xml:
                continue
            tipo_doc = row.get("tipo", "DOC")
            chave    = row.get("chave_acesso", "sem_chave")
            num      = row.get("numero") or chave[:8]
            data     = row.get("data_emissao") or "0000-00-00"
            fname    = f"{tipo_doc}_{data}_{num}_{chave}.xml"
            zf.writestr(fname, xml.encode("utf-8"))

    buf.seek(0)
    filename = _build_filename(company_id, data_inicio, data_fim, tipo, "zip")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_filename(company_id: str, inicio, fim, tipo, ext: str) -> str:
    parts = [tipo or "fiscal", company_id[:8]]
    if inicio:
        parts.append(inicio)
    if fim and fim != inicio:
        parts.append(f"a_{fim}")
    return "_".join(parts) + f".{ext}"

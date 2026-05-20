from fastapi import APIRouter, BackgroundTasks, Query, Depends, HTTPException
from typing import Optional

from auth import get_current_user, require_role
from db import get_supabase

router = APIRouter(prefix="/api/fiscal", tags=["nfse-search"])


@router.get("/companies")
def list_companies(_user: dict = Depends(get_current_user)):
    """Lista todas as empresas fiscais cadastradas."""
    sb = get_supabase()
    result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,regime,sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,"
        "ndd_last_sync_at,ndd_access_token,ndd_token_expires_at,cert_expiry,ultima_sync"
    ).order("nome").execute()
    return result.data or []


@router.post("/nfse/sync/run")
async def run_nfse_sync(
    background_tasks: BackgroundTasks,
    _user: dict = Depends(require_role("admin")),
):
    """Dispara o sync incremental NFSe NDD imediatamente (não aguarda 05:00)."""
    from services.scheduler import _sync_nfse_ndd_incremental
    background_tasks.add_task(_sync_nfse_ndd_incremental)
    return {"ok": True, "message": "Sync NFSe NDD iniciado em background"}


@router.get("/nfse")
def search_nfse(
    q:                Optional[str]   = Query(None, description="Busca full-text (emitente, destinatário, município, natureza)"),
    company_id:       Optional[str]   = Query(None),
    data_inicio:      Optional[str]   = Query(None, description="YYYY-MM-DD"),
    data_fim:         Optional[str]   = Query(None, description="YYYY-MM-DD"),
    emitente_cnpj:    Optional[str]   = Query(None, description="CNPJ parcial ou completo"),
    destinatario_cnpj: Optional[str]  = Query(None, description="CNPJ parcial ou completo"),
    municipio:        Optional[str]   = Query(None, description="Nome do município (parcial)"),
    status:           Optional[str]   = Query(None, description="pendente | conferido | divergencia | cancelado"),
    valor_min:        Optional[float] = Query(None),
    valor_max:        Optional[float] = Query(None),
    limit:            int             = Query(50, ge=1, le=200),
    offset:           int             = Query(0, ge=0),
    orderby:          str             = Query("data_emissao.desc", description="campo.asc ou campo.desc"),
    _user: dict = Depends(get_current_user),
):
    sb = get_supabase()

    # Full-text search via RPC (usa search_vector + websearch_to_tsquery com ranking)
    if q:
        try:
            rpc_result = sb.rpc("fiscal_nfse_search", {
                "p_query":      q,
                "p_company_id": company_id,
                "p_limit":      limit,
                "p_offset":     offset,
            }).execute()
            data = rpc_result.data or []
        except Exception:
            data = []
        return {"total": len(data), "offset": offset, "limit": limit, "data": data}

    # Filtros simples sem full-text
    query = sb.table("fiscal_documents").select(
        "id,company_id,tipo,chave_acesso,numero,serie,"
        "emitente_cnpj,emitente_nome,destinatario_cnpj,destinatario_nome,"
        "natureza_operacao,data_emissao,valor_total,valor_iss,valor_iss_retido,"
        "municipio_nome,status,ndd_id,ndd_sync_at,created_at"
    ).eq("tipo", "NFSe")

    if company_id:              query = query.eq("company_id", company_id)
    if status:                  query = query.eq("status", status)
    if data_inicio:             query = query.gte("data_emissao", data_inicio)
    if data_fim:                query = query.lte("data_emissao", data_fim)
    if valor_min is not None:   query = query.gte("valor_total", valor_min)
    if valor_max is not None:   query = query.lte("valor_total", valor_max)
    if emitente_cnpj:           query = query.ilike("emitente_cnpj", f"%{emitente_cnpj}%")
    if destinatario_cnpj:       query = query.ilike("destinatario_cnpj", f"%{destinatario_cnpj}%")
    if municipio:               query = query.ilike("municipio_nome", f"%{municipio}%")

    parts = (orderby + ".desc").split(".")
    col, direction = parts[0], parts[1]
    query = query.order(col, desc=(direction == "desc"))

    result = query.range(offset, offset + limit - 1).execute()
    data = result.data or []

    return {"total": len(data), "offset": offset, "limit": limit, "data": data}


@router.get("/nfse/stats")
def nfse_stats(
    company_id: Optional[str] = Query(None),
    ano:        Optional[int] = Query(None),
    mes:        Optional[int] = Query(None),
    _user: dict = Depends(get_current_user),
):
    """Totais por período: count, soma valor_total, soma valor_iss, breakdown por município e status."""
    sb = get_supabase()
    query = sb.table("fiscal_documents").select(
        "data_emissao,valor_total,valor_iss,municipio_nome,status"
    ).eq("tipo", "NFSe")

    if company_id:
        query = query.eq("company_id", company_id)
    if ano:
        query = query.gte("data_emissao", f"{ano}-01-01").lte("data_emissao", f"{ano}-12-31")
    if mes and ano:
        import calendar
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        query = query.gte("data_emissao", f"{ano}-{mes:02d}-01").lte(
            "data_emissao", f"{ano}-{mes:02d}-{ultimo_dia:02d}"
        )

    result = query.execute()
    docs = result.data or []

    return {
        "total_notas":  len(docs),
        "valor_total":  round(sum(d.get("valor_total") or 0 for d in docs), 2),
        "valor_iss":    round(sum(d.get("valor_iss") or 0 for d in docs), 2),
        "por_municipio": _group_count(docs, "municipio_nome"),
        "por_status":    _group_count(docs, "status"),
    }


def _group_count(docs: list, field: str) -> dict:
    counts: dict = {}
    for d in docs:
        k = d.get(field) or "desconhecido"
        counts[k] = counts.get(k, 0) + 1
    return counts

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
        "id,cnpj,nome,regime,grupo,tipo,cidade,uf_sede,"
        "sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,"
        "ndd_last_sync_at,ndd_access_token,ndd_refresh_token,ndd_token_expires_at,cert_expiry,ultima_sync"
    ).order("grupo").order("tipo").execute()
    return result.data or []


@router.get("/sync/logs")
def list_sync_logs_global(
    limit: int = Query(30, ge=1, le=100),
    _user: dict = Depends(get_current_user),
):
    """Logs de sync de todas as empresas, ordenados por data desc."""
    sb = get_supabase()
    result = (
        sb.table("fiscal_sync_logs")
        .select("id,company_id,tipo,status,documentos_novos,documentos_cancelados,erro_msg,janela,executado_em")
        .order("executado_em", desc=True)
        .limit(limit)
        .execute()
    )
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


@router.get("/nfse/stats")
def nfse_stats(
    company_id: Optional[str] = Query(None),
    ano:        Optional[int] = Query(None),
    mes:        Optional[int] = Query(None),
    _user: dict = Depends(get_current_user),
):
    """Totais agregados via SQL — sem varredura full-table no Python."""
    sb = get_supabase()
    result = sb.rpc("fiscal_nfse_stats", {
        "p_company_id": company_id,
        "p_ano": ano,
        "p_mes": mes,
    }).execute()
    data = result.data
    if isinstance(data, list):
        data = data[0] if data else {}
    return data or {
        "total_notas": 0, "valor_total": 0, "valor_iss": 0,
        "por_municipio": {}, "por_status": {},
    }


@router.get("/nfse/{doc_id}")
def get_nfse_detail(
    doc_id: str,
    _user: dict = Depends(get_current_user),
):
    """Retorna NFSe completa incluindo xml_content."""
    sb = get_supabase()
    r = sb.table("fiscal_documents").select("*").eq("id", doc_id).eq("tipo", "NFSe").execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="NFSe não encontrada")
    return r.data[0]


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

import logging
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Body, Query, Depends, HTTPException
from typing import Optional

from auth import get_current_user, require_role
from db import get_supabase, get_settings

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fiscal", tags=["nfse-search"])

# In-memory cache para lista de empresas (raramente muda, cara de buscar)
_COMPANIES_TTL = 300  # 5 minutos
_companies_cache: dict = {"data": None, "ts": 0.0}


def _invalidate_companies_cache() -> None:
    _companies_cache["data"] = None
    _companies_cache["ts"] = 0.0


@router.get("/companies")
def list_companies(_user: dict = Depends(get_current_user)):
    """Lista todas as empresas fiscais cadastradas (cache 5 min)."""
    now = time.monotonic()
    if _companies_cache["data"] is not None and now - _companies_cache["ts"] < _COMPANIES_TTL:
        return _companies_cache["data"]
    sb = get_supabase()
    result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,regime,grupo,tipo,cidade,uf_sede,"
        "sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,"
        "ndd_last_sync_at,ndd_access_token,ndd_refresh_token,ndd_token_expires_at,cert_expiry,ultima_sync"
    ).order("grupo").order("tipo").execute()
    data = result.data or []
    _companies_cache["data"] = data
    _companies_cache["ts"] = now
    return data


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
    fonte:            Optional[str]   = Query(None, description="ndd | portal_nacional | sefaz"),
    tipo:             Optional[str]   = Query(None, description="NFSe | NFe | CTe"),
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
        "municipio_nome,status,fonte,tipo_schema,ndd_id,ndd_sync_at,created_at"
    )

    # tipo pode ser: "NFSe", "NFe", "CTe" ou "NFe,CTe" para múltiplos
    if tipo and "," in tipo:
        query = query.in_("tipo", [t.strip() for t in tipo.split(",")])
    elif tipo:
        query = query.eq("tipo", tipo)
    else:
        query = query.eq("tipo", "NFSe")  # default: NFSe

    if company_id:              query = query.eq("company_id", company_id)
    if status:                  query = query.eq("status", status)
    if fonte:                   query = query.eq("fonte", fonte)
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


@router.post("/portal-nfse/sync/run")
def trigger_portal_nfse_sync(
    company_id: Optional[str] = Query(None, description="UUID da empresa; omitir para todas"),
    _user: dict = Depends(require_role("admin")),
):
    """Dispara sync Portal Nacional NFS-e (ADN) manualmente em daemon thread."""
    from services.scheduler import _sync_portal_nfse_company

    if not company_id:
        raise HTTPException(400, "company_id obrigatório para sync manual")

    sb  = get_supabase()
    res = sb.table("fiscal_companies").select(
        "id,cnpj,cert_pfx_encrypted,cert_password_encrypted,"
        "ultimo_nsu_nfse_nacional,sync_portal_nfse_ativo"
    ).eq("id", company_id).execute()
    if not res.data:
        raise HTTPException(404, "Empresa não encontrada")

    # daemon thread: roda fora do event loop, não bloqueia o servidor
    t = threading.Thread(
        target=_sync_portal_nfse_company,
        args=(res.data[0], "manual"),
        daemon=True,
        name=f"portal-nfse-{company_id[:8]}",
    )
    t.start()
    return {"ok": True, "message": f"Sync Portal NFS-e iniciado para empresa {company_id}"}


@router.get("/{company_id}/portal-nfse/logs")
def get_portal_nfse_logs(
    company_id: str,
    _: dict = Depends(get_current_user),
):
    """Últimas 5 tentativas de sync NFSe_Portal para esta empresa."""
    sb = get_supabase()
    logs = (
        sb.table("fiscal_sync_logs")
        .select("status,documentos_novos,documentos_cancelados,erro_msg,executado_em,nsu_final,nsu_inicial,janela")
        .eq("company_id", company_id)
        .eq("tipo", "NFSe_Portal")
        .order("executado_em", desc=True)
        .limit(5)
        .execute()
    )
    return logs.data or []


@router.get("/sync/status")
def get_sync_status(_user: dict = Depends(get_current_user)):
    """Status consolidado de todos os tipos de sync, por empresa."""
    sb = get_supabase()

    logs_result = sb.table("fiscal_sync_logs").select(
        "company_id,tipo,status,documentos_novos,documentos_cancelados,executado_em,erro_msg,nsu_final"
    ).order("executado_em", desc=True).limit(200).execute()
    logs = logs_result.data or []

    companies_result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,grupo,"
        "sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,sync_portal_nfse_ativo,"
        "ultimo_nsu_nfe,ultimo_nsu_cte,ultimo_nsu_nfse_nacional,"
        "portal_nfse_last_sync_at,sefaz_nfe_bloqueado_ate,sefaz_nfe_ultima_consulta_hb,"
        "cert_expiry"
    ).execute()
    companies = companies_result.data or []

    # Último log por (company_id, tipo)
    seen: dict[tuple, dict] = {}
    for log in logs:
        key = (log["company_id"], log["tipo"])
        if key not in seen:
            seen[key] = log

    def _get_log(cid, tipo):
        return seen.get((cid, tipo), {})

    now = datetime.now(timezone.utc)

    def _is_stuck(log: dict) -> bool:
        if log.get("status") != "running":
            return False
        ts = log.get("executado_em")
        if not ts:
            return False
        try:
            age = (now - datetime.fromisoformat(ts)).total_seconds()
            return age > 1800  # > 30 min = potencialmente preso
        except ValueError:
            return False

    return [
        {
            "company_id": c["id"],
            "cnpj":       c["cnpj"],
            "nome":       c["nome"],
            "grupo":      c.get("grupo"),
            "cert_expiry": c.get("cert_expiry"),
            "syncs": {
                "NFe": {
                    **_get_log(c["id"], "NFe"),
                    "ativo":        c["sync_nfe_ativo"],
                    "ultimo_nsu":   c["ultimo_nsu_nfe"],
                    "bloqueado_ate": c.get("sefaz_nfe_bloqueado_ate"),
                    "ultima_consulta_hb": c.get("sefaz_nfe_ultima_consulta_hb"),
                    "is_stuck":     _is_stuck(_get_log(c["id"], "NFe")),
                },
                "CTe": {
                    **_get_log(c["id"], "CTe"),
                    "ativo":      c["sync_cte_ativo"],
                    "ultimo_nsu": c["ultimo_nsu_cte"],
                    "is_stuck":   _is_stuck(_get_log(c["id"], "CTe")),
                },
                "NFSe_NDD": {
                    **_get_log(c["id"], "NFSe"),
                    "ativo":    c["sync_nfse_ativo"],
                    "is_stuck": _is_stuck(_get_log(c["id"], "NFSe")),
                },
                "NFSe_Portal": {
                    **_get_log(c["id"], "NFSe_Portal"),
                    "ativo":      c.get("sync_portal_nfse_ativo", False),
                    "ultimo_nsu": c.get("ultimo_nsu_nfse_nacional"),
                    "ultimo_sync": c.get("portal_nfse_last_sync_at"),
                    "is_stuck":   _is_stuck(_get_log(c["id"], "NFSe_Portal")),
                },
            },
        }
        for c in companies
    ]


@router.post("/fetch-by-key")
async def fetch_document_by_key(
    body: dict = Body(...),
    _user: dict = Depends(get_current_user),
):
    """
    Busca NF-e ou NFS-e por chave de acesso nos portais externos.
    Ordem: 1) banco local → 2) ADN (NFS-e Portal Nacional) → 3) SEFAZ NF-e.
    Salva automaticamente no banco se encontrado remotamente.
    """
    company_id = body.get("company_id")
    chave      = (body.get("chave_acesso") or "").replace(" ", "").strip()

    if not company_id or not chave:
        raise HTTPException(400, "company_id e chave_acesso são obrigatórios")
    if len(chave) not in (44, 50) or not chave.isdigit():
        raise HTTPException(400, "chave_acesso deve ter 44 dígitos (NF-e/CT-e) ou 50 dígitos (NFS-e Portal Nacional)")

    sb = get_supabase()

    # 1. Banco local
    existing = sb.table("fiscal_documents").select("*").eq("chave_acesso", chave).execute()
    if existing.data:
        return {"found": True, "source": "local", "document": existing.data[0]}

    # 2. Busca empresa e certificado
    co = sb.table("fiscal_companies").select(
        "id,cnpj,cert_pfx_encrypted,cert_password_encrypted"
    ).eq("id", company_id).execute()
    if not co.data:
        raise HTTPException(404, "Empresa não encontrada")
    company  = co.data[0]
    settings = get_settings()

    # 3. Tenta ADN (Portal Nacional NFS-e)
    if company.get("cert_pfx_encrypted"):
        try:
            from services.cert_manager import extract_pem_for_requests
            from services.portal_nfse_fetcher import PortalNFSeFetcher
            from services.xml_parser import parse_nfse_portal, _compute_hash

            with extract_pem_for_requests(
                company["cert_pfx_encrypted"],
                company["cert_password_encrypted"],
                settings.cert_encryption_key,
            ) as (cert_path, key_path):
                fetcher = PortalNFSeFetcher(
                    company["cnpj"], cert_path, key_path,
                    getattr(settings, "portal_nfse_ambiente", "1"),
                )
                xml_str = fetcher.consulta_por_chave(chave)

            if xml_str:
                parsed = parse_nfse_portal(xml_str)
                if parsed:
                    parsed.update({
                        "company_id":  company_id,
                        "fonte":       "portal_nacional",
                        "xml_content": xml_str,
                        "xml_hash":    _compute_hash(xml_str),
                    })
                    parsed.pop("_items", None)
                    sb.table("fiscal_documents").upsert(parsed, on_conflict="chave_acesso").execute()
                    return {"found": True, "source": "portal_nacional", "document": parsed}
        except Exception as exc:
            _logger.warning("fetch_by_key ADN erro: %s", exc)

    # 4. Tenta SEFAZ NF-e (por chave, usando NfeConsultaProtocolo estadual)
    if company.get("cert_pfx_encrypted"):
        try:
            from services.cert_manager import extract_pem_for_requests
            from services.sefaz_nfe_fetcher import fetch_nfe_by_key
            from services.xml_parser import parse_nfe, _compute_hash

            with extract_pem_for_requests(
                company["cert_pfx_encrypted"],
                company["cert_password_encrypted"],
                settings.cert_encryption_key,
            ) as (cert_path, key_path):
                xml_str = fetch_nfe_by_key(
                    chave, cert_path, key_path,
                    getattr(settings, "sefaz_ambiente", "1"),
                )

            if xml_str:
                parsed = parse_nfe(xml_str)
                if parsed:
                    parsed.update({
                        "company_id":  company_id,
                        "fonte":       "sefaz",
                        "xml_content": xml_str,
                        "xml_hash":    _compute_hash(xml_str),
                    })
                    sb.table("fiscal_documents").upsert(parsed, on_conflict="chave_acesso").execute()
                    return {"found": True, "source": "sefaz", "document": parsed}
        except Exception as exc:
            _logger.warning("fetch_by_key SEFAZ erro: %s", exc)

    raise HTTPException(404, f"Documento com chave {chave[:20]}... não encontrado em nenhum portal")

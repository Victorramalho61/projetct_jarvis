import asyncio
import logging
from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

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
    """Popula fiscal_nfse_municipalities a partir do registry. Preserva registros existentes."""
    from services.nfse_city_registry import NFSE_CITY_REGISTRY
    sb = get_supabase()

    company = sb.table("fiscal_companies").select("id").eq("id", company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    rows = []
    for ibge, info in NFSE_CITY_REGISTRY.items():
        # Usa tipo direto (carioca/paulistana/df) quando disponível; senão nddigital
        sistema = info.get("direct_tipo") or info["tipo"]
        rows.append({
            "company_id": company_id,
            "municipio_ibge": ibge,
            "municipio_nome": info["nome"],
            "uf": info["uf"],
            "sistema_tipo": sistema,
            "status": "pendente",
            "ativo": False,
        })

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


@router.post("/{company_id}/municipalities/{ibge}/test")
async def test_municipality(
    company_id: str,
    ibge: str,
    sandbox: bool = Query(default=True),
    _user: dict = Depends(require_role("admin")),
):
    """Testa conexão com API municipal usando certificado da empresa.
    sandbox=true usa URL de homologação (quando disponível).
    Retorna: {ok, tipo, docs_encontrados, sandbox}"""
    from services.cert_manager import extract_pem_for_requests
    from services.nfse_fetcher import NFSeFetcher
    from services.nfse_city_registry import NFSE_CITY_REGISTRY
    from db import get_settings

    city = NFSE_CITY_REGISTRY.get(ibge)
    if not city:
        raise HTTPException(status_code=404, detail=f"Município IBGE {ibge} não mapeado no registry")

    # Só suporta teste em tipos com API direta (não nddigital)
    tipo = city.get("direct_tipo") or city["tipo"]
    if tipo == "nddigital":
        raise HTTPException(
            status_code=400,
            detail="Município usa ND Digital — teste via /ndd/sync. Teste direto disponível apenas para carioca, paulistana, df, abrasf."
        )

    if sandbox:
        url = city.get("sandbox_url") or city.get("direct_url") or city["url"]
    else:
        url = city.get("direct_url") or city["url"]

    sb = get_supabase()
    company = sb.table("fiscal_companies").select(
        "cnpj,cert_pfx_encrypted,cert_password_encrypted"
    ).eq("id", company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    row = company.data[0]

    if not row.get("cert_pfx_encrypted"):
        raise HTTPException(status_code=400, detail="Empresa sem certificado digital cadastrado")

    settings = get_settings()
    hoje = date.today()
    data_inicio = hoje - timedelta(days=30)

    try:
        def _do_test():
            with extract_pem_for_requests(
                row["cert_pfx_encrypted"],
                row["cert_password_encrypted"],
                settings.cert_encryption_key,
            ) as (cert_path, key_path):
                fetcher = NFSeFetcher(row["cnpj"], cert_path, key_path)
                return fetcher.fetch_with_tipo_url(ibge, tipo, url, data_inicio, hoje)

        docs = await asyncio.to_thread(_do_test)
        return {
            "ok": True,
            "tipo": tipo,
            "url_testada": url,
            "docs_encontrados": len(docs),
            "sandbox": sandbox,
        }
    except Exception as e:
        _logger.warning("Teste municipal IBGE %s empresa %s: %s", ibge, company_id, e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{company_id}/municipalities/sync")
async def sync_municipalities(
    company_id: str,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(require_role("admin")),
):
    """Dispara sync via API direta para todos os municípios com ativo=true da empresa.
    Ignora municípios com sistema_tipo=nddigital (use /ndd/sync para esses)."""
    background_tasks.add_task(_sync_municipalities_background, company_id)
    return {"ok": True, "message": "Sync municipal direto iniciado em background"}


@router.post("/{company_id}/ndd/sync")
async def sync_ndd_manual(
    company_id: str,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(require_role("admin")),
):
    """Trigger manual do sync ND Digital para esta empresa."""
    background_tasks.add_task(_sync_ndd_background, company_id)
    return {"ok": True, "message": "Sync NDD iniciado em background"}


@router.post("/{company_id}/nfse/sync/all")
async def sync_all_nfse(
    company_id: str,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(require_role("admin")),
):
    """Sync unificado: dispara NDD + Portal Nacional + Municipal Direto para esta empresa."""
    background_tasks.add_task(_sync_all_nfse_background, company_id)
    return {"ok": True, "message": "Sync unificado NFS-e iniciado (NDD + Portal Nacional + Municipal)"}


# ── Background tasks ─────────────────────────────────────────────────────────

async def _sync_municipalities_background(company_id: str):
    """Sync via API direta para municípios ativos (não-nddigital)."""
    from services.cert_manager import extract_pem_for_requests
    from services.nfse_fetcher import NFSeFetcher
    from services.nfse_city_registry import NFSE_CITY_REGISTRY
    from services.scheduler import _ensure_period, _log_sync
    from db import get_supabase, get_settings

    sb = get_supabase()
    settings = get_settings()

    company = sb.table("fiscal_companies").select(
        "id,cnpj,cert_pfx_encrypted,cert_password_encrypted"
    ).eq("id", company_id).execute()
    if not company.data:
        _logger.error("Municipal sync: empresa %s não encontrada", company_id)
        return

    row = company.data[0]
    cnpj = row["cnpj"]

    if not row.get("cert_pfx_encrypted"):
        _logger.warning("[%s] Municipal sync: sem certificado", cnpj)
        return

    # Carrega municípios ativos com tipo != nddigital
    muns = sb.table("fiscal_nfse_municipalities").select("*").eq(
        "company_id", company_id
    ).eq("ativo", True).neq("sistema_tipo", "nddigital").execute()

    if not muns.data:
        _logger.info("[%s] Municipal sync: nenhum município direto ativo", cnpj)
        return

    hoje = date.today()
    data_inicio = hoje.replace(day=1)

    def _do_sync_all():
        with extract_pem_for_requests(
            row["cert_pfx_encrypted"],
            row["cert_password_encrypted"],
            settings.cert_encryption_key,
        ) as (cert_path, key_path):
            fetcher = NFSeFetcher(cnpj, cert_path, key_path)
            results = []
            for mun in muns.data:
                ibge = mun["municipio_ibge"]
                tipo = mun["sistema_tipo"]
                city = NFSE_CITY_REGISTRY.get(ibge, {})
                url  = city.get("direct_url") or city.get("url", "")
                docs_novos = 0
                erro_msg = None
                try:
                    docs = fetcher.fetch_with_tipo_url(ibge, tipo, url, data_inicio, hoje)
                    for doc in docs:
                        doc["company_id"] = company_id
                        doc["fonte"] = "municipal_direto"
                        _ensure_period(sb, company_id, doc.get("data_emissao"), doc)
                        try:
                            sb.table("fiscal_documents").upsert(
                                doc, on_conflict="chave_acesso"
                            ).execute()
                            docs_novos += 1
                        except Exception as e:
                            _logger.warning("[%s] Municipal upsert %s: %s", cnpj, ibge, e)
                    _logger.info("[%s] Municipal %s (%s): +%d docs", cnpj, mun["municipio_nome"], ibge, docs_novos)
                except Exception as e:
                    erro_msg = str(e)
                    _logger.error("[%s] Municipal %s ERRO: %s", cnpj, ibge, e)

                sb.table("fiscal_nfse_municipalities").update({
                    "last_sync_at": datetime.now(timezone.utc).isoformat(),
                    "docs_total": (mun.get("docs_total") or 0) + docs_novos,
                    "ultimo_erro": erro_msg,
                    "status": "cadastrado" if not erro_msg else "erro",
                }).eq("company_id", company_id).eq("municipio_ibge", ibge).execute()

                _log_sync(sb, company_id, "NFSe_Municipal", ibge, None, None,
                          docs_novos, 0, "ok" if not erro_msg else "erro", erro_msg, "manual")
                results.append({"ibge": ibge, "docs": docs_novos, "erro": erro_msg})
            return results

    await asyncio.to_thread(_do_sync_all)


async def _sync_ndd_background(company_id: str):
    from services.scheduler import sync_ndd_for_company
    try:
        await asyncio.to_thread(sync_ndd_for_company, company_id, "manual")
    except Exception as e:
        _logger.error("NDD manual ERRO empresa %s: %s", company_id, e)


async def _sync_all_nfse_background(company_id: str):
    """Dispara NDD + Portal Nacional + Municipal Direto em paralelo."""
    from services.scheduler import _sync_portal_nfse_company
    from db import get_supabase

    sb = get_supabase()
    company = sb.table("fiscal_companies").select(
        "id,cnpj,sync_nfse_ativo,sync_portal_nfse_ativo,"
        "cert_pfx_encrypted,cert_password_encrypted,"
        "ultimo_nsu_nfse_nacional,portal_nfse_last_sync_at,portal_nfse_hora_sync,"
        "sefaz_nfe_bloqueado_ate,ndd_access_token,ndd_refresh_token"
    ).eq("id", company_id).execute()
    if not company.data:
        return

    row = company.data[0]
    tasks = []

    # NDD
    if row.get("sync_nfse_ativo") and (row.get("ndd_access_token") or row.get("ndd_refresh_token")):
        tasks.append(_sync_ndd_background(company_id))

    # Portal Nacional ADN
    if row.get("sync_portal_nfse_ativo") and row.get("cert_pfx_encrypted"):
        tasks.append(asyncio.to_thread(_sync_portal_nfse_company, row, "manual_all"))

    # Municipal Direto
    tasks.append(_sync_municipalities_background(company_id))

    await asyncio.gather(*tasks, return_exceptions=True)

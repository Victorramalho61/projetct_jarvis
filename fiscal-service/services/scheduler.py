import asyncio
import logging
from datetime import datetime, date, timezone

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None
_portal_syncing: set[str] = set()   # guard: evita sync concorrente por empresa

TZ_BR = pytz.timezone("America/Sao_Paulo")


async def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=TZ_BR)
    _scheduler.add_job(
        _sync_all_companies,
        "cron",
        hour=2,
        minute=0,
        id="sync_principal",
        misfire_grace_time=600,
    )
    _scheduler.add_job(
        _sync_retry_errors,
        "cron",
        hour=4,
        minute=0,
        id="sync_retry",
        misfire_grace_time=600,
    )
    _scheduler.add_job(
        _sync_nfse_ndd_incremental,
        "cron",
        hour=5,
        minute=0,
        id="sync_nfse_ndd",
        misfire_grace_time=600,
    )
    _schedule_portal_nfse_jobs(_scheduler)
    _scheduler.start()
    _logger.info(
        "Scheduler fiscal iniciado: 02:00 (NFe/CTe) + 04:00 (retry) "
        "+ 05:00 (NFSe NDD) + Portal NFS-e no(s) horário(s) configurado(s)"
    )


async def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _logger.info("Scheduler fiscal encerrado")


def _schedule_portal_nfse_jobs(scheduler):
    """Cria um cron job por hora distinta configurada em portal_nfse_hora_sync.
    Roda apenas nas horas das empresas ativas — sem disparos desnecessários.
    Para aplicar mudanças de horário reinicie o serviço."""
    from db import get_supabase
    sb = get_supabase()
    try:
        res = sb.table("fiscal_companies").select("portal_nfse_hora_sync").eq(
            "sync_portal_nfse_ativo", True
        ).execute()
        horas = sorted({
            r["portal_nfse_hora_sync"]
            for r in (res.data or [])
            if r.get("portal_nfse_hora_sync") is not None
        })
    except Exception:
        _logger.warning("Erro ao ler portal_nfse_hora_sync — usando fallback 06:00")
        horas = [6]

    if not horas:
        horas = [6]

    for hora in horas:
        scheduler.add_job(
            _sync_portal_nfse,
            "cron",
            hour=hora,
            minute=0,
            id=f"sync_portal_nfse_{hora:02d}h",
            misfire_grace_time=300,
            replace_existing=True,
        )
        _logger.info("Portal NFS-e agendado: %02d:00 (Brasília)", hora)


async def _sync_all_companies():
    _logger.info("Sync principal 02:00 — buscando empresas ativas")
    from db import get_supabase
    sb = get_supabase()
    try:
        result = sb.table("fiscal_companies").select(
            "id,cnpj,nome,sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,"
            "cert_pfx_encrypted,cert_password_encrypted,ultimo_nsu_nfe,ultimo_nsu_cte,"
            "sefaz_nfe_bloqueado_ate,sefaz_nfe_ultima_consulta_hb,sefaz_usar_svc_an,cert_expiry"
        ).or_("sync_nfe_ativo.eq.true,sync_cte_ativo.eq.true,sync_nfse_ativo.eq.true").execute()
        companies = result.data or []
    except Exception:
        _logger.exception("Erro ao buscar empresas para sync principal")
        return

    _logger.info("Sync principal: %d empresa(s) encontrada(s)", len(companies))
    for company in companies:
        try:
            await _run_sync(company, janela="principal")
        except Exception:
            _logger.exception("Erro no sync principal para CNPJ %s", company.get("cnpj"))


async def _sync_retry_errors():
    _logger.info("Sync retry 04:00 — verificando erros da janela 02:00")
    from db import get_supabase
    sb = get_supabase()

    import pytz as _pytz
    _now_br = __import__('datetime').datetime.now(_pytz.timezone("America/Sao_Paulo"))
    today = _now_br.date().isoformat()
    try:
        # Busca company_ids com erro registrado hoje entre 02:00 e 03:59 BRT
        result = sb.table("fiscal_sync_logs").select("company_id").eq(
            "status", "erro"
        ).eq("janela", "principal").gte(
            "executado_em", f"{today}T02:00:00-03:00"
        ).lt(
            "executado_em", f"{today}T04:00:00-03:00"
        ).execute()
        error_ids = list({r["company_id"] for r in (result.data or [])})
    except Exception:
        _logger.exception("Erro ao consultar logs para retry")
        return

    if not error_ids:
        _logger.info("Nenhum erro na janela das 02:00 — retry cancelado")
        return

    _logger.info("Retry 04:00: %d empresa(s) com erro", len(error_ids))
    companies_result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,"
        "cert_pfx_encrypted,cert_password_encrypted,ultimo_nsu_nfe,ultimo_nsu_cte"
    ).in_("id", error_ids).execute()

    for company in (companies_result.data or []):
        try:
            await _run_sync(company, janela="retry")
        except Exception:
            _logger.exception("Erro no retry para CNPJ %s", company.get("cnpj"))


async def _run_sync(company: dict, janela: str = "manual"):
    from db import get_supabase, get_settings

    sb = get_supabase()
    settings = get_settings()
    company_id = company["id"]
    cnpj = company["cnpj"]

    _logger.info("[%s] Iniciando sync NFe/CTe (%s)", cnpj, janela)

    if company.get("sync_nfe_ativo") and company.get("cert_pfx_encrypted"):
        await _sync_nfe(sb, settings, company, janela)

    if company.get("sync_cte_ativo") and company.get("cert_pfx_encrypted"):
        await _sync_cte(sb, settings, company, janela)

    # NFSe NDD é tratada exclusivamente pelo job das 05:00 (_sync_nfse_ndd_incremental)

    # Alerta cert expirando — usa cert_expiry já carregado no company dict
    expiry_str = company.get("cert_expiry")
    if expiry_str:
        try:
            dias = (date.fromisoformat(expiry_str) - date.today()).days
            if dias < 30:
                _logger.critical(
                    "[%s] CERTIFICADO DIGITAL expira em %d dia(s)! Renove urgente.", cnpj, dias
                )
        except ValueError:
            pass


async def _sync_nfe(sb, settings, company, janela):
    from services.sefaz_nfe_fetcher import NFeDistribuicaoDFe
    from services.xml_parser import parse_xml_auto
    from services.cert_manager import extract_pem_for_requests

    company_id = company["id"]
    cnpj = company["cnpj"]
    ultimo_nsu = company.get("ultimo_nsu_nfe") or 0
    docs_novos = 0
    docs_cancelados = 0

    # Guard cStat 656: pula se ainda dentro do período de bloqueio
    bloqueado_ate = company.get("sefaz_nfe_bloqueado_ate")
    if bloqueado_ate:
        try:
            if datetime.fromisoformat(bloqueado_ate) > datetime.now(timezone.utc):
                _logger.warning("[%s] NFe: bloqueada pela SEFAZ (cStat 656) até %s — sync ignorado",
                                cnpj, bloqueado_ate)
                _log_sync(sb, company_id, "NFe", None, ultimo_nsu, ultimo_nsu,
                          0, 0, "bloqueado", f"cStat 656 — bloqueado até {bloqueado_ate}", janela)
                return
        except ValueError:
            pass

    # Alerta heartbeat: 60 dias sem consultar = perda permanente de documentos
    ultima_hb = company.get("sefaz_nfe_ultima_consulta_hb")
    if ultima_hb:
        try:
            dias = (datetime.now(timezone.utc) - datetime.fromisoformat(ultima_hb)).days
            if dias > 55:
                _logger.error(
                    "[%s] NFe: %d dias sem consulta — NSU em risco de perda permanente (limite: 60d)!",
                    cnpj, dias
                )
        except ValueError:
            pass

    try:
        with extract_pem_for_requests(
            company["cert_pfx_encrypted"],
            company["cert_password_encrypted"],
            settings.cert_encryption_key,
        ) as (cert_path, key_path):
            fetcher = NFeDistribuicaoDFe(
                cnpj, cert_path, key_path,
                settings.sefaz_ambiente,
                usar_svc_an=company.get("sefaz_usar_svc_an", False),
            )
            docs, flags = await asyncio.to_thread(fetcher.dist_dfe_interesse, ultimo_nsu)

        # Prepara campos para UPDATE único no final
        company_update: dict = {}
        if flags.get("bloqueado"):
            company_update["sefaz_nfe_bloqueado_ate"] = flags["bloqueado_ate"]
            _logger.error("[%s] NFe: cStat 656 gravado — bloqueado até %s", cnpj, flags["bloqueado_ate"])
        if flags.get("ultima_consulta"):
            company_update["sefaz_nfe_ultima_consulta_hb"] = flags["ultima_consulta"]

        for doc in docs:
            parsed = parse_xml_auto(doc["xml"])
            if not parsed:
                continue

            is_cancel = doc.get("tipo") == "cancelamento"
            if is_cancel:
                if parsed.get("chave_acesso"):
                    sb.table("fiscal_documents").update(
                        {"status": "cancelado"}
                    ).eq("chave_acesso", parsed["chave_acesso"]).execute()
                docs_cancelados += 1
                continue

            parsed["company_id"]  = company_id
            parsed["fonte"]       = "sefaz"
            parsed["tipo_schema"] = doc.get("tipo_schema", "completo")
            parsed["xml_hash"]    = doc.get("xml_hash")
            parsed["xml_content"] = doc.get("xml", "")
            _ensure_period(sb, company_id, parsed.get("data_emissao"), parsed)
            try:
                sb.table("fiscal_documents").upsert(
                    parsed, on_conflict="chave_acesso"
                ).execute()
                docs_novos += 1
            except Exception as e:
                _logger.warning("[%s] NFe upsert erro: %s", cnpj, e)

            if doc.get("nsu"):
                ultimo_nsu = max(ultimo_nsu, int(doc["nsu"]))

        # 1 único UPDATE: NSU + heartbeat + bloqueio (se aplicável)
        company_update["ultimo_nsu_nfe"] = ultimo_nsu
        sb.table("fiscal_companies").update(company_update).eq("id", company_id).execute()

        _log_sync(sb, company_id, "NFe", None, company.get("ultimo_nsu_nfe"), ultimo_nsu,
                  docs_novos, docs_cancelados, "ok", None, janela)
        _logger.info("[%s] NFe sync OK: +%d docs, %d cancelados", cnpj, docs_novos, docs_cancelados)

    except Exception as e:
        _log_sync(sb, company_id, "NFe", None, ultimo_nsu, ultimo_nsu,
                  0, 0, "erro", str(e), janela)
        _logger.error("[%s] NFe sync ERRO: %s", cnpj, e)
        raise


async def _sync_cte(sb, settings, company, janela):
    from services.sefaz_cte_fetcher import CTeDistribuicaoDFe
    from services.xml_parser import parse_xml_auto
    from services.cert_manager import extract_pem_for_requests

    company_id = company["id"]
    cnpj = company["cnpj"]
    ultimo_nsu = company.get("ultimo_nsu_cte") or 0
    docs_novos = 0

    try:
        with extract_pem_for_requests(
            company["cert_pfx_encrypted"],
            company["cert_password_encrypted"],
            settings.cert_encryption_key,
        ) as (cert_path, key_path):
            fetcher = CTeDistribuicaoDFe(cnpj, cert_path, key_path, settings.sefaz_ambiente)
            docs = await asyncio.to_thread(fetcher.dist_dfe_interesse, ultimo_nsu)

        for doc in docs:
            parsed = parse_xml_auto(doc["xml"])
            if not parsed:
                continue
            parsed["company_id"] = company_id
            _ensure_period(sb, company_id, parsed.get("data_emissao"), parsed)
            try:
                sb.table("fiscal_documents").upsert(
                    parsed, on_conflict="chave_acesso"
                ).execute()
                docs_novos += 1
            except Exception as e:
                _logger.warning("[%s] CTe upsert erro: %s", cnpj, e)
            if doc.get("nsu"):
                ultimo_nsu = max(ultimo_nsu, int(doc["nsu"]))

        sb.table("fiscal_companies").update({"ultimo_nsu_cte": ultimo_nsu}).eq(
            "id", company_id
        ).execute()
        _log_sync(sb, company_id, "CTe", None, company.get("ultimo_nsu_cte"), ultimo_nsu,
                  docs_novos, 0, "ok", None, janela)
        _logger.info("[%s] CTe sync OK: +%d docs", cnpj, docs_novos)

    except Exception as e:
        _log_sync(sb, company_id, "CTe", None, ultimo_nsu, ultimo_nsu, 0, 0, "erro", str(e), janela)
        _logger.error("[%s] CTe sync ERRO: %s", cnpj, e)
        raise


async def _sync_nfse(sb, settings, company, janela):
    """
    NFSe via NDD Digital portal — uma chamada busca XMLs de TODAS as empresas
    visíveis na conta. Os documentos são associados às empresas pelo CNPJ do tomador.
    """
    from services.ndd_xml_fetcher import fetch_all_xml
    from services.nfse_fetcher import _get_ndd_token
    from services.xml_parser import parse_xml_auto

    company_id = company["id"]
    cnpj = company["cnpj"]

    # Obtém token NDD — armazenado na empresa (conta do portal cobre todas as empresas)
    try:
        token = _get_ndd_token(company_id)
    except RuntimeError as e:
        _logger.warning("[%s] NFSe NDD: %s", cnpj, e)
        _log_sync(sb, company_id, "NFSe", None, None, None, 0, 0, "erro", str(e), janela)
        return

    hoje = date.today()
    data_inicio = hoje.replace(day=1)  # mês corrente

    # Mapa CNPJ → company_id para associar notas às empresas certas
    all_companies = sb.table("fiscal_companies").select("id,cnpj").execute()
    cnpj_map = {r["cnpj"]: r["id"] for r in (all_companies.data or [])}

    docs_por_empresa: dict[str, int] = {}
    erros = 0

    try:
        for nota in fetch_all_xml(token, data_inicio, hoje):
            cnpj_tom = nota["cnpj_tomador"]
            target_company_id = cnpj_map.get(cnpj_tom, company_id)

            doc = {
                "tipo": "NFSe",
                "company_id": target_company_id,
                "chave_acesso": nota["chave_acesso"],
                "emitente_cnpj": nota["cnpj_prestador"],
                "destinatario_cnpj": cnpj_tom,
                "data_emissao": nota["data_emissao"],
                "valor_total": nota["valor_total"],
                "xml_content": nota["xml"],
                "status": "pendente",
            }
            _ensure_period(sb, target_company_id, nota["data_emissao"], doc)

            try:
                sb.table("fiscal_documents").upsert(
                    doc, on_conflict="chave_acesso"
                ).execute()
                docs_por_empresa[cnpj_tom] = docs_por_empresa.get(cnpj_tom, 0) + 1
            except Exception as e:
                _logger.warning("NFSe NDD upsert erro (chave %s): %s", nota["chave_acesso"], e)
                erros += 1

        total = sum(docs_por_empresa.values())
        resumo = ", ".join(f"{c[-4:]}:{n}" for c, n in docs_por_empresa.items())
        _logger.info("[%s] NFSe NDD OK: %d notas (%s)", cnpj, total, resumo)
        _log_sync(sb, company_id, "NFSe", None, None, None, total, 0,
                  "ok" if erros == 0 else "parcial", None, janela)

    except Exception as e:
        _log_sync(sb, company_id, "NFSe", None, None, None, 0, 0, "erro", str(e), janela)
        _logger.error("[%s] NFSe NDD ERRO: %s", cnpj, e)
        raise


async def _sync_nfse_ndd_incremental():
    """05:00 — busca NFSe NDD incrementalmente usando ndd_last_sync_at como watermark."""
    from db import get_supabase, get_settings
    from services.nfse_fetcher import _get_ndd_token
    from services.ndd_xml_fetcher import fetch_all_xml

    _logger.info("NFSe NDD 05:00 — iniciando sync incremental")
    sb = get_supabase()

    result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,sync_nfse_ativo,ndd_access_token,ndd_refresh_token,"
        "ndd_token_expires_at,ndd_last_sync_at"
    ).eq("sync_nfse_ativo", True).execute()
    companies = result.data or []

    token_company = None
    for c in companies:
        if c.get("ndd_access_token") or c.get("ndd_refresh_token"):
            token_company = c
            break

    if not token_company:
        _logger.warning("NFSe NDD 05:00: nenhuma empresa com token NDD configurado")
        return

    try:
        token = _get_ndd_token(token_company["id"])
    except RuntimeError as e:
        _logger.error("NFSe NDD 05:00: token inválido — %s", e)
        _log_sync(sb, token_company["id"], "NFSe", None, None, None, 0, 0, "erro", str(e), "ndd_05h")
        return

    last_sync_str = token_company.get("ndd_last_sync_at")
    since_dt = datetime.fromisoformat(last_sync_str) if last_sync_str else None
    hoje = date.today()
    data_inicio = since_dt.date() if since_dt else hoje.replace(day=1)

    all_co = sb.table("fiscal_companies").select("id,cnpj").execute()
    cnpj_map = {r["cnpj"]: r["id"] for r in (all_co.data or [])}

    sync_start = datetime.now(timezone.utc)
    docs_total = 0
    erros = 0

    try:
        for nota in fetch_all_xml(token, data_inicio, hoje, since_dt=since_dt):
            cnpj_tom = nota["cnpj_tomador"]
            target_id = cnpj_map.get(cnpj_tom, token_company["id"])

            doc = {
                "tipo": "NFSe",
                "company_id": target_id,
                "chave_acesso": nota["chave_acesso"],
                "numero": nota.get("numero"),
                "serie": nota.get("serie"),
                "emitente_cnpj": nota["cnpj_prestador"],
                "emitente_nome": nota.get("nome_prestador"),
                "destinatario_cnpj": cnpj_tom,
                "destinatario_nome": nota.get("nome_tomador"),
                "data_emissao": nota["data_emissao"],
                "valor_total": nota["valor_total"],
                "valor_iss": nota.get("valor_iss"),
                "valor_iss_retido": nota.get("valor_iss_retido"),
                "municipio_nome": nota["municipio_nome"],
                "xml_content": nota["xml"],
                "status": "pendente",
                "ndd_id": nota["ndd_id"],
                "ndd_sync_at": sync_start.isoformat(),
            }
            _ensure_period(sb, target_id, nota["data_emissao"], doc)

            try:
                sb.table("fiscal_documents").upsert(
                    doc, on_conflict="chave_acesso"
                ).execute()
                docs_total += 1
            except Exception as e:
                _logger.warning("NFSe upsert erro (chave %s): %s", nota["chave_acesso"], e)
                erros += 1

        sb.table("fiscal_companies").update(
            {"ndd_last_sync_at": sync_start.isoformat()}
        ).eq("id", token_company["id"]).execute()

        status = "ok" if erros == 0 else "parcial"
        _log_sync(sb, token_company["id"], "NFSe", None, None, None,
                  docs_total, 0, status, None, "ndd_05h")
        _logger.info("NFSe NDD 05:00 OK: %d docs, %d erros", docs_total, erros)

    except Exception as e:
        _log_sync(sb, token_company["id"], "NFSe", None, None, None,
                  0, 0, "erro", str(e), "ndd_05h")
        _logger.error("NFSe NDD 05:00 ERRO: %s", e)


def sync_ndd_for_company(company_id: str, janela: str = "manual") -> dict:
    """Sync NDD incremental para uma empresa específica. Retorna {docs_total, erros, status}."""
    from db import get_supabase
    from services.nfse_fetcher import _get_ndd_token
    from services.ndd_xml_fetcher import fetch_all_xml

    sb = get_supabase()
    result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,ndd_access_token,ndd_refresh_token,ndd_token_expires_at,ndd_last_sync_at"
    ).eq("id", company_id).execute()
    if not result.data:
        raise ValueError(f"Empresa {company_id} não encontrada")

    company = result.data[0]
    cnpj = company["cnpj"]

    try:
        token = _get_ndd_token(company_id)
    except RuntimeError as e:
        _log_sync(sb, company_id, "NFSe", None, None, None, 0, 0, "erro", str(e), janela)
        raise

    last_sync_str = company.get("ndd_last_sync_at")
    since_dt = datetime.fromisoformat(last_sync_str) if last_sync_str else None
    hoje = date.today()
    data_inicio = since_dt.date() if since_dt else hoje.replace(day=1)

    all_co = sb.table("fiscal_companies").select("id,cnpj").execute()
    cnpj_map = {r["cnpj"]: r["id"] for r in (all_co.data or [])}

    sync_start = datetime.now(timezone.utc)
    docs_total = 0
    erros = 0

    try:
        for nota in fetch_all_xml(token, data_inicio, hoje, since_dt=since_dt):
            cnpj_tom = nota["cnpj_tomador"]
            target_id = cnpj_map.get(cnpj_tom, company_id)
            doc = {
                "tipo": "NFSe",
                "company_id": target_id,
                "chave_acesso": nota["chave_acesso"],
                "numero": nota.get("numero"),
                "serie": nota.get("serie"),
                "emitente_cnpj": nota["cnpj_prestador"],
                "emitente_nome": nota.get("nome_prestador"),
                "destinatario_cnpj": cnpj_tom,
                "destinatario_nome": nota.get("nome_tomador"),
                "data_emissao": nota["data_emissao"],
                "valor_total": nota["valor_total"],
                "valor_iss": nota.get("valor_iss"),
                "valor_iss_retido": nota.get("valor_iss_retido"),
                "municipio_nome": nota["municipio_nome"],
                "xml_content": nota["xml"],
                "status": "pendente",
                "ndd_id": nota["ndd_id"],
                "ndd_sync_at": sync_start.isoformat(),
            }
            _ensure_period(sb, target_id, nota["data_emissao"], doc)
            try:
                sb.table("fiscal_documents").upsert(doc, on_conflict="chave_acesso").execute()
                docs_total += 1
            except Exception as e:
                _logger.warning("NFSe NDD upsert (chave %s): %s", nota["chave_acesso"], e)
                erros += 1

        sb.table("fiscal_companies").update(
            {"ndd_last_sync_at": sync_start.isoformat()}
        ).eq("id", company_id).execute()

        status = "ok" if erros == 0 else "parcial"
        _log_sync(sb, company_id, "NFSe", None, None, None, docs_total, 0, status, None, janela)
        _logger.info("[%s] NDD manual OK: %d docs, %d erros", cnpj, docs_total, erros)
        return {"docs_total": docs_total, "erros": erros, "status": status}

    except Exception as e:
        _log_sync(sb, company_id, "NFSe", None, None, None, 0, 0, "erro", str(e), janela)
        _logger.error("[%s] NDD manual ERRO: %s", cnpj, e)
        raise


async def _sync_portal_nfse():
    """Portal Nacional NFS-e (ADN) — dispara no horário configurado por empresa (portal_nfse_hora_sync)."""
    from db import get_supabase, get_settings

    hora_atual = datetime.now(TZ_BR).hour
    _logger.info("Portal Nacional NFS-e %02d:00 — iniciando sync", hora_atual)
    sb = get_supabase()

    result = sb.table("fiscal_companies").select(
        "id,cnpj,nome,sync_portal_nfse_ativo,cert_pfx_encrypted,cert_password_encrypted,"
        "ultimo_nsu_nfse_nacional,portal_nfse_last_sync_at,portal_nfse_hora_sync"
    ).eq("sync_portal_nfse_ativo", True).eq("portal_nfse_hora_sync", hora_atual).execute()
    companies = result.data or []

    _logger.info("Portal Nacional NFS-e %02d:00: %d empresa(s)", hora_atual, len(companies))
    for company in companies:
        try:
            await asyncio.to_thread(_sync_portal_nfse_company, company, f"portal_{hora_atual:02d}h")
        except Exception:
            _logger.exception("Erro no sync Portal NFS-e para CNPJ %s", company.get("cnpj"))


def _sync_portal_nfse_company(company: dict, janela: str = "manual"):
    """Sync Portal Nacional NFS-e (ADN) para uma empresa.
    Função SÍNCRONA: Starlette/BackgroundTasks coloca em thread pool automaticamente.
    O APScheduler chama via asyncio.to_thread para não bloquear o event loop.
    """
    from db import get_supabase, get_settings
    from services.portal_nfse_fetcher import PortalNFSeFetcher
    from services.xml_parser import parse_nfse_portal, _compute_hash
    from services.cert_manager import extract_pem_for_requests

    company_id = company["id"]
    cnpj       = company["cnpj"]

    # Guard: evita sync concorrente para a mesma empresa (double-click, scheduler+manual)
    if company_id in _portal_syncing:
        _logger.info("[%s] Portal NFS-e: sync já em andamento — ignorando chamada duplicada", cnpj)
        return
    _portal_syncing.add(company_id)

    sb       = get_supabase()
    settings = get_settings()
    ultimo_nsu = company.get("ultimo_nsu_nfse_nacional") or 0
    docs_novos = 0
    docs_cancelados = 0

    if not company.get("cert_pfx_encrypted") or not company.get("cert_password_encrypted"):
        motivo = "Sem certificado digital" if not company.get("cert_pfx_encrypted") else "Sem senha do certificado"
        _logger.warning("[%s] Portal NFS-e: %s — sync ignorado", cnpj, motivo)
        _log_sync(sb, company_id, "NFSe_Portal", None, ultimo_nsu, ultimo_nsu,
                  0, 0, "erro", motivo, janela)
        _portal_syncing.discard(company_id)
        return

    try:
        with extract_pem_for_requests(
            company["cert_pfx_encrypted"],
            company["cert_password_encrypted"],
            settings.cert_encryption_key,
        ) as (cert_path, key_path):
            fetcher = PortalNFSeFetcher(
                cnpj, cert_path, key_path,
                getattr(settings, "portal_nfse_ambiente", "1"),
            )

            # Incremental: processa e salva cada página ADN (~50 docs) imediatamente.
            # Evita acumular 100k docs em RAM e torna o sync resumível por NSU.
            nsu_maximo     = ultimo_nsu
            periods_seen: set = set()

            for page_docs, nsu_pagina in fetcher.iter_dfe_interesse(ultimo_nsu):
                nsu_maximo = max(nsu_maximo, nsu_pagina)

                cancelamentos = [d for d in page_docs if d.get("tipo") == "cancelamento"]
                novos_raw     = [d for d in page_docs if d.get("tipo") != "cancelamento"]

                for doc in cancelamentos:
                    parsed = parse_nfse_portal(doc["xml"]) if doc.get("xml") else None
                    if parsed and parsed.get("chave_acesso"):
                        sb.table("fiscal_documents").update(
                            {"status": "cancelado"}
                        ).eq("chave_acesso", parsed["chave_acesso"]).execute()
                    docs_cancelados += 1

                # Filtro de data: só salva NFS-e com emissão >= 2026-01-01
                DATA_INICIO_PORTAL = date(2026, 1, 1)

                parsed_page: list[dict] = []
                for doc in novos_raw:
                    parsed = parse_nfse_portal(doc["xml"]) if doc.get("xml") else None
                    if not parsed:
                        continue
                    emissao_str = parsed.get("data_emissao") or ""
                    if emissao_str:
                        try:
                            if date.fromisoformat(emissao_str[:10]) < DATA_INICIO_PORTAL:
                                continue  # ignora docs antigos — só salva a partir de 2026
                        except ValueError:
                            pass
                    parsed.update({
                        "company_id":   company_id,
                        "fonte":        "portal_nacional",
                        "nsu_nacional": doc.get("nsu"),
                        "tipo_schema":  doc.get("tipo_schema", "completo"),
                        "xml_hash":     doc.get("xml_hash") or _compute_hash(doc.get("xml", "")),
                        "xml_content":  doc.get("xml", ""),
                    })
                    # chave_acesso da API ADN é autoritativa — usa como fallback se parser não extraiu
                    if not parsed.get("chave_acesso") and doc.get("chave_acesso"):
                        parsed["chave_acesso"] = doc["chave_acesso"]
                    parsed.pop("_items", None)  # campo interno do parser, não existe na tabela
                    emissao = parsed.get("data_emissao")
                    if emissao:
                        try:
                            from datetime import date as _date
                            d = _date.fromisoformat(str(emissao)[:10])
                            pk = (company_id, d.year, d.month)
                            if pk not in periods_seen:
                                periods_seen.add(pk)
                                _ensure_period(sb, company_id, emissao, parsed)
                        except ValueError:
                            pass
                    parsed_page.append(parsed)

                if parsed_page:
                    try:
                        sb.table("fiscal_documents").upsert(
                            parsed_page, on_conflict="chave_acesso"
                        ).execute()
                        docs_novos += len(parsed_page)
                    except Exception as exc:
                        _logger.warning("[%s] Portal NFS-e batch upsert erro: %s", cnpj, exc)
                        for pdoc in parsed_page:
                            try:
                                sb.table("fiscal_documents").upsert(pdoc, on_conflict="chave_acesso").execute()
                                docs_novos += 1
                            except Exception as exc2:
                                _logger.warning("[%s] Portal NFS-e upsert individual erro: %s", cnpj, exc2)

                # Salva NSU após cada página — sync é resumível se interrompido
                sb.table("fiscal_companies").update({
                    "ultimo_nsu_nfse_nacional": nsu_maximo,
                }).eq("id", company_id).execute()

        # Atualiza timestamp do último sync completo
        sb.table("fiscal_companies").update({
            "portal_nfse_last_sync_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", company_id).execute()

        _log_sync(sb, company_id, "NFSe_Portal", None,
                  company.get("ultimo_nsu_nfse_nacional"), nsu_maximo,
                  docs_novos, docs_cancelados, "ok", None, janela)
        _logger.info("[%s] Portal NFS-e OK: +%d docs, %d cancelados (NSU %d→%d)",
                     cnpj, docs_novos, docs_cancelados, ultimo_nsu, nsu_maximo)

    except Exception as exc:
        _log_sync(sb, company_id, "NFSe_Portal", None, ultimo_nsu, ultimo_nsu,
                  0, 0, "erro", str(exc), janela)
        _logger.error("[%s] Portal NFS-e ERRO: %s", cnpj, exc)
        raise
    finally:
        _portal_syncing.discard(company_id)


def _ensure_period(sb, company_id: str, data_emissao, doc: dict):
    if not data_emissao:
        return
    try:
        d = date.fromisoformat(str(data_emissao))
        result = sb.table("fiscal_periods").upsert({
            "company_id": company_id,
            "ano": d.year,
            "mes": d.month,
            "status": "aberto",
        }, on_conflict="company_id,ano,mes").execute()
        if result.data:
            doc["period_id"] = result.data[0]["id"]
    except Exception:
        _logger.exception("_ensure_period falhou company=%s data=%s — period_id não definido", company_id, data_emissao)


def _log_sync(sb, company_id, tipo, ibge, nsu_ini, nsu_fin, novos, cancelados, status, erro, janela):
    try:
        sb.table("fiscal_sync_logs").insert({
            "company_id": company_id,
            "tipo": tipo,
            "municipio_ibge": ibge,
            "nsu_inicial": nsu_ini,
            "nsu_final": nsu_fin,
            "documentos_novos": novos,
            "documentos_cancelados": cancelados,
            "status": status,
            "erro_msg": erro,
            "janela": janela,
        }).execute()
    except Exception:
        _logger.warning("Falha ao gravar sync_log")

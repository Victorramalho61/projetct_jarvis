import asyncio
import logging
from datetime import datetime, date, timezone

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None

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
    _scheduler.start()
    _logger.info("Scheduler fiscal iniciado: 02:00 (NFe/CTe) + 04:00 (retry) + 05:00 (NFSe NDD incremental)")


async def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _logger.info("Scheduler fiscal encerrado")


async def _sync_all_companies():
    _logger.info("Sync principal 02:00 — buscando empresas ativas")
    from db import get_supabase
    sb = get_supabase()
    try:
        result = sb.table("fiscal_companies").select(
            "id,cnpj,nome,sync_nfe_ativo,sync_cte_ativo,sync_nfse_ativo,"
            "cert_pfx_encrypted,cert_password_encrypted,ultimo_nsu_nfe,ultimo_nsu_cte"
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

    today = date.today().isoformat()
    try:
        # Busca company_ids com erro registrado hoje entre 02:00 e 03:59
        result = sb.table("fiscal_sync_logs").select("company_id").eq(
            "status", "erro"
        ).eq("janela", "principal").gte(
            "executado_em", f"{today}T02:00:00"
        ).lt(
            "executado_em", f"{today}T04:00:00"
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

    # Alerta cert expirando
    cert_expiry_res = sb.table("fiscal_companies").select("cert_expiry").eq(
        "id", company_id
    ).execute()
    if cert_expiry_res.data:
        expiry_str = cert_expiry_res.data[0].get("cert_expiry")
        if expiry_str:
            dias = (date.fromisoformat(expiry_str) - date.today()).days
            if dias < 30:
                _logger.critical(
                    "[%s] CERTIFICADO DIGITAL expira em %d dia(s)! Renove urgente.", cnpj, dias
                )


async def _sync_nfe(sb, settings, company, janela):
    from services.sefaz_nfe_fetcher import NFeDistribuicaoDFe
    from services.xml_parser import parse_xml_auto
    from services.cert_manager import extract_pem_for_requests

    company_id = company["id"]
    cnpj = company["cnpj"]
    ultimo_nsu = company.get("ultimo_nsu_nfe") or 0
    docs_novos = 0
    docs_cancelados = 0

    try:
        with extract_pem_for_requests(
            company["cert_pfx_encrypted"],
            company["cert_password_encrypted"],
            settings.cert_encryption_key,
        ) as (cert_path, key_path):
            fetcher = NFeDistribuicaoDFe(cnpj, cert_path, key_path, settings.sefaz_ambiente)
            docs = fetcher.dist_dfe_interesse(ultimo_nsu)

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

            parsed["company_id"] = company_id
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

        sb.table("fiscal_companies").update({"ultimo_nsu_nfe": ultimo_nsu}).eq(
            "id", company_id
        ).execute()

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
            docs = fetcher.dist_dfe_interesse(ultimo_nsu)

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
                "emitente_cnpj": nota["cnpj_prestador"],
                "destinatario_cnpj": cnpj_tom,
                "data_emissao": nota["data_emissao"],
                "valor_total": nota["valor_total"],
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
        pass


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

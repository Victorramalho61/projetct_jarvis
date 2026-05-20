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
    _scheduler.start()
    _logger.info("Scheduler fiscal iniciado: 02:00 (principal) + 04:00 (retry on error)")


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
    from services.cert_manager import extract_pem_for_requests
    from services.nfse_fetcher import NFSeFetcher
    from services.xml_parser import parse_xml_auto

    sb = get_supabase()
    settings = get_settings()
    company_id = company["id"]
    cnpj = company["cnpj"]

    _logger.info("[%s] Iniciando sync (%s)", cnpj, janela)

    if company.get("sync_nfe_ativo") and company.get("cert_pfx_encrypted"):
        await _sync_nfe(sb, settings, company, janela)

    if company.get("sync_cte_ativo") and company.get("cert_pfx_encrypted"):
        await _sync_cte(sb, settings, company, janela)

    if company.get("sync_nfse_ativo"):
        await _sync_nfse(sb, settings, company, janela)

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
    from services.nfse_fetcher import NFSeFetcher
    from services.xml_parser import parse_xml_auto
    from services.cert_manager import extract_pem_for_requests
    from datetime import timedelta

    company_id = company["id"]
    cnpj = company["cnpj"]

    mun_result = sb.table("fiscal_nfse_municipalities").select(
        "municipio_ibge,municipio_nome,uf,sistema_tipo,status"
    ).eq("company_id", company_id).eq("ativo", True).execute()

    municipios = mun_result.data or []
    if not municipios:
        _logger.info("[%s] NFSe: nenhum município ativo", cnpj)
        return

    cert_path_ctx = None
    if company.get("cert_pfx_encrypted") and settings.cert_encryption_key:
        cert_path_ctx = extract_pem_for_requests(
            company["cert_pfx_encrypted"],
            company["cert_password_encrypted"],
            settings.cert_encryption_key,
        )

    hoje = date.today()
    data_inicio = hoje.replace(day=1)

    for mun in municipios:
        ibge = mun["municipio_ibge"]
        if mun["status"] == "pendente":
            _logger.warning(
                "[%s] NFSe %s/%s: necessário realizar cadastro como contribuinte "
                "no portal da prefeitura (IBGE: %s) para habilitar o sync.",
                cnpj, mun["municipio_nome"], mun["uf"], ibge,
            )
            continue

        docs_novos = 0
        try:
            if cert_path_ctx:
                with cert_path_ctx as (cert_path, key_path):
                    fetcher = NFSeFetcher(cnpj, cert_path, key_path)
                    docs = fetcher.fetch_municipio(ibge, data_inicio, hoje)
            else:
                fetcher = NFSeFetcher(cnpj, None, None)
                docs = fetcher.fetch_municipio(ibge, data_inicio, hoje)

            for doc in docs:
                doc["company_id"] = company_id
                doc["municipio_ibge"] = ibge
                _ensure_period(sb, company_id, doc.get("data_emissao"), doc)
                try:
                    sb.table("fiscal_documents").upsert(
                        doc, on_conflict="chave_acesso"
                    ).execute()
                    docs_novos += 1
                except Exception as e:
                    _logger.warning("[%s] NFSe upsert erro (%s): %s", cnpj, ibge, e)

            sb.table("fiscal_nfse_municipalities").update(
                {"ultima_sync": datetime.now(timezone.utc).isoformat(), "status": "cadastrado"}
            ).eq("company_id", company_id).eq("municipio_ibge", ibge).execute()

            _log_sync(sb, company_id, "NFSe", ibge, None, None, docs_novos, 0, "ok", None, janela)
            _logger.info("[%s] NFSe %s OK: +%d docs", cnpj, ibge, docs_novos)

        except Exception as e:
            sb.table("fiscal_nfse_municipalities").update(
                {"status": "erro"}
            ).eq("company_id", company_id).eq("municipio_ibge", ibge).execute()
            _log_sync(sb, company_id, "NFSe", ibge, None, None, 0, 0, "erro", str(e), janela)
            _logger.error("[%s] NFSe %s ERRO: %s", cnpj, ibge, e)


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

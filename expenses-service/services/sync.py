import logging
from datetime import datetime, timezone

from db import get_supabase
from services.expenses import fetch_dashboard
from services.forecast import fetch_forecast

logger = logging.getLogger(__name__)

_YEARS = [2025, 2026]


def run_expenses_sync() -> str:
    """Pré-computa dashboard, forecast e KPIs de governança e persiste no Supabase."""
    db = get_supabase()
    total_parcelas = 0
    errors: list[str] = []

    for year in _YEARS:
        try:
            data = fetch_dashboard(year)
            total_parcelas += data["kpis"].get("count_parcelas", 0)
            _upsert(db, year, f"dashboard_{year}", data)
            logger.info("Cache dashboard %d salvo (%d parcelas)", year, data["kpis"].get("count_parcelas", 0))
        except Exception as exc:
            errors.append(f"dashboard_{year}: {exc}")
            logger.exception("Erro ao sincronizar dashboard %d", year)

    try:
        fc = fetch_forecast(2026)
        _upsert(db, 2026, "forecast_2026", fc)
        logger.info("Cache forecast 2026 salvo")
    except Exception as exc:
        errors.append(f"forecast_2026: {exc}")
        logger.exception("Erro ao sincronizar forecast 2026")

    try:
        from services.governance import get_governance_kpis
        gov = get_governance_kpis()
        _upsert(db, 2026, "governance_dashboard", gov)
        logger.info("Cache governance_dashboard salvo (%d contratos)", gov.get("total_contratos", 0))
    except Exception as exc:
        errors.append(f"governance_dashboard: {exc}")
        logger.exception("Erro ao sincronizar governance_dashboard")

    if errors:
        raise RuntimeError("; ".join(errors))

    return f"Sync concluído: {total_parcelas} parcelas, {len(_YEARS)} anos"


def _upsert(db, year: int, cache_key: str, payload: dict) -> None:
    db.table("expenses_cache").upsert(
        {
            "year": year,
            "cache_key": cache_key,
            "payload": payload,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "error_msg": None,
        },
        on_conflict="year,cache_key",
    ).execute()


def get_last_updated() -> str | None:
    """Retorna ISO timestamp da última sincronização bem-sucedida."""
    try:
        res = (
            get_supabase()
            .table("expenses_cache")
            .select("updated_at")
            .eq("status", "success")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["updated_at"]
    except Exception:
        logger.warning("Não foi possível obter last_updated do cache", exc_info=True)
    return None


def get_cached_dashboard(year: int) -> dict | None:
    """Lê dashboard do cache Supabase. Retorna None se não encontrar ou cache inválido."""
    try:
        res = (
            get_supabase()
            .table("expenses_cache")
            .select("payload, updated_at")
            .eq("cache_key", f"dashboard_{year}")
            .eq("status", "success")
            .limit(1)
            .execute()
        )
        if res.data:
            payload = res.data[0]["payload"]
            payload["last_updated"] = res.data[0]["updated_at"]
            return payload
    except Exception:
        logger.warning("Erro ao ler cache dashboard_%d", year, exc_info=True)
    return None


def get_cached_forecast(year: int) -> dict | None:
    """Lê forecast do cache Supabase. Retorna None se não encontrar."""
    try:
        res = (
            get_supabase()
            .table("expenses_cache")
            .select("payload")
            .eq("cache_key", f"forecast_{year}")
            .eq("status", "success")
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["payload"]
    except Exception:
        logger.warning("Erro ao ler cache forecast_%d", year, exc_info=True)
    return None


def get_cached_governance_dashboard() -> dict | None:
    """Lê KPIs de governança do cache Supabase."""
    try:
        res = (
            get_supabase()
            .table("expenses_cache")
            .select("payload, updated_at")
            .eq("cache_key", "governance_dashboard")
            .eq("status", "success")
            .limit(1)
            .execute()
        )
        if res.data:
            payload = res.data[0]["payload"]
            payload["last_updated"] = res.data[0]["updated_at"]
            return payload
    except Exception:
        logger.warning("Erro ao ler cache governance_dashboard", exc_info=True)
    return None

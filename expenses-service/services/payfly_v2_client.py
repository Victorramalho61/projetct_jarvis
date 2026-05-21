"""
PayFly API V2 client — token cache, parallel fetches, Supabase upsert.
Estrutura real dos dados baseada nos exemplos do Postman (18 mai 2026).
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

PAGE_WORKERS = 5

# ── Token cache (thread-safe) ─────────────────────────────────────────────────

_token_lock  = threading.Lock()
_token_value: Optional[str] = None
_token_exp:   float = 0.0


def _get_token() -> str:
    global _token_value, _token_exp
    with _token_lock:
        from db import get_settings
        s = get_settings()
        # Bearer token estático (prioridade)
        if s.payfly_v2_bearer_token:
            return s.payfly_v2_bearer_token
        # Renovar via clientId/clientSecret
        if _token_value and time.time() < _token_exp - 120:
            return _token_value
        resp = requests.post(
            f"{s.payfly_v2_url}/api/v2/auth/token",
            json={"clientId": s.payfly_v2_client_id, "clientSecret": s.payfly_v2_client_secret},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        # Estrutura real: {"success": true, "data": {"accessToken": "...", "expiresIn": 86400}}
        data = body.get("data") or body
        token = data.get("accessToken") or data.get("access_token") or data.get("token")
        if not token:
            raise ValueError(f"Token não encontrado na resposta: {list(data.keys())}")
        expires_in = data.get("expiresIn") or data.get("expires_in") or 86400
        _token_value = token
        _token_exp   = time.time() + expires_in
        return _token_value


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/json"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_dt(d: date) -> str:
    """Formato esperado pela API: 'YYYY-MM-DD HH:MM:SS'"""
    return f"{d.isoformat()} 00:00:00"


def _fmt_dt_end(d: date) -> str:
    return f"{d.isoformat()} 23:59:59"


def _ts(val) -> Optional[str]:
    if not val:
        return None
    return str(val)


# ── API calls ─────────────────────────────────────────────────────────────────

def get_reservation_ids(start_date: date, end_date: date) -> dict:
    from db import get_settings
    s = get_settings()
    resp = requests.post(
        f"{s.payfly_v2_url}/api/v2/reservations/ids",
        json={
            "startDate": _fmt_dt(start_date),
            "endDate":   _fmt_dt_end(end_date),
        },
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    # Estrutura real: {"success": true, "data": {"emitidos": [...], "cancelados": [...], ...}}
    return body.get("data") or body


def get_reservation_detail(res_id: str, res_type: str) -> Optional[dict]:
    from db import get_settings
    s = get_settings()
    try:
        resp = requests.post(
            f"{s.payfly_v2_url}/api/v2/reservations/by-id",
            json={"id": res_id, "type": res_type},
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data") or body
    except Exception as exc:
        logger.warning("get_reservation_detail %s/%s: %s", res_id, res_type, exc)
        return None


# ── Flatten (baseado na estrutura real do Postman) ────────────────────────────

def _flatten(raw: dict) -> dict:
    dates   = raw.get("dates")   or {}
    people  = raw.get("people")  or {}
    company = raw.get("company") or {}
    pricing = raw.get("pricing") or {}
    corp    = raw.get("corporate_fields") or {}
    hotel   = raw.get("hotel_data") or {}
    flight  = raw.get("flight_data") or {}

    pax   = people.get("passenger") or {}
    appr  = people.get("approver")  or {}
    soli  = people.get("solicitor") or {}

    stay  = hotel.get("stay_info")  or {}
    hinfo = hotel.get("hotel_info") or {}
    room  = hotel.get("room_info")  or {}

    # Voo: estrutura esperada (adaptar se necessário quando tivermos exemplo real)
    fseg  = (flight.get("segments") or [{}])[0] if flight else {}

    return {
        # Identificação
        "id":                        raw.get("id"),
        "type":                      raw.get("type"),
        "status":                    raw.get("status"),
        "os_number":                 raw.get("os_number"),
        "trip_type":                 raw.get("trip_type"),
        "is_reissue":                raw.get("is_reissue"),
        "original_id":               raw.get("original_id"),
        "order_origin":              raw.get("order_origin"),
        # Datas
        "choice_date":               _ts(dates.get("choice_date")),
        "emission_date":             _ts(dates.get("emission_date")),
        "travel_start_date":         _ts(dates.get("travel_start_date")),
        "travel_end_date":           _ts(dates.get("travel_end_date")),
        "approval_date":             _ts(dates.get("cost_approval_date")),
        "cancellation_date":         _ts(dates.get("cancellation_date")),
        "expiration_date":           _ts(dates.get("expiration_date")),
        "last_update_date":          _ts(dates.get("last_update_date")),
        "request_date":              _ts(dates.get("solicitation_date")),
        # Empresa
        "company_id":                company.get("id"),
        "company_cnpj":              company.get("cnpj"),
        "company_name":              company.get("name"),
        # Passageiro
        "passenger_name":            pax.get("full_name"),
        "passenger_email":           pax.get("email"),
        "passenger_document":        pax.get("document"),
        "passenger_employee_id":     pax.get("employee_id"),
        "passenger_department_name": pax.get("department_name"),
        "passenger_age_group":       pax.get("age_group"),
        "passenger_employee_level":  pax.get("employee_level"),
        # Aprovador / Solicitante
        "approver_name":             appr.get("full_name"),
        "approver_email":            appr.get("email"),
        "solicitor_name":            soli.get("full_name"),
        "solicitor_email":           soli.get("email"),
        # Financeiro
        "currency":                  pricing.get("currency"),
        "total_amount":              pricing.get("total_amount"),
        "daily_rate":                pricing.get("daily_rate"),
        "total_nights":              pricing.get("total_nights"),
        "base_fare":                 pricing.get("base_fare"),
        "service_tax":               pricing.get("service_tax"),
        "boarding_tax":              pricing.get("boarding_tax"),
        "iss_tax":                   pricing.get("iss_tax"),
        "net_amount":                pricing.get("net_amount"),
        "published_fare":            pricing.get("published_fare"),
        "payment_method":            pricing.get("payment_method"),
        # Hotel
        "hotel_name":                hinfo.get("name"),
        "hotel_city":                hinfo.get("city"),
        "hotel_address":             hinfo.get("address"),
        "checkin_date":              _ts(stay.get("checkin_date")),
        "checkout_date":             _ts(stay.get("checkout_date")),
        "rooms":                     stay.get("rooms"),
        "adults":                    stay.get("adults"),
        "children":                  stay.get("children"),
        "destination":               stay.get("destination"),
        "record_locator":            hotel.get("record_locator"),
        "source_system":             hotel.get("source_system"),
        "supplier_code":             hotel.get("supplier_code"),
        "room_name":                 room.get("name"),
        "cancellation_policy":       hotel.get("cancellation_policy"),
        # Voo
        "origin":                    fseg.get("departure") or flight.get("origin"),
        "airline":                   fseg.get("carrierCode") or flight.get("airline"),
        "flight_number":             fseg.get("flightNumber") or fseg.get("number") or flight.get("flight_number"),
        "cabin_class":               flight.get("cabin_class") or flight.get("cabinClass"),
        # Corporativo
        "cost_center_name":          corp.get("cost_center_name"),
        "project_name":              corp.get("project_name"),
        "reason_name":               corp.get("reason_name"),
        "travel_justification_name": corp.get("travel_justification_name"),
        "sales_channel":             corp.get("sales_channel"),
        "policy_compliance":         str(corp.get("policy_compliance")) if corp.get("policy_compliance") is not None else None,
        # Meta
        "raw_json":                  raw,
        "synced_at":                 datetime.utcnow().isoformat(),
    }


# ── Sync ──────────────────────────────────────────────────────────────────────

def sync_date_range(start_date: date, end_date: date) -> tuple[int, int]:
    from db import get_supabase
    sb = get_supabase()

    try:
        ids_data = get_reservation_ids(start_date, end_date)
    except Exception as exc:
        logger.error("sync_date_range get_ids %s→%s: %s", start_date, end_date, exc)
        return 0, 1

    # Coletar todos os {id, type} dos 4 buckets
    items: list[tuple[str, str]] = []
    for bucket_key in ("emitidos", "cancelados", "reservados", "expirados"):
        for entry in (ids_data.get(bucket_key) or []):
            res_id   = entry.get("id")
            res_type = entry.get("type") or "flight"
            if res_id:
                items.append((res_id, res_type))

    total = ids_data.get("totalCount") or len(items)
    logger.info("sync_date_range %s→%s: %d reservas", start_date, end_date, total)

    if not items:
        return 0, 0

    ok_count = err_count = 0
    batch: list[dict] = []

    def _fetch(item: tuple[str, str]) -> Optional[dict]:
        raw = get_reservation_detail(item[0], item[1])
        return _flatten(raw) if raw else None

    with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as pool:
        futures = {pool.submit(_fetch, it): it for it in items}
        for fut in as_completed(futures):
            result = fut.result()
            if result is None:
                err_count += 1
            else:
                batch.append(result)
                if len(batch) >= 50:
                    _upsert(sb, batch)
                    ok_count += len(batch)
                    batch = []

    if batch:
        _upsert(sb, batch)
        ok_count += len(batch)

    logger.info("sync_date_range %s→%s: %d ok, %d erros", start_date, end_date, ok_count, err_count)
    return ok_count, err_count


def _upsert(sb, records: list[dict]) -> None:
    try:
        sb.table("payfly_reservations").upsert(records, on_conflict="id").execute()
    except Exception as exc:
        logger.error("payfly upsert batch: %s", exc)

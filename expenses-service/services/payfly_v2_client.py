"""
PayFly API V2 client — auth token cache, parallel detail fetches, Supabase upsert.
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

# ── Token (thread-safe) ───────────────────────────────────────────────────────
# Se payfly_v2_bearer_token estiver definido, usa diretamente (token estático).
# Caso contrário, autentica via clientId/clientSecret → /api/v2/auth/token.

_token_lock  = threading.Lock()
_token_value: Optional[str] = None
_token_exp:   float = 0.0


def _get_token() -> str:
    global _token_value, _token_exp
    with _token_lock:
        from db import get_settings
        s = get_settings()
        # Bearer token estático tem prioridade
        if s.payfly_v2_bearer_token:
            return s.payfly_v2_bearer_token
        # Renova via clientId/clientSecret
        if _token_value and time.time() < _token_exp - 120:
            return _token_value
        resp = requests.post(
            f"{s.payfly_v2_url}/api/v2/auth/token",
            json={"clientId": s.payfly_v2_client_id, "clientSecret": s.payfly_v2_client_secret},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_value = data.get("token") or data.get("access_token")
        _token_exp   = time.time() + 86400
        return _token_value


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/json"}


# ── API calls ─────────────────────────────────────────────────────────────────

def get_reservation_ids(start_date: date, end_date: date) -> dict:
    from db import get_settings
    s = get_settings()
    resp = requests.post(
        f"{s.payfly_v2_url}/api/v2/reservations/ids",
        json={
            "startDate": start_date.isoformat(),
            "endDate":   end_date.isoformat(),
        },
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


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
        return resp.json()
    except Exception as exc:
        logger.warning("get_reservation_detail %s/%s: %s", res_id, res_type, exc)
        return None


# ── Flatten ───────────────────────────────────────────────────────────────────

def _ts(val) -> Optional[str]:
    """Return ISO string or None."""
    if not val:
        return None
    if isinstance(val, str):
        return val
    return str(val)


def _flatten(raw: dict) -> dict:
    def g(*keys):
        obj = raw
        for k in keys:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(k)
        return obj

    flight  = raw.get("flight") or {}
    hotel   = raw.get("hotel")  or {}
    company = raw.get("company") or {}
    pax     = raw.get("passenger") or {}
    appr    = raw.get("approver")  or {}
    soli    = raw.get("solicitor") or {}
    fin     = raw.get("financial") or {}
    corp    = raw.get("corporate") or {}

    return {
        "id":                        raw.get("id"),
        "type":                      raw.get("type"),
        "status":                    raw.get("status"),
        "os_number":                 raw.get("osNumber") or raw.get("os_number"),
        "trip_type":                 raw.get("tripType") or raw.get("trip_type"),
        "is_reissue":                raw.get("isReissue") or raw.get("is_reissue"),
        "original_id":               raw.get("originalId") or raw.get("original_id"),
        "order_origin":              raw.get("orderOrigin") or raw.get("order_origin"),
        # datas
        "choice_date":               _ts(raw.get("choiceDate") or raw.get("choice_date")),
        "emission_date":             _ts(raw.get("emissionDate") or raw.get("emission_date")),
        "travel_start_date":         _ts(raw.get("travelStartDate") or raw.get("travel_start_date")),
        "travel_end_date":           _ts(raw.get("travelEndDate") or raw.get("travel_end_date")),
        "approval_date":             _ts(raw.get("approvalDate") or raw.get("approval_date")),
        "cancellation_date":         _ts(raw.get("cancellationDate") or raw.get("cancellation_date")),
        "expiration_date":           _ts(raw.get("expirationDate") or raw.get("expiration_date")),
        "last_update_date":          _ts(raw.get("lastUpdateDate") or raw.get("last_update_date")),
        "request_date":              _ts(raw.get("requestDate") or raw.get("request_date")),
        # empresa
        "company_id":                company.get("id") or company.get("companyId"),
        "company_cnpj":              company.get("cnpj"),
        "company_name":              company.get("name") or company.get("companyName"),
        # passageiro
        "passenger_name":            pax.get("name"),
        "passenger_email":           pax.get("email"),
        "passenger_document":        pax.get("document"),
        "passenger_employee_id":     pax.get("employeeId") or pax.get("employee_id"),
        "passenger_department_name": pax.get("departmentName") or pax.get("department_name"),
        "passenger_age_group":       pax.get("ageGroup") or pax.get("age_group"),
        "passenger_employee_level":  pax.get("employeeLevel") or pax.get("employee_level"),
        # aprovador / solicitante
        "approver_name":             appr.get("name"),
        "approver_email":            appr.get("email"),
        "solicitor_name":            soli.get("name"),
        "solicitor_email":           soli.get("email"),
        # financeiro
        "currency":                  fin.get("currency"),
        "total_amount":              fin.get("totalAmount") or fin.get("total_amount"),
        "daily_rate":                fin.get("dailyRate") or fin.get("daily_rate"),
        "total_nights":              fin.get("totalNights") or fin.get("total_nights"),
        "base_fare":                 fin.get("baseFare") or fin.get("base_fare"),
        "service_tax":               fin.get("serviceTax") or fin.get("service_tax"),
        "boarding_tax":              fin.get("boardingTax") or fin.get("boarding_tax"),
        "iss_tax":                   fin.get("issTax") or fin.get("iss_tax"),
        "net_amount":                fin.get("netAmount") or fin.get("net_amount"),
        "published_fare":            fin.get("publishedFare") or fin.get("published_fare"),
        "payment_method":            fin.get("paymentMethod") or fin.get("payment_method"),
        # hotel
        "hotel_name":                hotel.get("name") or hotel.get("hotelName"),
        "hotel_city":                hotel.get("city") or hotel.get("hotelCity"),
        "hotel_address":             hotel.get("address"),
        "checkin_date":              _ts(hotel.get("checkinDate") or hotel.get("checkin_date")),
        "checkout_date":             _ts(hotel.get("checkoutDate") or hotel.get("checkout_date")),
        "rooms":                     hotel.get("rooms"),
        "adults":                    hotel.get("adults"),
        "children":                  hotel.get("children"),
        "destination":               hotel.get("destination"),
        "record_locator":            hotel.get("recordLocator") or hotel.get("record_locator"),
        "source_system":             hotel.get("sourceSystem") or hotel.get("source_system"),
        "supplier_code":             hotel.get("supplierCode") or hotel.get("supplier_code"),
        "room_name":                 hotel.get("roomName") or hotel.get("room_name"),
        "cancellation_policy":       hotel.get("cancellationPolicy") or hotel.get("cancellation_policy"),
        # voo
        "origin":                    flight.get("origin"),
        "airline":                   flight.get("airline"),
        "flight_number":             flight.get("flightNumber") or flight.get("flight_number"),
        "cabin_class":               flight.get("cabinClass") or flight.get("cabin_class"),
        # corporativo
        "cost_center_name":          corp.get("costCenterName") or corp.get("cost_center_name"),
        "project_name":              corp.get("projectName") or corp.get("project_name"),
        "reason_name":               corp.get("reasonName") or corp.get("reason_name"),
        "travel_justification_name": corp.get("travelJustificationName") or corp.get("travel_justification_name"),
        "sales_channel":             corp.get("salesChannel") or corp.get("sales_channel"),
        "policy_compliance":         corp.get("policyCompliance") or corp.get("policy_compliance"),
        # meta
        "raw_json":                  raw,
        "synced_at":                 datetime.utcnow().isoformat(),
    }


# ── Sync ──────────────────────────────────────────────────────────────────────

def sync_date_range(start_date: date, end_date: date) -> tuple[int, int]:
    """
    Fetch IDs for date range, pull details in parallel, upsert to Supabase.
    Returns (ok_count, error_count).
    """
    from db import get_supabase
    sb = get_supabase()

    try:
        ids_resp = get_reservation_ids(start_date, end_date)
    except Exception as exc:
        logger.error("sync_date_range get_ids %s→%s: %s", start_date, end_date, exc)
        return 0, 1

    # Collect all {id, type} pairs across 4 buckets
    items: list[tuple[str, str]] = []
    STATUS_MAP = {
        "emitidos":   "Emitido",
        "cancelados": "Cancelado",
        "reservados": "Reservado",
        "expirados":  "Expirado",
    }
    for bucket_key in ("emitidos", "cancelados", "reservados", "expirados"):
        for entry in (ids_resp.get(bucket_key) or []):
            res_id   = entry.get("id")   or entry.get("reservationId")
            res_type = entry.get("type") or entry.get("reservationType") or "flight"
            if res_id:
                items.append((res_id, res_type))

    if not items:
        logger.info("sync_date_range %s→%s: 0 reservas", start_date, end_date)
        return 0, 0

    ok_count = err_count = 0
    batch: list[dict] = []

    def _fetch_and_flatten(item: tuple[str, str]) -> Optional[dict]:
        raw = get_reservation_detail(item[0], item[1])
        if raw is None:
            return None
        return _flatten(raw)

    with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as pool:
        futures = {pool.submit(_fetch_and_flatten, it): it for it in items}
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

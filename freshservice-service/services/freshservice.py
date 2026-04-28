import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from db import get_settings, get_supabase

logger = logging.getLogger(__name__)

BASE_URL = "https://voetur1.freshservice.com/api/v2"
PAGE_SIZE = 100
RATE_LIMIT_DELAY = 0.5
MAX_RETRIES = 3
_BRT = timezone(timedelta(hours=-3))
_RATING_MAP = {"Happy": 3, "Neutral": 2, "Unhappy": 1}
_PHASE_ORDER = ["resolved", "closed", "csat", "metadata"]
_PHASE_STATUS = {"resolved": 4, "closed": 5}

# {key: (data, monotonic_expires)}
_live_cache: dict[str, tuple[dict, float]] = {}


class FreshserviceClient:
    def __init__(self, api_key: str):
        self._auth = (api_key, "X")

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=30, auth=self._auth) as client:
                    r = client.get(url, params=params)
                    if r.status_code == 429:
                        time.sleep(2 ** (attempt + 1))
                        continue
                    r.raise_for_status()
                    time.sleep(RATE_LIMIT_DELAY)
                    return r.json()
            except httpx.HTTPStatusError as exc:
                # don't retry client errors (4xx)
                if exc.response.status_code < 500 or attempt >= MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)
                continue
            except httpx.RequestError:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return {}

    def list_tickets_by_status(self, status: int, page: int = 1) -> list[dict]:
        """Backfill: fetch tickets by exact status via /tickets/filter."""
        return self._get("/tickets/filter", {
            "query": f'"status:{status}"',
            "page": page,
            "per_page": PAGE_SIZE,
        }).get("tickets", [])

    def list_updated_tickets(self, updated_since: str, page: int = 1) -> list[dict]:
        """Daily sync: all tickets updated since a given timestamp."""
        return self._get("/tickets", {
            "updated_since": updated_since,
            "include": "stats",
            "page": page,
            "per_page": PAGE_SIZE,
        }).get("tickets", [])

    def list_satisfaction_ratings(
        self,
        page: int = 1,
        updated_since: str | None = None,
    ) -> list[dict]:
        params: dict = {"page": page, "per_page": PAGE_SIZE}
        if updated_since:
            params["updated_since"] = updated_since
        return self._get("/surveys/satisfaction_ratings", params).get("satisfaction_ratings", [])

    def list_agents(self, page: int = 1) -> list[dict]:
        return self._get("/agents", {"page": page, "per_page": PAGE_SIZE}).get("agents", [])

    def list_groups(self) -> list[dict]:
        return self._get("/groups", {"per_page": PAGE_SIZE}).get("groups", [])

    def list_companies(self, page: int = 1) -> list[dict]:
        return self._get("/companies", {"page": page, "per_page": PAGE_SIZE}).get("companies", [])

    def get_open_tickets(self, page: int = 1) -> list[dict]:
        # status:2 = Open; sorted oldest-first via /tickets/filter
        return self._get("/tickets/filter", {
            "query": '"status:2"',
            "order_by": "created_at",
            "order_type": "asc",
            "page": page,
            "per_page": 10,
        }).get("tickets", [])

    def get_waiting_vendor_tickets(self, page: int = 1) -> list[dict]:
        return self._get("/tickets", {
            "filter": "waiting_on_third_party",
            "page": page,
            "per_page": PAGE_SIZE,
        }).get("tickets", [])


def _extract_ticket_row(raw: dict) -> dict:
    stats = raw.get("stats") or {}
    return {
        "id":              raw["id"],
        "subject":         raw.get("subject") or "",
        "status":          raw.get("status"),
        "priority":        raw.get("priority"),
        "type":            raw.get("type"),
        "group_id":        raw.get("group_id"),
        "responder_id":    raw.get("responder_id"),
        "requester_id":    raw.get("requester_id"),
        "company_id":      raw.get("company_id"),
        "created_at":      raw.get("created_at"),
        "updated_at":      raw.get("updated_at"),
        "resolved_at":     stats.get("resolved_at"),
        "closed_at":       stats.get("closed_at"),
        "due_by":          raw.get("due_by"),
        "fr_due_by":       raw.get("fr_due_by"),
        "fr_responded_at": stats.get("first_responded_at"),
        "is_escalated":    raw.get("is_escalated", False),
        "raw":             raw,
    }


def _upsert_tickets(db, rows: list[dict]) -> None:
    if not rows:
        return
    db.table("freshservice_tickets").upsert(rows).execute()


def _sync_csat_page(
    db,
    client: FreshserviceClient,
    page: int,
    updated_since: str | None = None,
) -> int:
    try:
        ratings = client.list_satisfaction_ratings(page=page, updated_since=updated_since)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.info("CSAT endpoint unavailable (404) — skipping")
            return 0
        raise
    if not ratings:
        return 0

    batch = []
    for r in ratings:
        ticket_id = r.get("ticket_id")
        if not ticket_id:
            continue
        csat_value = _RATING_MAP.get(r.get("rating", ""))
        batch.append({
            "ticket_id":    ticket_id,
            "csat_rating":  csat_value,
            "csat_comment": (r.get("feedback") or ""),
        })

    if batch:
        db.rpc("upsert_csat_ratings", {"p_ratings": batch}).execute()

    return len(ratings)


def _sync_metadata(db, client: FreshserviceClient) -> None:
    page = 1
    while True:
        agents = client.list_agents(page=page)
        if not agents:
            break
        rows = [{"id": a["id"], "name": a.get("name", ""), "email": a.get("email")} for a in agents]
        db.table("freshservice_agents").upsert(rows).execute()
        if len(agents) < PAGE_SIZE:
            break
        page += 1

    groups = client.list_groups()
    if groups:
        rows = [{"id": g["id"], "name": g.get("name", "")} for g in groups]
        db.table("freshservice_groups").upsert(rows).execute()

    page = 1
    while True:
        companies = client.list_companies(page=page)
        if not companies:
            break
        rows = [{"id": c["id"], "name": c.get("name", "")} for c in companies]
        db.table("freshservice_companies").upsert(rows).execute()
        if len(companies) < PAGE_SIZE:
            break
        page += 1

    logger.info("Freshservice metadata sync completed")


def _save_checkpoint(db, log_id: int, phase: str, page: int, upserted: int) -> None:
    db.table("freshservice_sync_log").update({
        "checkpoint":       {"phase": phase, "page": page},
        "tickets_upserted": upserted,
    }).eq("id", log_id).execute()


def _run_backfill_sync() -> None:
    db = get_supabase()
    s = get_settings()
    client = FreshserviceClient(s.freshservice_api_key)

    existing = (
        db.table("freshservice_sync_log")
        .select("*")
        .eq("sync_type", "backfill")
        .eq("status", "running")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if existing:
        log_id = existing[0]["id"]
        checkpoint = existing[0].get("checkpoint") or {}
        total_upserted = existing[0].get("tickets_upserted", 0)
        logger.info("Resuming backfill from checkpoint: %s", checkpoint)
    else:
        result = db.table("freshservice_sync_log").insert({
            "sync_type":        "backfill",
            "status":           "running",
            "checkpoint":       {},
            "tickets_upserted": 0,
        }).execute()
        log_id = result.data[0]["id"]
        checkpoint = {}
        total_upserted = 0

    current_phase = checkpoint.get("phase", "resolved")
    start_page = checkpoint.get("page", 1)

    if current_phase not in _PHASE_ORDER:
        current_phase = "resolved"
    start_idx = _PHASE_ORDER.index(current_phase)

    try:
        for phase in _PHASE_ORDER[start_idx:]:
            page = start_page if phase == current_phase else 1

            if phase in ("resolved", "closed"):
                while True:
                    tickets = client.list_tickets_by_status(status=_PHASE_STATUS[phase], page=page)
                    if not tickets:
                        break
                    rows = [_extract_ticket_row(t) for t in tickets]
                    _upsert_tickets(db, rows)
                    total_upserted += len(rows)
                    logger.info("Backfill %s p%d: %d tickets (total %d)", phase, page, len(rows), total_upserted)
                    _save_checkpoint(db, log_id, phase, page + 1, total_upserted)
                    if len(tickets) < PAGE_SIZE:
                        break
                    page += 1

            elif phase == "csat":
                while True:
                    count = _sync_csat_page(db, client, page)
                    logger.info("Backfill CSAT page %d: %d ratings", page, count)
                    if count == 0:
                        break
                    _save_checkpoint(db, log_id, "csat", page + 1, total_upserted)
                    if count < PAGE_SIZE:
                        break
                    page += 1

            elif phase == "metadata":
                _sync_metadata(db, client)

            # Move to next phase
            next_idx = _PHASE_ORDER.index(phase) + 1
            if next_idx < len(_PHASE_ORDER):
                _save_checkpoint(db, log_id, _PHASE_ORDER[next_idx], 1, total_upserted)

        db.table("freshservice_sync_log").update({
            "status":           "completed",
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "checkpoint":       {"phase": "done"},
            "tickets_upserted": total_upserted,
        }).eq("id", log_id).execute()
        logger.info("Freshservice backfill completed: %d tickets", total_upserted)

    except Exception as e:
        logger.exception("Freshservice backfill failed")
        db.table("freshservice_sync_log").update({
            "status":           "failed",
            "error":            str(e),
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "tickets_upserted": total_upserted,
        }).eq("id", log_id).execute()
        raise


def _run_daily_sync_sync() -> None:
    from services.freshservice_agent import generate_daily_summary_sync  # noqa: PLC0415

    db = get_supabase()
    s = get_settings()
    client = FreshserviceClient(s.freshservice_api_key)

    yesterday = (datetime.now(_BRT) - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    updated_since = yesterday.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = db.table("freshservice_sync_log").insert({
        "sync_type":        "daily",
        "status":           "running",
        "checkpoint":       {"updated_since": updated_since},
        "tickets_upserted": 0,
    }).execute()
    log_id = result.data[0]["id"]
    total_upserted = 0

    try:
        page = 1
        while True:
            tickets = client.list_updated_tickets(updated_since=updated_since, page=page)
            if not tickets:
                break
            rows = [_extract_ticket_row(t) for t in tickets if t.get("status") in (4, 5)]
            if rows:
                _upsert_tickets(db, rows)
                total_upserted += len(rows)
            if len(tickets) < PAGE_SIZE:
                break
            page += 1

        page = 1
        while True:
            count = _sync_csat_page(db, client, page, updated_since=updated_since)
            if count == 0 or count < PAGE_SIZE:
                break
            page += 1

        today = datetime.now(_BRT)
        p_from = yesterday.astimezone(timezone.utc).isoformat()
        p_to = today.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()

        summary_raw = db.rpc("freshservice_summary", {"p_from": p_from, "p_to": p_to}).execute().data or {}

        stats = {
            "date":               yesterday.strftime("%Y-%m-%d"),
            "total_closed":       summary_raw.get("total_closed", 0),
            "csat_avg":           summary_raw.get("csat_avg"),
            "sla_breach_pct":     summary_raw.get("sla_breach_pct"),
            "avg_resolution_min": summary_raw.get("avg_resolution_min"),
            "tickets_synced":     total_upserted,
        }

        summary_json = generate_daily_summary_sync(stats)

        db.table("freshservice_sync_log").update({
            "status":           "completed",
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "tickets_upserted": total_upserted,
            "summary_json":     summary_json,
        }).eq("id", log_id).execute()
        logger.info("Freshservice daily sync completed: %d tickets", total_upserted)

    except Exception as e:
        logger.exception("Freshservice daily sync failed")
        db.table("freshservice_sync_log").update({
            "status":           "failed",
            "error":            str(e),
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "tickets_upserted": total_upserted,
        }).eq("id", log_id).execute()
        raise


def _get_live_metrics_sync() -> dict:
    s = get_settings()
    client = FreshserviceClient(s.freshservice_api_key)

    oldest_open = client.get_open_tickets(page=1)

    waiting_vendor: list[dict] = []
    page = 1
    while True:
        batch = client.get_waiting_vendor_tickets(page=page)
        if not batch:
            break
        waiting_vendor.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1

    by_group: dict[str, int] = {}
    for t in waiting_vendor:
        key = str(t.get("group_id") or "sem-grupo")
        by_group[key] = by_group.get(key, 0) + 1

    now = datetime.now(timezone.utc)
    for t in oldest_open:
        created = t.get("created_at")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                t["time_open_hours"] = int((now - dt).total_seconds() / 3600)
            except Exception:
                pass

    return {
        "oldest_open":         oldest_open[:10],
        "waiting_vendor_count": len(waiting_vendor),
        "by_vendor":           [{"group_id": k, "count": v} for k, v in sorted(by_group.items(), key=lambda x: -x[1])],
    }


async def run_backfill() -> None:
    await asyncio.to_thread(_run_backfill_sync)


async def run_daily_sync() -> None:
    await asyncio.to_thread(_run_daily_sync_sync)


async def get_live_metrics() -> dict:
    cache_key = "live"
    now = time.monotonic()

    if cache_key in _live_cache:
        data, expires_at = _live_cache[cache_key]
        if now < expires_at:
            return data

    data = await asyncio.to_thread(_get_live_metrics_sync)
    _live_cache[cache_key] = (data, now + 1800)
    return data

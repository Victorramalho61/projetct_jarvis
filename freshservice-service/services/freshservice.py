import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from services.app_logger import log_event
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
# Workspaces ativos (id=23 Financeiro está em draft)
_ACTIVE_WORKSPACE_IDS = [2, 5, 6, 13, 18, 19, 21, 22, 24, 25]
# Data de início aproximada de cada workspace (para gerar chunks trimestrais)
_WS_START_DATES = {
    2: "2023-06-01", 5: "2023-08-01", 6: "2023-08-01",
    13: "2023-11-01", 18: "2025-01-01", 19: "2025-02-01",
    21: "2025-10-01", 22: "2025-10-01", 24: "2026-03-01", 25: "2026-04-01",
}

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

    def list_tickets_by_status(self, status: int, page: int = 1, workspace_id: int | None = None) -> list[dict]:
        """Backfill: fetch tickets by exact status via /tickets/filter."""
        params: dict = {"query": f'"status:{status}"', "page": page, "per_page": PAGE_SIZE}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        try:
            return self._get("/tickets/filter", params).get("tickets", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                logger.warning("Workspace %s: acesso negado (403) — ignorando", workspace_id)
                return []
            raise

    def list_tickets_by_date_range(
        self, status: int, date_from: str, date_to: str,
        page: int = 1, workspace_id: int | None = None,
    ) -> list[dict]:
        """Backfill com chunks: status + intervalo de created_at (evita limite de 10k)."""
        query = f'"status:{status} AND created_at:>\'{date_from}\' AND created_at:<\'{date_to}\'"'
        params: dict = {"query": query, "page": page, "per_page": PAGE_SIZE}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        try:
            return self._get("/tickets/filter", params).get("tickets", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                logger.warning("Workspace %s: %s — ignorando", workspace_id, exc.response.status_code)
                return []
            raise

    def list_updated_tickets(self, updated_since: str, page: int = 1, workspace_id: int | None = None) -> list[dict]:
        """Daily sync: all tickets updated since a given timestamp."""
        params: dict = {"updated_since": updated_since, "include": "stats", "page": page, "per_page": PAGE_SIZE}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        try:
            return self._get("/tickets", params).get("tickets", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                logger.warning("Workspace %s: acesso negado (403) — ignorando", workspace_id)
                return []
            raise

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
        try:
            return self._get("/companies", {"page": page, "per_page": PAGE_SIZE}).get("companies", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Endpoint /companies nao disponivel neste plano Freshservice — ignorando")
                return []
            raise

    def get_open_tickets(self, page: int = 1) -> list[dict]:
        # status:2 = Open; sorted oldest-first via /tickets/filter
        return self._get("/tickets/filter", {
            "query": '"status:2"',
            "order_by": "created_at",
            "order_type": "asc",
            "page": page,
            "per_page": 10,
        }).get("tickets", [])

    # status 6 = Waiting on Third Party (padrão Freshservice)
    _WAITING_VENDOR_STATUS = 6

    def get_waiting_vendor_tickets(self, page: int = 1) -> list[dict]:
        try:
            return self._get("/tickets/filter", {
                "query": f'"status:{self._WAITING_VENDOR_STATUS}"',
                "page": page,
                "per_page": PAGE_SIZE,
            }).get("tickets", [])
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (400, 422):
                logger.warning("get_waiting_vendor_tickets: status %s inválido para esta conta (%s)", self._WAITING_VENDOR_STATUS, exc)
                return []
            raise


def _extract_ticket_row(raw: dict) -> dict:
    stats = raw.get("stats") or {}
    return {
        "id":              raw["id"],
        "workspace_id":    raw.get("workspace_id"),
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


_UPSERT_BATCH = 5


def _upsert_tickets(db, rows: list[dict]) -> None:
    if not rows:
        return
    for i in range(0, len(rows), _UPSERT_BATCH):
        db.table("freshservice_tickets").upsert(rows[i:i + _UPSERT_BATCH]).execute()


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


def _generate_date_chunks(ws_id: int, chunk_months: int = 3) -> list[tuple[str, str]]:
    """Gera intervalos trimestrais desde o início do workspace até amanhã."""
    from datetime import date, timedelta
    start = date.fromisoformat(_WS_START_DATES.get(ws_id, "2023-01-01"))
    end = date.today() + timedelta(days=1)
    chunks: list[tuple[str, str]] = []
    cur = start
    while cur < end:
        m = cur.month - 1 + chunk_months
        nxt = date(cur.year + m // 12, m % 12 + 1, 1)
        if nxt > end:
            nxt = end
        chunks.append((cur.isoformat(), nxt.isoformat()))
        cur = nxt
    return chunks


def _save_checkpoint(
    db, log_id: int, workspace_id: int | None, phase: str, page: int, upserted: int,
    date_from: str | None = None,
) -> None:
    cp: dict = {"workspace_id": workspace_id, "phase": phase, "page": page}
    if date_from:
        cp["date_from"] = date_from
    db.table("freshservice_sync_log").update({
        "checkpoint":       cp,
        "tickets_upserted": upserted,
    }).eq("id", log_id).execute()


def _run_backfill_sync() -> int:
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

    # Determina ponto de retomada — suporta checkpoint legado (sem workspace_id)
    ckpt_ws        = checkpoint.get("workspace_id", _ACTIVE_WORKSPACE_IDS[0])
    ckpt_phase     = checkpoint.get("phase", "resolved")
    ckpt_page      = checkpoint.get("page", 1)
    ckpt_date_from = checkpoint.get("date_from")

    if ckpt_ws not in _ACTIVE_WORKSPACE_IDS:
        ckpt_ws = _ACTIVE_WORKSPACE_IDS[0]
    if ckpt_phase not in _PHASE_ORDER:
        ckpt_phase = "resolved"

    ws_start_idx    = _ACTIVE_WORKSPACE_IDS.index(ckpt_ws)
    phase_start_idx = _PHASE_ORDER.index(ckpt_phase)

    try:
        for ws_id in _ACTIVE_WORKSPACE_IDS[ws_start_idx:]:
            is_first_ws = (ws_id == ckpt_ws)
            phase_start = phase_start_idx if is_first_ws else 0

            for phase in _PHASE_ORDER[phase_start:]:
                is_resume_phase = is_first_ws and (phase == ckpt_phase)

                if phase in ("resolved", "closed"):
                    chunks = _generate_date_chunks(ws_id)
                    # Determina chunk de retomada
                    chunk_start = 0
                    if is_resume_phase and ckpt_date_from:
                        chunk_start = next(
                            (i for i, (df, _) in enumerate(chunks) if df >= ckpt_date_from), 0
                        )
                    for chunk_idx, (date_from, date_to) in enumerate(chunks[chunk_start:], chunk_start):
                        is_resume_chunk = is_resume_phase and (date_from == ckpt_date_from)
                        page = ckpt_page if is_resume_chunk else 1
                        while True:
                            tickets = client.list_tickets_by_date_range(
                                status=_PHASE_STATUS[phase], date_from=date_from, date_to=date_to,
                                page=page, workspace_id=ws_id,
                            )
                            if not tickets:
                                break
                            rows = [_extract_ticket_row(t) for t in tickets]
                            _upsert_tickets(db, rows)
                            total_upserted += len(rows)
                            logger.info(
                                "Backfill ws%d %s [%s] p%d: %d tickets (total %d)",
                                ws_id, phase, date_from[:7], page, len(rows), total_upserted,
                            )
                            if page % 10 == 0:
                                log_event("info", "freshservice",
                                          f"Backfill ws{ws_id} {phase} {date_from[:7]}: {len(rows)} tickets (total {total_upserted})")
                            _save_checkpoint(db, log_id, ws_id, phase, page + 1, total_upserted, date_from=date_from)
                            if len(tickets) < PAGE_SIZE:
                                break
                            page += 1

                elif phase == "csat":
                    if ws_id == _ACTIVE_WORKSPACE_IDS[0]:
                        page = ckpt_page if is_resume_phase else 1
                        while True:
                            count = _sync_csat_page(db, client, page)
                            logger.info("Backfill CSAT page %d: %d ratings", page, count)
                            if count == 0:
                                break
                            _save_checkpoint(db, log_id, ws_id, "csat", page + 1, total_upserted)
                            if count < PAGE_SIZE:
                                break
                            page += 1

                elif phase == "metadata":
                    if ws_id == _ACTIVE_WORKSPACE_IDS[0]:
                        _sync_metadata(db, client)

                # Avança para próxima fase
                next_phase_idx = _PHASE_ORDER.index(phase) + 1
                if next_phase_idx < len(_PHASE_ORDER):
                    _save_checkpoint(db, log_id, ws_id, _PHASE_ORDER[next_phase_idx], 1, total_upserted)

            # Avança para próximo workspace
            next_ws_idx = _ACTIVE_WORKSPACE_IDS.index(ws_id) + 1
            if next_ws_idx < len(_ACTIVE_WORKSPACE_IDS):
                _save_checkpoint(db, log_id, _ACTIVE_WORKSPACE_IDS[next_ws_idx], "resolved", 1, total_upserted)
                log_event("info", "freshservice",
                          f"Backfill ws{ws_id} concluído ({total_upserted} total), iniciando ws{_ACTIVE_WORKSPACE_IDS[next_ws_idx]}")

        db.table("freshservice_sync_log").update({
            "status":           "completed",
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "checkpoint":       {"phase": "done"},
            "tickets_upserted": total_upserted,
        }).eq("id", log_id).execute()
        logger.info("Freshservice backfill completed: %d tickets", total_upserted)
        log_event("info", "freshservice", f"Backfill concluído: {total_upserted} tickets em {len(_ACTIVE_WORKSPACE_IDS)} workspaces")
        return total_upserted

    except Exception as e:
        logger.exception("Freshservice backfill failed")
        log_event("error", "freshservice", f"Backfill falhou: {e}")
        db.table("freshservice_sync_log").update({
            "status":           "failed",
            "error":            str(e),
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "tickets_upserted": total_upserted,
        }).eq("id", log_id).execute()
        raise


def _run_daily_sync_sync() -> int:
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
        for ws_id in _ACTIVE_WORKSPACE_IDS:
            page = 1
            while True:
                tickets = client.list_updated_tickets(updated_since=updated_since, page=page, workspace_id=ws_id)
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

        summary_json = None
        try:
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
        except Exception as e:
            logger.warning("Daily summary generation failed (sync data saved): %s", e)

        db.table("freshservice_sync_log").update({
            "status":           "completed",
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "tickets_upserted": total_upserted,
            "summary_json":     summary_json,
        }).eq("id", log_id).execute()
        logger.info("Freshservice daily sync completed: %d tickets", total_upserted)
        return total_upserted

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


async def run_backfill() -> int:
    return await asyncio.to_thread(_run_backfill_sync)


async def run_daily_sync() -> int:
    return await asyncio.to_thread(_run_daily_sync_sync)


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

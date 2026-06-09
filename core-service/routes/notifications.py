"""
Endpoint batch de notificações — agrega 5 queries em 1 chamada.
Reduz carga de polling do frontend de ~330 req/hora/admin para ~50.
Cache Redis TTL=30s: sistemas (todos os usuários) e contadores admin.
"""
import json
import logging

from fastapi import APIRouter, Depends

from auth import get_current_user
from db import get_redis, get_supabase

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)

_TTL_SYSTEMS = 30   # segundos — sistemas mudam a cada 5min pelo monitor
_TTL_ADMIN   = 15   # segundos — contadores admin mudam com frequência


async def _cache_get(redis, key: str):
    try:
        raw = await redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _cache_set(redis, key: str, value, ttl: int):
    try:
        await redis.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


@router.get("/summary")
async def notifications_summary(current_user: dict = Depends(get_current_user)):
    """
    Agrega contagens de notificação em uma única chamada.
    Usado por useNotifications.ts no frontend.
    """
    db = get_supabase()
    is_admin = current_user.get("role") == "admin"
    redis = await get_redis()

    # ── 1. Sistemas (cache compartilhado entre todos os usuários) ──
    systems_key = "notif:systems:v1"
    systems_cached = await _cache_get(redis, systems_key) if redis else None

    if systems_cached is not None:
        systems_down     = systems_cached["down"]
        systems_degraded = systems_cached["degraded"]
    else:
        systems_down: list[dict] = []
        systems_degraded: list[dict] = []
        try:
            systems = (
                db.table("monitored_systems")
                .select("id,name,consecutive_down_count,last_alerted_at")
                .eq("enabled", True)
                .execute()
                .data or []
            )
            sys_ids = [s["id"] for s in systems]
            if sys_ids:
                checks = (
                    db.table("system_checks")
                    .select("system_id,status,detail,checked_at")
                    .in_("system_id", sys_ids)
                    .order("checked_at", desc=True)
                    .limit(len(sys_ids) * 2)
                    .execute()
                    .data or []
                )
                latest: dict[str, dict] = {}
                for c in checks:
                    if c["system_id"] not in latest:
                        latest[c["system_id"]] = c

                sys_map = {s["id"]: s for s in systems}
                for sid, check in latest.items():
                    sys = sys_map.get(sid, {})
                    if check["status"] == "down" and (sys.get("consecutive_down_count") or 0) >= 2:
                        systems_down.append({
                            "id": sid,
                            "name": sys.get("name", ""),
                            "detail": check.get("detail") or "Sistema inacessível",
                        })
                    elif check["status"] == "degraded":
                        systems_degraded.append({
                            "id": sid,
                            "name": sys.get("name", ""),
                            "detail": check.get("detail") or "Resposta lenta ou parcial",
                        })
        except Exception as exc:
            logger.warning("notifications/summary: falha ao buscar sistemas — %s", exc)

        if redis:
            await _cache_set(redis, systems_key, {"down": systems_down, "degraded": systems_degraded}, _TTL_SYSTEMS)

    # ── 2. Contadores admin (cache compartilhado entre todos os admins) ──
    pending_users = 0
    pending_proposals = 0
    unread_inbox = 0
    critical_findings = 0

    if is_admin:
        admin_key = "notif:admin:v1"
        admin_cached = await _cache_get(redis, admin_key) if redis else None

        if admin_cached is not None:
            pending_users      = admin_cached["pending_users"]
            pending_proposals  = admin_cached["pending_proposals"]
            unread_inbox       = admin_cached["unread_inbox"]
            critical_findings  = admin_cached["critical_findings"]
        else:
            try:
                result = db.table("profiles").select("id", count="exact").eq("active", False).execute()
                pending_users = result.count or 0
            except Exception as exc:
                logger.warning("notifications/summary: falha ao buscar pending users — %s", exc)

            try:
                result = db.table("improvement_proposals").select("id", count="exact").in_("validation_status", ["pending", "pending_cto"]).execute()
                pending_proposals = result.count or 0
            except Exception as exc:
                logger.warning("notifications/summary: falha ao buscar proposals — %s", exc)

            try:
                result = db.table("agent_messages").select("id", count="exact").eq("to_agent", "human").eq("status", "pending").execute()
                unread_inbox = result.count or 0
            except Exception as exc:
                logger.warning("notifications/summary: falha ao buscar inbox — %s", exc)

            try:
                result = db.table("agent_events").select("id", count="exact").eq("processed", False).eq("priority", "critical").execute()
                critical_findings = result.count or 0
            except Exception as exc:
                logger.warning("notifications/summary: falha ao buscar events — %s", exc)

            if redis:
                await _cache_set(redis, admin_key, {
                    "pending_users":     pending_users,
                    "pending_proposals": pending_proposals,
                    "unread_inbox":      unread_inbox,
                    "critical_findings": critical_findings,
                }, _TTL_ADMIN)

    return {
        "systems_down":      systems_down,
        "systems_degraded":  systems_degraded,
        "pending_users":     pending_users,
        "pending_proposals": pending_proposals,
        "unread_inbox":      unread_inbox,
        "critical_findings": critical_findings,
    }

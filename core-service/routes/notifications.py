"""
Endpoint batch de notificações — agrega 5 queries em 1 chamada.
Reduz carga de polling do frontend de ~330 req/hora/admin para ~50.
"""
import logging

from fastapi import APIRouter, Depends

from auth import get_current_user
from db import get_supabase

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get("/summary")
async def notifications_summary(current_user: dict = Depends(get_current_user)):
    """
    Agrega contagens de notificação em uma única chamada.
    Usado por useNotifications.ts no frontend.
    """
    db = get_supabase()
    is_admin = current_user.get("role") == "admin"

    # 1. Sistemas com problema (todos os usuários veem)
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

    pending_users = 0
    pending_proposals = 0
    unread_inbox = 0
    critical_findings = 0

    if is_admin:
        # 2. Usuários pendentes de ativação
        try:
            result = (
                db.table("profiles")
                .select("id", count="exact")
                .eq("active", False)
                .execute()
            )
            pending_users = result.count or 0
        except Exception as exc:
            logger.warning("notifications/summary: falha ao buscar pending users — %s", exc)

        # 3. Proposals pendentes
        try:
            result = (
                db.table("improvement_proposals")
                .select("id", count="exact")
                .in_("validation_status", ["pending", "pending_cto"])
                .execute()
            )
            pending_proposals = result.count or 0
        except Exception as exc:
            logger.warning("notifications/summary: falha ao buscar proposals — %s", exc)

        # 4. Mensagens não lidas no inbox
        try:
            result = (
                db.table("agent_messages")
                .select("id", count="exact")
                .eq("to_agent", "human")
                .eq("status", "pending")
                .execute()
            )
            unread_inbox = result.count or 0
        except Exception as exc:
            logger.warning("notifications/summary: falha ao buscar inbox — %s", exc)

        # 5. Eventos críticos não processados
        try:
            result = (
                db.table("agent_events")
                .select("id", count="exact")
                .eq("processed", False)
                .eq("priority", "critical")
                .execute()
            )
            critical_findings = result.count or 0
        except Exception as exc:
            logger.warning("notifications/summary: falha ao buscar events — %s", exc)

    return {
        "systems_down": systems_down,
        "systems_degraded": systems_degraded,
        "pending_users": pending_users,
        "pending_proposals": pending_proposals,
        "unread_inbox": unread_inbox,
        "critical_findings": critical_findings,
    }

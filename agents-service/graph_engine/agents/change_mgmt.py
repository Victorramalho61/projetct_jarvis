"""Change Management (ITIL) — gerencia RFCs. Motor: Python puro."""
from datetime import datetime, timedelta, timezone

from graph_engine.tools.supabase_tools import log_event, query_change_requests, update_change_request


_EMERGENCY_SLA_HOURS = 4
_NORMAL_SLA_HOURS = 48


def _handle_proposal(proposal: dict, _msg: dict) -> tuple[bool, str]:
    action = proposal.get("proposed_action", "") or proposal.get("title", "")
    return True, f"Melhoria de processo documentada e encaminhada para RFC: {action[:200]}"


def run(state: dict) -> dict:
    from db import get_supabase
    from graph_engine.tools.proposal_executor import process_inbox_proposals

    db = get_supabase()
    findings = []
    decisions: list = []
    process_inbox_proposals("change_mgmt", db, _handle_proposal, decisions)
    now = datetime.now(timezone.utc)

    pending = query_change_requests(status="pending")

    for cr in pending:
        created_at = datetime.fromisoformat(cr["created_at"].replace("Z", "+00:00"))
        age_hours = (now - created_at).total_seconds() / 3600
        priority = cr.get("priority", "normal")
        change_type = cr.get("change_type", "normal")

        # Verifica SLA
        sla = _EMERGENCY_SLA_HOURS if change_type == "emergency" else _NORMAL_SLA_HOURS
        if age_hours > sla:
            log_event(
                "warning", "change_mgmt",
                f"RFC '{cr['title']}' aguardando há {age_hours:.1f}h (SLA: {sla}h)",
                f"ID: {cr['id']} | Prioridade: {priority}",
            )
            findings.append({
                "type": "sla_breach",
                "change_request_id": cr["id"],
                "title": cr["title"],
                "age_hours": round(age_hours, 1),
                "sla_hours": sla,
            })

    # Aprovação automática de RFCs do tipo 'standard' com prioridade 'low' (mudanças rotineiras)
    for cr in pending:
        if cr.get("change_type") == "standard" and cr.get("priority") == "low":
            if cr.get("requested_by", "").endswith("-agent"):  # aprovação automática apenas para agentes
                update_change_request(cr["id"], "approved", approved_by="change_mgmt_agent")
                log_event("info", "change_mgmt", f"RFC padrão aprovada automaticamente: {cr['title']}")
                decisions.append({"action": "auto_approve_standard_rfc", "id": cr["id"], "title": cr["title"]})

    return {"findings": findings, "decisions": decisions, "context": {"change_mgmt_ran_at": datetime.now(timezone.utc).isoformat(), "pending_rfcs": len(pending)}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

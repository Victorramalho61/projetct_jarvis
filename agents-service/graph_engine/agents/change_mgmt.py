"""Change Management (ITIL) — gerencia RFCs. Motor: Python puro."""
from datetime import datetime, timedelta, timezone

from graph_engine.tools.supabase_tools import insert_change_request, log_event, query_change_requests, update_change_request


_EMERGENCY_SLA_HOURS = 4
_NORMAL_SLA_HOURS = 48
_STANDARD_SLA_HOURS = 72

# Prefixos de commit → (change_type, priority)
_COMMIT_TYPE_MAP = [
    (("hotfix!", "fix!:", "emergency:"),        ("emergency", "critical")),
    (("feat:", "feature:", "refactor!:"),        ("normal",    "medium")),
    (("fix:", "bug:", "perf:", "patch:"),        ("standard",  "low")),
    (("chore:", "docs:", "style:", "ci:", "test:", "refactor:", "build:"), ("standard", "low")),
]


def _classify_commit(message: str) -> tuple[str, str]:
    """Retorna (change_type, priority) baseado no prefixo do commit."""
    lower = message.lower().strip()
    for prefixes, result in _COMMIT_TYPE_MAP:
        if any(lower.startswith(p) for p in prefixes):
            return result
    return "normal", "medium"


def _sla_deadline(change_type: str, now: datetime) -> str:
    hours = {"emergency": _EMERGENCY_SLA_HOURS, "standard": _STANDARD_SLA_HOURS}.get(change_type, _NORMAL_SLA_HOURS)
    return (now + timedelta(hours=hours)).isoformat()


def _auto_create_from_commits(now: datetime, decisions: list) -> int:
    """Cria RFCs para commits recentes que ainda não têm uma RFC registrada."""
    try:
        from graph_engine.tools.github_tools import list_recent_commits
        commits = list_recent_commits(limit=20)
        if not commits:
            return 0
    except Exception:
        return 0

    # Coleta SHAs já registrados no context dos change_requests existentes
    from db import get_supabase
    db = get_supabase()
    existing = db.table("change_requests").select("context").execute().data or []
    known_shas = {
        row.get("context", {}).get("commit_sha")
        for row in existing
        if row.get("context") and row["context"].get("commit_sha")
    }

    created = 0
    for c in commits:
        sha = c.get("sha", "")
        if not sha or sha in known_shas:
            continue

        message = c.get("message", "").strip() or "Commit sem mensagem"
        change_type, priority = _classify_commit(message)
        title = f"[Deploy] {message[:120]}"
        files_list = c.get('files', [])
        file_names = [f["filename"] if isinstance(f, dict) else str(f) for f in files_list[:10]]
        description = (
            f"Commit: {sha[:12]}\n"
            f"Autor: {c.get('author', 'N/A')}\n"
            f"Data: {c.get('date', 'N/A')}\n"
            f"Arquivos alterados: {', '.join(file_names) or 'N/A'}"
        )
        rollback = f"git revert {sha[:12]} && docker compose -f /opt/jarvis/docker-compose.yml up -d --build"

        insert_change_request(
            title=title,
            description=description,
            change_type=change_type,
            priority=priority,
            requested_by="change_mgmt_agent",
            rollback_plan=rollback,
            sla_deadline=_sla_deadline(change_type, now),
            context={"commit_sha": sha, "author": c.get("author"), "date": c.get("date"), "files": c.get("files", [])},
        )
        known_shas.add(sha)
        created += 1
        log_event("info", "change_mgmt", f"RFC criada automaticamente: {title[:80]}", f"SHA: {sha[:12]} | Tipo: {change_type}")
        decisions.append({"action": "auto_create_rfc", "sha": sha[:12], "title": title[:80], "type": change_type})

    return created


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

    # Auto-criar RFCs a partir de commits recentes sem RFC registrada
    created = _auto_create_from_commits(now, decisions)

    pending = query_change_requests(status="pending")

    for cr in pending:
        created_at = datetime.fromisoformat(cr["created_at"].replace("Z", "+00:00"))
        age_hours = (now - created_at).total_seconds() / 3600
        priority = cr.get("priority", "normal")
        change_type = cr.get("change_type", "normal")

        sla = {"emergency": _EMERGENCY_SLA_HOURS, "standard": _STANDARD_SLA_HOURS}.get(change_type, _NORMAL_SLA_HOURS)
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

    # Aprovação automática de RFCs do tipo 'standard' com prioridade 'low'
    for cr in pending:
        if cr.get("change_type") == "standard" and cr.get("priority") == "low":
            if cr.get("requested_by", "").endswith("-agent"):
                update_change_request(cr["id"], "approved", approved_by="change_mgmt_agent")
                log_event("info", "change_mgmt", f"RFC padrão aprovada automaticamente: {cr['title']}")
                decisions.append({"action": "auto_approve_standard_rfc", "id": cr["id"], "title": cr["title"]})

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "change_mgmt_ran_at": now.isoformat(),
            "pending_rfcs": len(pending),
            "rfcs_created": created,
        },
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

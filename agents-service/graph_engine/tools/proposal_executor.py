"""
Utilitário compartilhado para agentes processarem proposals aprovadas por humanos
vindas da inbox (agent_messages com proposal_id no contexto).
"""
import logging
from datetime import datetime, timezone
from typing import Callable

logger = logging.getLogger(__name__)


def _load_proposal(db, proposal_id: str) -> dict | None:
    rows = (
        db.table("improvement_proposals")
        .select("*")
        .eq("id", proposal_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def _mark_applied(db, proposal_id: str, note: str = "") -> None:
    db.table("improvement_proposals").update({
        "validation_status": "applied",
        "applied": True,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "implementation_error": note[:500] if note else None,
    }).eq("id", proposal_id).execute()


def _mark_failed(db, proposal_id: str, error: str) -> None:
    db.table("improvement_proposals").update({
        "validation_status": "implementation_failed",
        "applied": False,
        "implementation_error": error[:500],
    }).eq("id", proposal_id).execute()


def process_inbox_proposals(
    agent_name: str,
    db,
    handler: Callable[[dict, dict], tuple[bool, str]],
    decisions: list | None = None,
    limit: int = 500,
) -> int:
    """
    Lê proposals pendentes da inbox do agente e processa cada uma.

    handler(proposal, message) -> (success: bool, note: str)
      - success=True  → marca como applied
      - success=False → marca como implementation_failed com note como erro

    Retorna a quantidade de proposals processadas.
    """
    from graph_engine.tools.supabase_tools import get_pending_messages, mark_message_processed

    messages = get_pending_messages(agent_name)
    pending = [m for m in messages if m.get("context", {}).get("proposal_id")][:limit]
    processed = 0

    for msg in pending:
        proposal_id = msg["context"]["proposal_id"]
        proposal = _load_proposal(db, proposal_id)

        if not proposal:
            mark_message_processed(msg["id"])
            continue

        # Já resolvida por outro ciclo
        if proposal.get("validation_status") in ("applied", "implementation_failed", "rejected"):
            mark_message_processed(msg["id"])
            continue

        try:
            success, note = handler(proposal, msg)
        except Exception as exc:
            success, note = False, f"Erro interno em {agent_name}: {exc}"
            logger.error("%s: erro ao processar proposal %s: %s", agent_name, proposal_id, exc)

        if success:
            _mark_applied(db, proposal_id, note)
            logger.info("%s: proposal aplicada — %s", agent_name, proposal.get("title", "")[:60])
        else:
            _mark_failed(db, proposal_id, note)
            logger.warning("%s: proposal falhou — %s | %s", agent_name, proposal.get("title", "")[:50], note[:60])

        if decisions is not None:
            status = "aplicada" if success else "falhou"
            decisions.append(f"Proposal {status}: {proposal.get('title', '')[:60]}")

        mark_message_processed(msg["id"])
        processed += 1

    return processed

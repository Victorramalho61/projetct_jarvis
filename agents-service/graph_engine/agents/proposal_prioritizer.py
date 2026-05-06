"""
Proposal Prioritizer — priorização diária inteligente de proposals.

Ciclo de trabalho:
1. Busca todas as proposals pending/pending_cto não aplicadas
2. Usa LLM para atribuir score de impacto x esforço a cada uma
3. Atualiza o campo priority com base no score
4. Promove automaticamente proposals críticas sem risco para approved
5. Envia digest diário ao CTO com o ranking e recomendações
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_PRIORITY_LEVELS = ["critical", "high", "medium", "low"]

_EFFORT_SCORE = {"low": 3, "medium": 2, "high": 1, "very_high": 0}
_PRIORITY_SCORE = {"critical": 4, "high": 3, "medium": 2, "low": 1}

_AUTO_APPROVE_TYPES = {"index", "vacuum", "config"}


def _compute_score(p: dict) -> float:
    """Score simples: impacto ponderado por esforço inverso."""
    priority_s = _PRIORITY_SCORE.get(p.get("priority", "medium"), 2)
    effort_s = _EFFORT_SCORE.get(p.get("estimated_effort", "medium"), 2)
    risk_penalty = 0.5 if p.get("risk") in ("high", "critical") else 0
    return priority_s * effort_s - risk_penalty


def _should_auto_approve(p: dict) -> bool:
    """Proposals de baixo risco e tipo auto-executável podem ser auto-aprovadas."""
    return (
        p.get("proposal_type") in _AUTO_APPROVE_TYPES
        and p.get("risk") in ("low", "none", None, "")
        and p.get("validation_status") == "pending_cto"
    )


def run(state: dict) -> dict:
    from graph_engine.llm import get_fast_llm, invoke_llm_with_timeout
    from graph_engine.tools.supabase_tools import send_agent_message, log_event
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []
    db = __import__("db").get_supabase()

    # Busca proposals pendentes (pending + pending_cto)
    pending = (
        db.table("improvement_proposals")
        .select("id,title,proposal_type,priority,estimated_effort,risk,validation_status,description,source_agent,created_at")
        .in_("validation_status", ["pending", "pending_cto"])
        .eq("applied", False)
        .order("created_at")
        .limit(100)
        .execute()
        .data or []
    )

    if not pending:
        log_event("info", "proposal_prioritizer", "Nenhuma proposal pendente para priorizar")
        return {
            "findings": [{"agent": "proposal_prioritizer", "pending_count": 0}],
            "decisions": ["Nenhuma proposal pendente"],
            "context": {"proposal_prioritizer_run": datetime.now(timezone.utc).isoformat()},
            "next_agent": "END",
        }

    # Recalcula scores e auto-aprova elegíveis
    auto_approved = 0
    score_updates: list[tuple[str, float, str]] = []

    for p in pending:
        score = _compute_score(p)
        score_updates.append((p["id"], score, p.get("priority", "medium")))

        if _should_auto_approve(p):
            try:
                db.table("improvement_proposals").update({
                    "validation_status": "approved",
                    "implementation_error": f"Auto-aprovada pelo prioritizer em {datetime.now(timezone.utc).isoformat()} — baixo risco e tipo seguro",
                }).eq("id", p["id"]).execute()
                decisions.append(f"Auto-aprovada: {p.get('title', '')[:60]}")
                auto_approved += 1
            except Exception as exc:
                logger.warning("proposal_prioritizer: auto-approve %s: %s", p["id"], exc)

    # Reordena por score
    score_updates.sort(key=lambda x: x[1], reverse=True)

    # Atualiza priority das top-N que estão sub-classificadas
    priority_updated = 0
    for rank, (pid, score, current_priority) in enumerate(score_updates):
        new_priority = (
            "critical" if score >= 9 else
            "high"     if score >= 6 else
            "medium"   if score >= 3 else
            "low"
        )
        if new_priority != current_priority:
            try:
                db.table("improvement_proposals").update({
                    "priority": new_priority,
                }).eq("id", pid).execute()
                priority_updated += 1
            except Exception as exc:
                logger.warning("proposal_prioritizer: update priority %s: %s", pid, exc)

    findings.append({
        "agent": "proposal_prioritizer",
        "pending_count": len(pending),
        "auto_approved": auto_approved,
        "priority_updated": priority_updated,
    })

    # Consulta LLM para análise qualitativa das top-10
    top10 = [p for p in pending[:10]]
    top10_summary = "\n".join([
        f"- [{p.get('priority','?').upper()}] {p.get('title','')[:60]} "
        f"(tipo: {p.get('proposal_type','?')}, risco: {p.get('risk','?')}, "
        f"esforço: {p.get('estimated_effort','?')})"
        for p in top10
    ])

    llm_digest = ""
    try:
        llm = get_fast_llm()
        response = invoke_llm_with_timeout(llm, [
            SystemMessage(content=(
                "Você é um gestor de TI experiente. Analise a lista de proposals pendentes "
                "e indique: 1) quais devem ser aprovadas HOJE (máx 3), 2) quais podem esperar, "
                "3) alguma que deveria ser rejeitada. Seja direto e conciso. Português."
            )),
            HumanMessage(content=f"Proposals pendentes ({len(pending)} total):\n{top10_summary}"),
        ], timeout_s=30)
        llm_digest = response.content
    except Exception as exc:
        logger.warning("proposal_prioritizer: LLM digest: %s", exc)
        llm_digest = f"Análise LLM indisponível: {exc}"

    # Envia digest ao CTO
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    digest = (
        f"📋 PRIORIZAÇÃO DIÁRIA — {now_str}\n\n"
        f"Proposals pendentes: {len(pending)}\n"
        f"Auto-aprovadas (baixo risco): {auto_approved}\n"
        f"Prioridades re-calibradas: {priority_updated}\n\n"
        f"Top proposals para revisão:\n{top10_summary}\n\n"
        f"Recomendação:\n{llm_digest[:500]}"
    )

    try:
        send_agent_message(
            from_agent="proposal_prioritizer",
            to_agent="cto",
            message=digest,
            context={
                "pending_count": len(pending),
                "auto_approved": auto_approved,
                "priority_updated": priority_updated,
            },
        )
        decisions.append("Digest de priorização enviado ao CTO")
    except Exception as exc:
        logger.warning("proposal_prioritizer: digest CTO: %s", exc)

    log_event("info", "proposal_prioritizer",
              f"Priorização concluída: {len(pending)} pendentes, {auto_approved} auto-aprovadas")

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "proposal_prioritizer_run": datetime.now(timezone.utc).isoformat(),
            "pending_count": len(pending),
            "auto_approved": auto_approved,
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

"""
Proposal Analysis Agent — triagem automática de proposals pendentes.

Classifica criticidade, tema principal e sugere ação para cada proposal
via keyword matching. Não usa LLM — determinístico e sem latência.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_CRITICAL_KEYWORDS = ["security", "breach", "outage", "critical", "urgent", "vulnerability"]
_HIGH_PRIORITY_THEMES = ["performance", "scalability", "compliance", "cost", "debt"]
_ACTION_SUGGESTIONS = {
    "security":    "Escalar para revisão imediata do time de segurança",
    "performance": "Iniciar benchmark e plano de otimização",
    "cost":        "Engajar análise de custo-benefício com stakeholders",
    "compliance":  "Encaminhar para avaliação jurídica/compliance",
    "default":     "Atribuir ao responsável de produto para triagem em 48h",
}


def run(state: dict) -> dict:
    findings = []
    decisions = []

    proposals = state.get("pending_proposals", [])
    if not proposals:
        try:
            from db import get_supabase
            db = get_supabase()
            result = (
                db.table("improvement_proposals")
                .select("id,title,description,priority,status")
                .in_("status", ["pending", "pending_cto"])
                .limit(100)
                .execute()
            )
            proposals = result.data or []
        except Exception as exc:
            logger.warning("proposal_analysis_agent: erro ao buscar proposals: %s", exc)

    if not proposals:
        findings.append({"type": "analysis_skip", "reason": "nenhuma proposal pendente"})
        return {"findings": findings, "decisions": decisions}

    priority_order = {"critical": 0, "high": 1, "medium": 2}

    for proposal in proposals:
        content = f"{proposal.get('title', '')} {proposal.get('description', '')}".lower()
        proposal_id = proposal.get("id", "unknown")

        critical_score = sum(1 for word in _CRITICAL_KEYWORDS if word in content)
        if critical_score >= 3:
            severity = "critical"
        elif critical_score >= 1:
            severity = "high"
        else:
            severity = "medium"

        detected_themes = [t for t in _HIGH_PRIORITY_THEMES if t in content]
        theme = detected_themes[0] if detected_themes else "general"

        action_key = next((k for k in _ACTION_SUGGESTIONS if k != "default" and k in content), "default")

        findings.append({
            "type": "proposal_classified",
            "proposal_id": proposal_id,
            "detected_theme": theme,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        decisions.append({
            "type": "proposal_action",
            "proposal_id": proposal_id,
            "action": _ACTION_SUGGESTIONS[action_key],
            "assigned_priority": severity,
            "justification": (
                f"Keywords críticas: {[w for w in _CRITICAL_KEYWORDS if w in content]}"
                if critical_score else f"Tema detectado: {theme}"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    decisions.sort(key=lambda x: priority_order.get(x["assigned_priority"], 3))
    logger.info("proposal_analysis_agent: %d proposals classificadas", len(proposals))
    return {"findings": findings, "decisions": decisions}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

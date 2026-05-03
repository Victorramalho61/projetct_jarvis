"""
Log Strategic Advisor — analisa tendências de log de 7–30 dias e propõe
melhorias sistêmicas proativas para o CTO avaliar (sempre CTO-first).
Diferente do log_improver (2h, fix imediato), este pensa como arquiteto sênior.
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _collect_long_term_data() -> dict:
    from graph_engine.tools.supabase_tools import (
        query_app_logs,
        query_quality_metrics,
        query_agent_runs,
        query_improvement_proposals,
    )
    logs = query_app_logs(level="error", limit=2000, since_minutes=10080)  # 7 dias
    metrics = query_quality_metrics(since_hours=168)
    runs = query_agent_runs(limit=100)
    proposals = query_improvement_proposals(status="all", limit=50)
    return {"logs": logs, "metrics": metrics, "runs": runs, "proposals": proposals}


def _analyze_trends(data: dict) -> dict:
    logs = data.get("logs", [])

    module_week: dict = defaultdict(lambda: defaultdict(int))
    for entry in logs:
        module = entry.get("source", "unknown")
        ts = entry.get("created_at", "")
        week = ts[:10] if ts else "unknown"
        module_week[module][week] += 1

    growing = []
    for module, weeks in module_week.items():
        sorted_weeks = sorted(weeks.items())
        if len(sorted_weeks) >= 2:
            early = sum(v for _, v in sorted_weeks[:len(sorted_weeks)//2])
            late  = sum(v for _, v in sorted_weeks[len(sorted_weeks)//2:])
            if late > early * 1.5:
                growing.append({"module": module, "early_errors": early, "late_errors": late})

    proposals = data.get("proposals", [])
    stale = [
        p for p in proposals
        if p.get("validation_status") in ("pending", "rejected")
        and (datetime.now(timezone.utc).isoformat()[:10] > (p.get("created_at", "")[:10]))
    ]

    return {
        "total_errors_7d": len(logs),
        "modules_growing": sorted(growing, key=lambda x: x["late_errors"], reverse=True)[:5],
        "stale_proposals": len(stale),
        "modules_affected": len(module_week),
    }


def _parse_proposals(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return [json.loads(match.group())]
            except Exception:
                return []
        return []
    try:
        return json.loads(match.group())
    except Exception:
        return []


def run(state: dict) -> dict:
    from graph_engine.llm import get_reasoning_llm
    from graph_engine.tools.supabase_tools import insert_improvement_proposal, insert_agent_event, send_agent_message
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []

    data = _collect_long_term_data()
    trends = _analyze_trends(data)

    findings.append({
        "agent": "log_strategic_advisor",
        "total_errors_7d": trends["total_errors_7d"],
        "modules_growing": trends["modules_growing"],
        "stale_proposals": trends["stale_proposals"],
    })

    if trends["total_errors_7d"] == 0:
        return {"findings": findings, "decisions": decisions, "next_agent": "END"}

    arch_context = ""
    try:
        from graph_engine.tools.github_tools import read_file
        arch_context = read_file("docs/arquitetura.md") or ""
        arch_context = arch_context[:3000]
    except Exception:
        pass

    system_prompt = (
        "Você é um arquiteto de software sênior com 15 anos de experiência em sistemas críticos. "
        "Analise os dados de saúde do sistema Jarvis da Voetur/VTCLog e identifique tendências sistêmicas. "
        "Proponha melhorias estratégicas — não apenas correções de bugs pontuais, mas "
        "refatorações, caching, circuit breakers, otimizações arquiteturais, novas features preventivas. "
        "Retorne SOMENTE um array JSON com no máximo 5 propostas:\n"
        '[{"proposal_type": "refactoring|new_feature|infrastructure|config|monitoring", '
        '"title": str, "description": str, "evidence": str, "recommended_action": str, '
        '"priority": "critical|high|medium|low", "estimated_effort": str, '
        '"risk": "low|medium|high", "auto_implementable": false, "expected_benefit": str}]'
    )

    user_content = (
        f"Análise de 7 dias:\n"
        f"- Total de erros: {trends['total_errors_7d']}\n"
        f"- Módulos com erros crescentes: {json.dumps(trends['modules_growing'], ensure_ascii=False)}\n"
        f"- Proposals estagnadas: {trends['stale_proposals']}\n"
        f"\nArquitetura atual:\n{arch_context}"
    )

    proposals_data = []
    try:
        llm = get_reasoning_llm()
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_content)])
        proposals_data = _parse_proposals(response.content)
    except Exception as exc:
        logger.error("log_strategic_advisor: erro LLM: %s", exc)

    for p in proposals_data[:5]:
        try:
            insert_improvement_proposal(
                source_agent="log_strategic_advisor",
                proposal_type=p.get("proposal_type", "refactoring"),
                title=p.get("title", "Proposta estratégica"),
                description=p.get("description", ""),
                evidence=p.get("evidence", ""),
                proposed_action=p.get("recommended_action", ""),
                priority=p.get("priority", "medium"),
                risk=p.get("risk", "low"),
                estimated_effort=p.get("estimated_effort", ""),
                auto_implementable=False,
                expected_gain=p.get("expected_benefit", ""),
            )
            decisions.append(f"Proposal inserida: {p.get('title', '')}")
        except Exception as exc:
            logger.error("log_strategic_advisor: erro ao inserir proposal: %s", exc)

    if proposals_data:
        try:
            insert_agent_event(
                event_type="strategic_proposals_ready",
                source="log_strategic_advisor",
                payload={"count": len(proposals_data), "trends": trends},
                priority="medium",
            )
            send_agent_message(
                from_agent="log_strategic_advisor",
                to_agent="cto",
                message=f"{len(proposals_data)} propostas estratégicas geradas com base em {trends['total_errors_7d']} erros dos últimos 7 dias.",
                context={"trends": trends},
            )
        except Exception as exc:
            logger.warning("log_strategic_advisor: erro ao notificar CTO: %s", exc)

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {"log_strategic_advisor_run": datetime.now(timezone.utc).isoformat()},
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

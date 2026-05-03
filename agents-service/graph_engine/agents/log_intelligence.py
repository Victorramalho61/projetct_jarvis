"""
Log Intelligence — análise profunda de logs com janela de 72h.
Complementa o log_scanner (2h, spikes) e o log_strategic_advisor (7 dias, tendências).
Foco: correlação de erros entre múltiplos serviços no mesmo período de tempo,
detecção de falhas em cascata e identificação de causa raiz inter-serviços.
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_WINDOW_MINUTES = 72 * 60  # 72 horas


def _collect_data() -> dict:
    from graph_engine.tools.supabase_tools import query_app_logs, query_quality_metrics
    logs = query_app_logs(level="error", limit=1000, since_minutes=_WINDOW_MINUTES)
    metrics = query_quality_metrics(since_hours=72)
    return {"logs": logs, "metrics": metrics}


def _correlate_errors(logs: list[dict]) -> list[dict]:
    """Agrupa erros por janelas de 5 minutos e detecta co-ocorrências entre serviços."""
    time_buckets: dict = defaultdict(lambda: defaultdict(list))

    for entry in logs:
        ts = entry.get("created_at", "")
        if not ts:
            continue
        # Trunca para janela de 5 minutos
        bucket = ts[:15] + "0:00"
        source = entry.get("source", "unknown")
        time_buckets[bucket][source].append(entry.get("message", ""))

    cascades = []
    for bucket, services in time_buckets.items():
        if len(services) >= 2:
            services_list = list(services.keys())
            total_errors = sum(len(v) for v in services.values())
            cascades.append({
                "timestamp_window": bucket,
                "services_affected": services_list,
                "services_count": len(services_list),
                "total_errors": total_errors,
                "sample_messages": {
                    svc: msgs[:2] for svc, msgs in services.items()
                },
            })

    return sorted(cascades, key=lambda x: x["services_count"] * x["total_errors"], reverse=True)[:10]


def _parse_proposals(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except Exception:
        return []


def run(state: dict) -> dict:
    from graph_engine.llm import get_reasoning_llm
    from graph_engine.tools.supabase_tools import insert_improvement_proposal, send_agent_message
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []

    data = _collect_data()
    logs = data.get("logs", [])

    if not logs:
        findings.append({"agent": "log_intelligence", "status": "sem_logs_72h"})
        return {"findings": findings, "decisions": decisions, "next_agent": "END"}

    cascades = _correlate_errors(logs)

    findings.append({
        "agent": "log_intelligence",
        "total_errors_72h": len(logs),
        "cascade_events": len(cascades),
        "top_cascade": cascades[0] if cascades else None,
    })

    if not cascades:
        return {"findings": findings, "decisions": decisions, "next_agent": "END"}

    system_prompt = (
        "Você é um engenheiro de confiabilidade de site (SRE) sênior especialista em análise de sistemas distribuídos. "
        "Analise os eventos de falha em cascata detectados entre múltiplos serviços e identifique: "
        "1. Qual serviço é provavelmente a causa raiz das falhas em cascata "
        "2. Por que a falha se propaga para outros serviços "
        "3. Como corrigir ou prevenir a cascata "
        "Retorne SOMENTE um array JSON com até 3 diagnósticos:\n"
        '[{"root_cause_service": str, "cascade_pattern": str, "description": str, '
        '"recommended_fix": str, "priority": "critical|high|medium", '
        '"auto_implementable": false}]'
    )

    cascade_summary = json.dumps(cascades[:5], ensure_ascii=False, default=str)

    proposals_data = []
    try:
        llm = get_reasoning_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Eventos de cascata detectados (72h):\n{cascade_summary}"),
        ])
        proposals_data = _parse_proposals(response.content)
    except Exception as exc:
        logger.error("log_intelligence: erro LLM: %s", exc)

    for p in proposals_data[:3]:
        try:
            insert_improvement_proposal(
                source_agent="log_intelligence",
                proposal_type="monitoring",
                title=f"Cascata detectada: {p.get('root_cause_service', 'múltiplos serviços')}",
                description=p.get("description", ""),
                evidence=f"Cascata em {len(cascades)} janelas de 5min nas últimas 72h",
                proposed_action=p.get("recommended_fix", ""),
                priority=p.get("priority", "high"),
                risk="medium",
                auto_implementable=False,
            )
            decisions.append(f"Diagnóstico de cascata inserido: {p.get('root_cause_service', '')}")
        except Exception as exc:
            logger.error("log_intelligence: erro ao inserir proposal: %s", exc)

    if cascades and cascades[0]["services_count"] >= 3:
        try:
            send_agent_message(
                from_agent="log_intelligence",
                to_agent="cto",
                message=f"Cascata crítica detectada: {cascades[0]['services_count']} serviços afetados simultaneamente em {cascades[0]['timestamp_window']}",
                context={"top_cascade": cascades[0], "total_cascades": len(cascades)},
            )
        except Exception as exc:
            logger.warning("log_intelligence: erro ao notificar CTO: %s", exc)

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {
            "log_intelligence_run": datetime.now(timezone.utc).isoformat(),
            "cascades_detected": len(cascades),
        },
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

"""Docker Intelligence — analisa logs Docker e sugere otimizações. Motor: Ollama."""
import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from graph_engine.llm import get_reasoning_llm
from graph_engine.tools.docker_tools import get_container_logs, get_container_stats, list_containers
from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um especialista em Docker e infraestrutura analisando métricas de containers.
Receberá logs e estatísticas de containers Docker do sistema Jarvis.
Identifique problemas e oportunidades de otimização.
Retorne um array JSON de propostas com os campos: proposal_type, title, description, proposed_action, priority, estimated_effort, risk, auto_implementable.
Responda APENAS com o JSON, sem explicações."""


def run(state: dict) -> dict:
    containers = list_containers()
    if not containers:
        return {"findings": [], "context": {"docker_intel_ran_at": datetime.now(timezone.utc).isoformat()}}

    # Coleta dados de todos os containers
    container_data = []
    for c in containers[:8]:  # Limita a 8 containers para não exceder contexto do LLM
        if isinstance(c, dict) and "error" not in c:
            stats = get_container_stats(c["name"])
            recent_logs = get_container_logs(c["name"], lines=30, since_minutes=30)
            container_data.append({
                "name": c["name"],
                "stats": stats,
                "recent_log_excerpt": recent_logs[-1000:] if len(recent_logs) > 1000 else recent_logs,
            })

    try:
        llm = get_reasoning_llm()
        prompt = f"DADOS DOS CONTAINERS:\n{json.dumps(container_data, indent=2, default=str)[:5000]}"
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        raw = response.content if hasattr(response, "content") else str(response)
        start = raw.find("[")
        end = raw.rfind("]") + 1
        proposals_raw = json.loads(raw[start:end]) if start >= 0 else []
    except Exception as e:
        log.warning("docker_intel LLM error: %s", e)
        proposals_raw = []

    submitted = []
    for p in proposals_raw:
        try:
            result = insert_improvement_proposal(
                source_agent="docker_intel",
                proposal_type=p.get("proposal_type", "infrastructure"),
                title=p.get("title", "Otimização Docker"),
                description=p.get("description", ""),
                proposed_action=p.get("proposed_action", ""),
                priority=p.get("priority", "low"),
                estimated_effort=p.get("estimated_effort", "hours"),
                risk=p.get("risk", "low"),
                auto_implementable=p.get("auto_implementable", False),
                affected_files=["docker-compose.yml"],
            )
            submitted.append(result)
        except Exception as e:
            log.warning("docker_intel insert error: %s", e)

    if submitted:
        log_event("info", "docker_intel", f"{len(submitted)} propostas de otimização Docker geradas")

    return {
        "findings": [{"type": "docker_intel_analysis", "proposals_count": len(submitted)}],
        "context": {"docker_intel_ran_at": datetime.now(timezone.utc).isoformat()},
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

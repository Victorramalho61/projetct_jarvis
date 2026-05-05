"""Docker Intelligence — analisa logs Docker e sugere otimizações. Motor: Ollama."""
import json
import logging
import re
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from graph_engine.llm import get_reasoning_llm
from graph_engine.tools.docker_tools import get_container_logs, get_container_stats, list_containers, restart_container
from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event

log = logging.getLogger(__name__)


def _extract_container(text: str) -> str | None:
    m = re.search(r"jarvis-[\w-]+-\d+", text)
    return m.group(0) if m else None


def _handle_proposal(proposal: dict, _msg: dict) -> tuple[bool, str]:
    """Handler para proposals Docker aprovadas por humanos."""
    ptype = proposal.get("proposal_type", "")
    action = proposal.get("proposed_action", "") or ""
    title = proposal.get("title", "")

    _RESTART_TYPES = {"container_update", "container_compatibility", "container_integration"}
    should_restart = ptype in _RESTART_TYPES and "restart" in action.lower()

    if should_restart:
        container = _extract_container(title) or _extract_container(action)
        if container:
            try:
                result = restart_container(container)
                if result.get("success"):
                    return True, f"Container {container} reiniciado com sucesso"
                return False, f"Falha ao reiniciar {container}: {result.get('error', 'desconhecido')}"
            except Exception as exc:
                return False, f"Erro ao reiniciar container: {exc}"

    # Advisory: proposta analisada e documentada
    note = (action[:200] if action else title[:200])
    return True, f"Recomendação Docker registrada: {note}"

_SYSTEM_PROMPT = """Você é um especialista em Docker e infraestrutura analisando métricas de containers.
Receberá logs e estatísticas de containers Docker do sistema Jarvis.
Identifique problemas e oportunidades de otimização.
Retorne um array JSON de propostas com os campos: proposal_type, title, description, proposed_action, priority, estimated_effort, risk, auto_implementable.
Responda APENAS com o JSON, sem explicações."""


def run(state: dict) -> dict:
    from db import get_supabase
    from graph_engine.tools.proposal_executor import process_inbox_proposals

    db = get_supabase()
    decisions: list = []
    processed = process_inbox_proposals("docker_intel", db, _handle_proposal, decisions)
    if processed:
        log.info("docker_intel: %d proposals da inbox processadas", processed)

    containers = list_containers()
    if not containers:
        return {"findings": [], "decisions": decisions, "context": {"docker_intel_ran_at": datetime.now(timezone.utc).isoformat()}}

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
        "decisions": decisions,
        "context": {"docker_intel_ran_at": datetime.now(timezone.utc).isoformat()},
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

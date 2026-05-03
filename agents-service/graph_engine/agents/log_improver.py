"""Log Improvement Proposer — diagnóstica causas e gera propostas estruturadas. Motor: Ollama."""
import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from graph_engine.state import JarvisState
from graph_engine.llm import get_reasoning_llm
from graph_engine.tools.github_tools import read_file
from graph_engine.tools.supabase_tools import (
    insert_improvement_proposal,
    log_event,
    query_app_logs,
    send_agent_message,
)

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um engenheiro de software sênior analisando logs do sistema Jarvis.
O sistema usa FastAPI (Python 3.11), React, Supabase, Docker Compose e Kong.

Sua tarefa: analisar padrões de erro e propor melhorias concretas e práticas.

Para cada padrão de erro, gere UMA proposta JSON com esta estrutura exata:
{
  "proposal_type": "code_fix" | "config_change" | "new_agent" | "infrastructure" | "monitoring",
  "title": "título conciso",
  "description": "diagnóstico da causa-raiz em português",
  "proposed_action": "o que fazer exatamente, de forma específica",
  "affected_files": ["lista de arquivos/serviços afetados"],
  "priority": "low" | "medium" | "high" | "critical",
  "estimated_effort": "minutes" | "hours" | "days",
  "risk": "low" | "medium" | "high",
  "auto_implementable": true | false
}

auto_implementable=true apenas quando a ação é simples e reversível (ex: adicionar um monitored_system, ajustar config).
Responda com um array JSON válido de propostas. Nada mais."""


def _enrich_context(findings: list) -> str:
    """Adiciona contexto relevante aos findings para o LLM."""
    context_parts = [f"FINDINGS ({len(findings)} padrões de erro):\n{json.dumps(findings, indent=2, default=str)}"]

    # Tenta buscar arquivo de arquitetura para contexto
    arch = read_file("docs/arquitetura.md")
    if not arch.startswith("Erro") and not arch.startswith("GitHub"):
        context_parts.append(f"\nARQUITETURA DO SISTEMA (resumo):\n{arch[:2000]}")

    return "\n\n".join(context_parts)


def _parse_proposals(text: str) -> list[dict]:
    """Extrai JSON do response do LLM."""
    try:
        # Tenta encontrar array JSON no texto
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    # Tenta encontrar objeto JSON único
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0:
            return [json.loads(text[start:end])]
    except json.JSONDecodeError:
        pass
    return []


def _receive_findings(state: JarvisState) -> dict:
    findings = state.get("findings", [])
    context = state.get("context", {})
    # Busca também findings passados via mensagem pelo log_scanner
    from graph_engine.tools.supabase_tools import get_pending_messages, mark_message_processed
    messages = get_pending_messages("log_improver")
    extra_findings = []
    for msg in messages:
        content = msg.get("content", {})
        if content.get("trigger") == "log_findings":
            extra_findings.extend(content.get("findings", []))
            mark_message_processed(msg["id"])
    all_findings = findings + extra_findings
    return {"findings": all_findings, "context": {**context, "improver_findings_count": len(all_findings)}}


def _llm_diagnose(state: JarvisState) -> dict:
    findings = state.get("findings", [])
    if not findings:
        return {"context": {**state.get("context", {}), "proposals_raw": []}}

    context_text = _enrich_context(findings)
    try:
        llm = get_reasoning_llm()
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=context_text),
        ])
        raw = response.content if hasattr(response, "content") else str(response)
        proposals = _parse_proposals(raw)
    except Exception as e:
        log.warning("log_improver LLM error: %s", e)
        proposals = []
        log_event("warning", "log_improver", f"Erro ao chamar LLM: {e}")

    return {"context": {**state.get("context", {}), "proposals_raw": proposals}}


def _submit_to_cto(state: JarvisState) -> dict:
    proposals_raw = state.get("context", {}).get("proposals_raw", [])
    submitted = []

    for p in proposals_raw:
        try:
            result = insert_improvement_proposal(
                source_agent="log_improver",
                proposal_type=p.get("proposal_type", "code_fix"),
                title=p.get("title", "Proposta sem título"),
                description=p.get("description", ""),
                proposed_action=p.get("proposed_action", ""),
                priority=p.get("priority", "medium"),
                estimated_effort=p.get("estimated_effort", "hours"),
                risk=p.get("risk", "medium"),
                auto_implementable=p.get("auto_implementable", False),
                affected_files=p.get("affected_files", []),
                source_findings=state.get("findings", [])[:3],
            )
            submitted.append(result)
        except Exception as e:
            log.warning("Erro ao inserir proposta: %s", e)

    if submitted:
        send_agent_message(
            from_agent="log_improver",
            to_agent="cto",
            content={"trigger": "improvement_proposal", "proposals": [p.get("id") for p in submitted if p], "count": len(submitted)},
        )
        log_event("info", "log_improver", f"{len(submitted)} propostas enviadas ao CTO")

    return {"decisions": [{"action": "proposals_submitted", "count": len(submitted)}]}


def build():
    graph = StateGraph(JarvisState)
    graph.add_node("receive_findings", _receive_findings)
    graph.add_node("llm_diagnose", _llm_diagnose)
    graph.add_node("submit_to_cto", _submit_to_cto)
    graph.add_edge(START, "receive_findings")
    graph.add_edge("receive_findings", "llm_diagnose")
    graph.add_edge("llm_diagnose", "submit_to_cto")
    graph.add_edge("submit_to_cto", END)
    return graph.compile()

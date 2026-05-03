"""Docs Agent — atualiza documentação após deploys/mudanças. Motor: Ollama."""
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from graph_engine.llm import get_reasoning_llm
from graph_engine.tools.github_tools import list_recent_commits, read_file, update_file
from graph_engine.tools.supabase_tools import log_event

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um technical writer especializado em documentação de sistemas.
Receberá o conteúdo atual de um arquivo de documentação e uma lista de commits recentes.
Identifique o que mudou e atualize a documentação de forma concisa e precisa em português.
Mantenha a formatação Markdown existente. Retorne APENAS o conteúdo atualizado do arquivo, sem explicações adicionais."""


def _update_doc(file_path: str, commits: list[dict]) -> dict:
    current = read_file(file_path)
    if current.startswith("Erro") or current.startswith("GitHub"):
        return {"file": file_path, "updated": False, "reason": current}

    commit_summary = "\n".join(f"- {c.get('date','')[:10]} [{c.get('sha','')}] {c.get('message','')}" for c in commits[:10])
    prompt = f"DOCUMENTAÇÃO ATUAL:\n{current[:4000]}\n\nCOMMITS RECENTES:\n{commit_summary}\n\nAtualize a documentação para refletir as mudanças."

    try:
        llm = get_reasoning_llm()
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        updated_content = response.content if hasattr(response, "content") else str(response)
        result = update_file(file_path, updated_content, f"docs: auto-update by docs-agent [{datetime.now(timezone.utc).strftime('%Y-%m-%d')}]")
        return {"file": file_path, "updated": result.get("success", False)}
    except Exception as e:
        log.warning("docs agent LLM error for %s: %s", file_path, e)
        return {"file": file_path, "updated": False, "reason": str(e)}


def run(state: dict) -> dict:
    commits = list_recent_commits(limit=10)
    if not commits or (len(commits) == 1 and "error" in commits[0]):
        return {"findings": [{"type": "docs_skip", "reason": "GitHub não configurado"}]}

    results = []
    for doc_path in ["docs/arquitetura.md", "CLAUDE.md"]:
        result = _update_doc(doc_path, commits)
        results.append(result)
        if result.get("updated"):
            log_event("info", "docs_agent", f"Documentação atualizada: {doc_path}")

    return {"findings": [{"type": "docs_update", "results": results}], "context": {"docs_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

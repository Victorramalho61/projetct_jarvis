"""
Quality Code Backend — revisa código Python/FastAPI dos serviços alterados,
detecta problemas estáticos e faz revisão LLM de diffs. Acionado pelo cicd_monitor.
"""
import ast
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_DANGEROUS_PATTERNS = [
    (re.compile(r'exec\s*\('), "uso de exec()"),
    (re.compile(r'eval\s*\('), "uso de eval()"),
    (re.compile(r'os\.system\s*\('), "os.system() — use subprocess"),
    (re.compile(r'(?i)password\s*=\s*["\'][^"\']{4,}'), "senha hardcoded"),
    (re.compile(r'(?i)secret\s*=\s*["\'][^"\']{4,}'), "secret hardcoded"),
    (re.compile(r'except\s*:\s*\n\s*pass'), "except genérico com pass"),
    (re.compile(r'except\s+Exception\s*:\s*\n\s*pass'), "except Exception com pass"),
    (re.compile(r'f["\'].*SELECT.*{.*}.*["\']', re.IGNORECASE), "SQL com f-string — risco injection"),
]


def _static_analysis(code: str, filename: str) -> list[dict]:
    issues = []

    for pattern, description in _DANGEROUS_PATTERNS:
        if pattern.search(code):
            issues.append({"file": filename, "severity": "high", "issue": description})

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines = (node.end_lineno or 0) - node.lineno
                if lines > 60:
                    issues.append({
                        "file": filename,
                        "severity": "medium",
                        "issue": f"Função '{node.name}' muito longa ({lines} linhas) — candidata a refatoração",
                    })
    except SyntaxError as exc:
        issues.append({"file": filename, "severity": "critical", "issue": f"Erro de sintaxe: {exc}"})

    return issues


def _fetch_changed_python_files() -> list[dict]:
    try:
        from graph_engine.tools.github_tools import list_recent_commits, get_file_diff
        commits = list_recent_commits(limit=3) or []
        files_seen: set = set()
        results = []
        for commit in commits:
            for f in commit.get("files", []):
                fname = f.get("filename", "")
                if fname.endswith(".py") and fname not in files_seen:
                    files_seen.add(fname)
                    diff = get_file_diff(fname, commit.get("sha", "")) or ""
                    content = f.get("patch", diff) or ""
                    if content:
                        results.append({"filename": fname, "content": content[:3000], "sha": commit.get("sha")})
        return results
    except Exception as exc:
        logger.warning("quality_code_backend: não foi possível buscar arquivos: %s", exc)
        return []


def _parse_llm_issues(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except Exception:
        return []


def run(state: dict) -> dict:
    from graph_engine.llm import get_reasoning_llm
    from graph_engine.tools.supabase_tools import insert_improvement_proposal, insert_agent_event
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []
    all_issues = []

    changed_files = _fetch_changed_python_files()
    if not changed_files:
        findings.append({"agent": "quality_code_backend", "status": "sem_alterações_recentes"})
        return {"findings": findings, "decisions": decisions, "next_agent": "END"}

    for file_data in changed_files:
        fname = file_data["filename"]
        content = file_data["content"]
        static_issues = _static_analysis(content, fname)
        all_issues.extend(static_issues)

    findings.append({
        "agent": "quality_code_backend",
        "files_analyzed": len(changed_files),
        "static_issues": len(all_issues),
        "critical_issues": [i for i in all_issues if i.get("severity") == "critical"],
    })

    if all_issues:
        critical = [i for i in all_issues if i.get("severity") == "critical"]
        if critical:
            try:
                insert_agent_event(
                    event_type="code_quality_critical",
                    source="quality_code_backend",
                    payload={"issues": critical, "files": [f["filename"] for f in changed_files]},
                    priority="critical",
                )
            except Exception as exc:
                logger.warning("quality_code_backend: erro ao inserir evento crítico: %s", exc)

    diff_summary = "\n\n".join(
        f"Arquivo: {f['filename']}\n{f['content'][:1500]}" for f in changed_files[:3]
    )

    system_prompt = (
        "Você é um code reviewer sênior especializado em Python e FastAPI. "
        "Analise os diffs de código e identifique problemas: performance, segurança, manutenibilidade, testes faltantes. "
        "Retorne SOMENTE um array JSON:\n"
        '[{"file": str, "issue": str, "severity": "critical|high|medium|low", '
        '"suggestion": str, "auto_implementable": false}]'
    )

    llm_issues = []
    try:
        llm = get_reasoning_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Diffs recentes:\n{diff_summary}"),
        ])
        llm_issues = _parse_llm_issues(response.content)
    except Exception as exc:
        logger.error("quality_code_backend: erro LLM: %s", exc)

    all_combined = all_issues + llm_issues
    for issue in all_combined[:10]:
        sev = issue.get("severity", "medium")
        if sev in ("critical", "high", "medium"):
            try:
                insert_improvement_proposal(
                    source_agent="quality_code_backend",
                    proposal_type="refactoring",
                    title=f"Code Quality: {issue.get('issue', 'Problema detectado')[:80]}",
                    description=issue.get("suggestion", issue.get("issue", "")),
                    evidence=f"Arquivo: {issue.get('file', 'N/A')}",
                    priority=sev if sev != "critical" else "critical",
                    risk="low",
                    auto_implementable=False,
                )
                decisions.append(f"Proposal inserida: {issue.get('issue', '')[:50]}")
            except Exception as exc:
                logger.error("quality_code_backend: erro ao inserir proposal: %s", exc)

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {"quality_code_backend_run": datetime.now(timezone.utc).isoformat()},
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

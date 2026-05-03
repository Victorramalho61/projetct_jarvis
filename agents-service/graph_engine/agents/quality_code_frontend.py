"""
Quality Code Frontend — revisa alterações em TypeScript/React (TSX/TS/CSS),
detecta anti-patterns de performance, acessibilidade e tipagem. Acionado pelo cicd_monitor.
"""
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_TS_PATTERNS = [
    (re.compile(r':\s*any\b'), "tipo 'any' detectado — use tipagem explícita", "medium"),
    (re.compile(r'useEffect\s*\([^,]+\)(?!\s*,)'), "useEffect sem dependency array", "high"),
    (re.compile(r'console\.(log|warn|error)\s*\('), "console.log em produção", "low"),
    (re.compile(r'(?<!\w)(\d{4,})\b'), "número mágico hardcoded — use constante", "low"),
    (re.compile(r'<img(?![^>]*alt=)'), "tag <img> sem atributo alt — acessibilidade", "medium"),
    (re.compile(r'onClick=\{[^}]*\}\s*(?!.*aria-)'), "elemento clicável sem aria-label", "low"),
    (re.compile(r'style=\{\{[^}]{100,}\}\}'), "estilo inline longo — use className/tailwind", "low"),
    (re.compile(r'@ts-ignore'), "@ts-ignore detectado — corrija o tipo", "high"),
    (re.compile(r'@ts-nocheck'), "@ts-nocheck detectado — remova", "high"),
]

_HEAVY_IMPORTS = ["lodash", "moment", "rxjs", "d3", "three", "antd", "material-ui"]


def _analyze_ts_file(content: str, filename: str) -> list[dict]:
    issues = []
    for pattern, description, severity in _TS_PATTERNS:
        if pattern.search(content):
            issues.append({"file": filename, "severity": severity, "issue": description})

    for lib in _HEAVY_IMPORTS:
        if f"from '{lib}'" in content or f'from "{lib}"' in content:
            issues.append({
                "file": filename,
                "severity": "medium",
                "issue": f"Import de biblioteca pesada '{lib}' — verifique tree-shaking",
            })

    line_count = content.count("\n")
    if line_count > 350:
        issues.append({
            "file": filename,
            "severity": "medium",
            "issue": f"Componente com {line_count} linhas — candidato a split em componentes menores",
        })

    return issues


def _fetch_changed_frontend_files() -> list[dict]:
    try:
        from graph_engine.tools.github_tools import list_recent_commits, get_file_diff
        commits = list_recent_commits(limit=3) or []
        files_seen: set = set()
        results = []
        for commit in commits:
            for f in commit.get("files", []):
                fname = f.get("filename", "")
                if any(fname.endswith(ext) for ext in (".tsx", ".ts", ".css", ".scss")) and fname not in files_seen:
                    files_seen.add(fname)
                    content = f.get("patch", "") or ""
                    if content:
                        results.append({"filename": fname, "content": content[:3000], "sha": commit.get("sha")})
        return results
    except Exception as exc:
        logger.warning("quality_code_frontend: não foi possível buscar arquivos: %s", exc)
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
    from graph_engine.tools.supabase_tools import insert_improvement_proposal
    from langchain_core.messages import SystemMessage, HumanMessage

    findings = []
    decisions = []
    all_issues = []

    changed_files = _fetch_changed_frontend_files()
    if not changed_files:
        findings.append({"agent": "quality_code_frontend", "status": "sem_alterações_recentes"})
        return {"findings": findings, "decisions": decisions, "next_agent": "END"}

    for file_data in changed_files:
        static_issues = _analyze_ts_file(file_data["content"], file_data["filename"])
        all_issues.extend(static_issues)

    findings.append({
        "agent": "quality_code_frontend",
        "files_analyzed": len(changed_files),
        "static_issues": len(all_issues),
        "high_severity": [i for i in all_issues if i.get("severity") == "high"],
    })

    diff_summary = "\n\n".join(
        f"Arquivo: {f['filename']}\n{f['content'][:1500]}" for f in changed_files[:3]
    )

    system_prompt = (
        "Você é um senior frontend developer especializado em React, TypeScript e performance web. "
        "Analise os diffs de código frontend e identifique problemas: "
        "performance, acessibilidade, tipagem, boas práticas React. "
        "Retorne SOMENTE um array JSON:\n"
        '[{"file": str, "issue": str, "severity": "critical|high|medium|low", '
        '"suggestion": str}]'
    )

    llm_issues = []
    try:
        llm = get_reasoning_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Diffs frontend:\n{diff_summary}"),
        ])
        llm_issues = _parse_llm_issues(response.content)
    except Exception as exc:
        logger.error("quality_code_frontend: erro LLM: %s", exc)

    all_combined = all_issues + llm_issues
    for issue in all_combined[:8]:
        sev = issue.get("severity", "medium")
        if sev in ("critical", "high", "medium"):
            try:
                insert_improvement_proposal(
                    source_agent="quality_code_frontend",
                    proposal_type="refactoring",
                    title=f"Frontend Quality: {issue.get('issue', '')[:80]}",
                    description=issue.get("suggestion", issue.get("issue", "")),
                    evidence=f"Arquivo: {issue.get('file', 'N/A')}",
                    priority=sev if sev != "critical" else "critical",
                    risk="low",
                    auto_implementable=False,
                )
                decisions.append(f"Proposal frontend inserida: {issue.get('issue', '')[:50]}")
            except Exception as exc:
                logger.error("quality_code_frontend: erro ao inserir proposal: %s", exc)

    return {
        "findings": findings,
        "decisions": decisions,
        "context": {"quality_code_frontend_run": datetime.now(timezone.utc).isoformat()},
        "next_agent": "END",
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

"""Frontend Agent — auditoria de componentes React. Motor: Python puro."""
from datetime import datetime, timezone

from graph_engine.tools.supabase_tools import insert_improvement_proposal, log_event, query_app_logs


_FRONTEND_ERROR_PATTERNS = ["TypeError", "ReferenceError", "SyntaxError", "ChunkLoadError", "Network Error", "Cannot read properties"]


def run(state: dict) -> dict:
    findings = []
    logs = query_app_logs(level="error", since_minutes=1440, limit=200)

    # Detecta erros de frontend nos logs de aplicação
    frontend_errors = [l for l in logs if any(p in ((l.get("message") or "") + (l.get("detail") or "")) for p in _FRONTEND_ERROR_PATTERNS)]

    if len(frontend_errors) > 5:
        insert_improvement_proposal(
            source_agent="frontend_agent",
            proposal_type="code_fix",
            title=f"Erros de frontend recorrentes ({len(frontend_errors)}x em 24h)",
            description=f"Detectados {len(frontend_errors)} erros de JavaScript/TypeScript. Padrões mais comuns: {set(e.get('message','')[:40] for e in frontend_errors[:5])}",
            proposed_action="Revisar componentes React que geram esses erros e adicionar error boundaries adequados.",
            priority="medium",
            estimated_effort="hours",
            risk="low",
            auto_implementable=False,
            source_findings=frontend_errors[:5],
        )
        findings.append({"type": "frontend_errors", "count": len(frontend_errors)})
        log_event("warning", "frontend_agent", f"{len(frontend_errors)} erros de frontend nas últimas 24h")

    return {"findings": findings, "context": {"frontend_agent_ran_at": datetime.now(timezone.utc).isoformat()}}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

"""Code Security — valida scripts antes de execução. Motor: Python puro."""
from graph_engine.tools.code_tools import analyze_python_code, check_security_patterns, validate_script_imports
from graph_engine.tools.supabase_tools import insert_security_alert, log_event, query_agents


def scan_all_scripts() -> list[dict]:
    """Varre todos os agentes do tipo script no banco e valida o código."""
    agents = query_agents(enabled=True)
    results = []
    for agent in agents:
        if agent.get("agent_type") != "script":
            continue
        code = agent.get("config", {}).get("code", "")
        if not code:
            continue
        agent_name = agent.get("name", agent.get("id"))
        security_issues = check_security_patterns(code)
        import_check = validate_script_imports(code)
        syntax = analyze_python_code(code)
        has_issues = bool(security_issues) or not import_check["approved"] or not syntax["valid_syntax"]
        if has_issues:
            desc = f"Agente '{agent_name}' tem problemas de segurança: "
            details = [i["description"] for i in security_issues]
            if not import_check["approved"]:
                details.append(f"Imports bloqueados: {import_check['blocked_imports']}")
            if not syntax["valid_syntax"]:
                details.append(f"Sintaxe inválida: {syntax['syntax_error']}")
            insert_security_alert("high", "code_security", desc + "; ".join(details), f"agent:{agent.get('id')}")
            log_event("warning", "code_security", f"Problemas de segurança no agente {agent_name}", "; ".join(details))
        results.append({"agent_id": agent.get("id"), "agent_name": agent_name, "approved": not has_issues, "issues": details if has_issues else []})
    return results


def run(state: dict) -> dict:
    results = scan_all_scripts()
    failed = [r for r in results if not r["approved"]]
    return {
        "findings": [{"type": "code_security_scan", "results": results, "failed_count": len(failed)}],
        "context": {"code_security_scanned": len(results), "issues_found": len(failed)},
    }


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

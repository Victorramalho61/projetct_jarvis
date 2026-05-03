"""Fix Validator — valida correções propostas via análise AST. Motor: Python puro."""
from graph_engine.tools.code_tools import analyze_python_code, check_security_patterns, validate_script_imports
from graph_engine.tools.supabase_tools import log_event, update_improvement_proposal


def validate_proposal(proposal: dict) -> dict:
    """Valida uma proposta de tipo code_fix tecnicamente."""
    code = proposal.get("proposed_action", "")
    result = {"proposal_id": proposal.get("id"), "approved": True, "issues": []}

    # Verifica sintaxe
    analysis = analyze_python_code(code)
    if not analysis["valid_syntax"]:
        result["approved"] = False
        result["issues"].append(f"Sintaxe inválida: {analysis['syntax_error']}")

    # Verifica padrões perigosos
    security_issues = check_security_patterns(code)
    if security_issues:
        result["approved"] = False
        result["issues"].extend([f"{i['description']}" for i in security_issues])

    # Valida imports
    import_check = validate_script_imports(code)
    if not import_check["approved"]:
        result["approved"] = False
        result["issues"].append(f"Imports bloqueados: {import_check['blocked_imports']}")

    return result


def run(state: dict) -> dict:
    findings = state.get("findings", [])
    decisions = []

    for finding in findings:
        if finding.get("type") == "improvement_proposal" and finding.get("proposal", {}).get("proposal_type") == "code_fix":
            proposal = finding["proposal"]
            validation = validate_proposal(proposal)
            if validation["approved"]:
                log_event("info", "fix_validator", f"Proposta aprovada: {proposal.get('title')}")
                decisions.append({"action": "approve_fix", "proposal_id": proposal.get("id"), "reason": "Código validado com sucesso"})
            else:
                reason = "; ".join(validation["issues"])
                log_event("warning", "fix_validator", f"Proposta rejeitada: {proposal.get('title')}", reason)
                if proposal.get("id"):
                    update_improvement_proposal(proposal["id"], "rejected", f"Fix Validator: {reason}")
                decisions.append({"action": "reject_fix", "proposal_id": proposal.get("id"), "reason": reason})

    return {"decisions": decisions}


def build():
    from graph_engine.agents.base import build_deterministic_agent
    return build_deterministic_agent(run)

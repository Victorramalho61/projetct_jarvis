"""Fix Validator — valida correções propostas via análise AST. Motor: Python puro."""
from graph_engine.tools.code_tools import analyze_python_code, check_security_patterns, validate_script_imports
from graph_engine.tools.supabase_tools import log_event, update_improvement_proposal


def _handle_proposal(proposal: dict, _msg: dict) -> tuple[bool, str]:
    """Valida código de propostas code_fix/refactoring aprovadas por humanos."""
    code = proposal.get("proposed_fix") or proposal.get("proposed_action") or ""
    affected = proposal.get("affected_files") or []

    if not code or not code.strip():
        return True, "Proposta advisory reconhecida — sem código para validar, implementação manual"

    # Se não parece código Python (sem newlines, keywords, etc.), tratar como advisory
    python_indicators = ["def ", "class ", "import ", "from ", "return ", "if ", "for ", "while ", "try:", "\n    "]
    if not any(ind in code for ind in python_indicators):
        return True, f"Proposta advisory registrada: {code[:100]}"

    analysis = analyze_python_code(code)
    if not analysis.get("valid_syntax", True):
        return False, f"Código com sintaxe inválida: {analysis.get('syntax_error', 'erro desconhecido')}"

    security_issues = check_security_patterns(code)
    if security_issues:
        issues_str = "; ".join(i.get("description", "") for i in security_issues[:3])
        return False, f"Código bloqueado por padrões de segurança: {issues_str}"

    import_check = validate_script_imports(code)
    if not import_check.get("approved", True):
        return False, f"Imports bloqueados: {import_check.get('blocked_imports', [])}"

    files_str = ", ".join(str(f) for f in affected[:3]) if affected else "arquivo não especificado"
    return True, f"Código validado — implementar manualmente em: {files_str}"


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
    from db import get_supabase
    from graph_engine.tools.proposal_executor import process_inbox_proposals

    db = get_supabase()
    decisions: list = []

    # Processa proposals aprovadas por humanos vindas da inbox
    processed = process_inbox_proposals("fix_validator", db, _handle_proposal, decisions)
    if processed:
        log_event("info", "fix_validator", f"{processed} proposals da inbox processadas")

    # Valida code_fix vindas do pipeline de análise (comportamento original)
    for finding in state.get("findings", []):
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

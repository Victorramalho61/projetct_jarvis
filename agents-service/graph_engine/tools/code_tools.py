"""Ferramentas de an�lise est�tica de c�digo Python."""
import ast
import re


DANGEROUS_PATTERNS = [
    (r"\beval\s*\(", "eval() detectado"),
    (r"\bexec\s*\(", "exec() detectado"),
    (r"\b__import__\s*\(", "__import__() detectado"),
    (r"\bsubprocess\b", "subprocess detectado"),
    (r"\bos\.system\s*\(", "os.system() detectado"),
    (r"\bos\.popen\s*\(", "os.popen() detectado"),
    (r"\bopen\s*\(.*['\"]w", "abertura de arquivo para escrita detectada"),
    (r"(?i)(password|secret|token|key)\s*=\s*['\"][^'\"]{8,}", "poss�vel credencial hardcoded"),
]


def analyze_python_code(code: str) -> dict:
    """Analisa c�digo Python via AST � retorna erros de sintaxe e m�tricas b�sicas."""
    result = {"valid_syntax": True, "syntax_error": None, "num_lines": len(code.splitlines()), "imports": [], "functions": [], "classes": []}
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    result["imports"].extend(a.name for a in node.names)
                else:
                    result["imports"].append(node.module or "")
            elif isinstance(node, ast.FunctionDef):
                result["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                result["classes"].append(node.name)
    except SyntaxError as e:
        result["valid_syntax"] = False
        result["syntax_error"] = str(e)
    return result


def check_security_patterns(code: str) -> list[dict]:
    """Verifica padr�es perigosos no c�digo � retorna lista de alertas."""
    alerts = []
    for pattern, description in DANGEROUS_PATTERNS:
        matches = re.findall(pattern, code)
        if matches:
            alerts.append({"severity": "high", "pattern": pattern, "description": description, "occurrences": len(matches)})
    return alerts


def extract_imports(code: str) -> list[str]:
    """Extrai lista de m�dulos importados."""
    try:
        tree = ast.parse(code)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        return list(set(imports))
    except Exception:
        return []


ALLOWED_STDLIB = {
    "json", "datetime", "os", "re", "math", "collections", "itertools",
    "functools", "typing", "time", "uuid", "hashlib", "base64", "urllib",
    "http", "logging", "traceback", "copy", "dataclasses",
}
ALLOWED_THIRD_PARTY = {"httpx", "supabase", "jwt", "pydantic"}


def validate_script_imports(code: str) -> dict:
    """Valida se imports de script s�o permitidos pela pol�tica de seguran�a."""
    imports = extract_imports(code)
    blocked = [i for i in imports if i not in ALLOWED_STDLIB and i not in ALLOWED_THIRD_PARTY and not i.startswith("_")]
    return {"approved": len(blocked) == 0, "blocked_imports": blocked, "allowed_imports": [i for i in imports if i in ALLOWED_STDLIB or i in ALLOWED_THIRD_PARTY]}

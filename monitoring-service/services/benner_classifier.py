"""Classifica erros Benner em categorias para o motor RPA."""
import re

# Padrões regex → categoria (ordem importa: mais específico primeiro)
_PATTERNS: list[tuple[str, list[str]]] = [
    ("auth_expirada", [
        r"\b401\b", r"\b403\b", r"unauthorized", r"token.*expir",
        r"credencial.*inv[aá]lida", r"acesso.*negado",
    ]),
    ("timeout_rede", [
        r"\btimeout\b", r"connection.*refused", r"unreachable",
        r"timed?.?out", r"network.*error", r"socket.*error",
    ]),
    ("fornecedor_nao_localizado", [
        r"fornecedor n[aã]o (encontrado|informado|localizado)",
        r"supplier.*not.*found", r"fornecedor.*null",
    ]),
    ("fee_pendente", [
        r"fee.*n[aã]o est[aá] pago", r"fee.*pendente",
        r"taxa.*n[aã]o.*paga", r"fee.*ausente",
    ]),
    ("reserva_nao_encontrada", [
        r"reserva n[aã]o encontrada", r"booking.*not.*found",
        r"CODIGORESERVA.*null", r"n[uú]mero.*reserva.*inv[aá]lid",
    ]),
    ("xml_malformado", [
        r"xml.*inv[aá]lid", r"parse.*error", r"malformed",
        r"invalid.*xml", r"unexpected.*token",
    ]),
    ("dados_incompletos", [
        r"campo obrigat[oó]rio", r"not null", r"missing.*field",
        r"campo.*vazio", r"valor.*obrigat[oó]rio",
    ]),
]

_COMPILED: list[tuple[str, list[re.Pattern]]] = [
    (cat, [re.compile(p, re.IGNORECASE) for p in patterns])
    for cat, patterns in _PATTERNS
]


def classify(mensagem: str | None, tipo_erro: int | None = None) -> str:
    """Retorna categoria do erro. Fallback: 'outros'."""
    texto = mensagem or ""
    for categoria, compiled in _COMPILED:
        for pat in compiled:
            if pat.search(texto):
                return categoria
    return "outros"


# Labels legíveis para o frontend
CATEGORIA_LABEL: dict[str, str] = {
    "auth_expirada":          "Auth Expirada",
    "timeout_rede":           "Timeout / Rede",
    "fornecedor_nao_localizado": "Fornecedor não localizado",
    "fee_pendente":           "Fee pendente",
    "reserva_nao_encontrada": "Reserva não encontrada",
    "xml_malformado":         "XML malformado",
    "dados_incompletos":      "Dados incompletos",
    "outros":                 "Outros",
}

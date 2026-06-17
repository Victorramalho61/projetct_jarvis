"""Classifica erros Benner em categorias para o motor RPA.

Padrões derivados de análise real de 987 erros acumulados em 2026-06.
Ordem importa: mais específico primeiro para evitar falsos positivos.
"""
import re

_PATTERNS: list[tuple[str, list[str]]] = [
    # ── Crash de DLL — maior grupo (680+ erros) ─────────────────────────
    ("crash_dll", [
        r"access violation.*TurVendas\.dll",
        r"TurVendas\.dll.*access violation",
        r"access violation.*module.*TurVendas",
    ]),

    # ── Integração Envision — SearchUser falha (28 erros Ordem Serviço) ─
    ("envision_usuario", [
        r"Envision\.SearchUser",
        r"GetBackOfficeIdToUser",
        r"ConverterServicoParaPnrs.*SearchUser",
    ]),

    # ── Cliente não identificado no PNR (111+ erros) ─────────────────────
    ("cliente_nao_identificado", [
        r"c[oó]digo do cliente n[aã]o informado",
        r"cliente n[aã]o informado",
        r"cliente n[aã]o encontrado",
        r"GetCliente.*Erro.*cliente",
        r"ObterCliente.*cliente n[aã]o",
        r"MontarPnr.*ObterCliente",
    ]),

    # ── Contrato do fornecedor ausente (3+ erros) ────────────────────────
    ("contrato_nao_localizado", [
        r"n[aã]o foi poss[ií]vel localizar o contrato",
        r"localizar o contrato do fornecedor",
        r"contrato.*n[aã]o (encontrado|localizado)",
    ]),

    # ── Fornecedor não encontrado (60+ erros — todos os subtipos) ────────
    ("fornecedor_nao_localizado", [
        r"fornecedor.*n[aã]o (encontrado|informado|localizado)",
        r"Fornecedor do tipo.*n[aã]o encontrado",
        r"n[aã]o foi poss[ií]vel encontrar um fornecedor",
        r"Fornecedor com o (nome|apelido).*n[aã]o encontrado",
        r"supplier.*not.*found",
        r"BuscarFornecedorTerrestre.*n[aã]o foi poss[ií]vel encontrar",
    ]),

    # ── Fee / taxa pendente ───────────────────────────────────────────────
    ("fee_pendente", [
        r"fee.*n[aã]o est[aá] pago", r"fee.*pendente",
        r"taxa.*n[aã]o.*paga", r"fee.*ausente",
    ]),

    # ── Localizador de assento/bagagem ausente ────────────────────────────
    ("localizador_ausente", [
        r"n[aã]o foi informado o localizador",
        r"localizador.*assento",
        r"localizador.*bagagem",
    ]),

    # ── Referência nula / tipo inválido (.NET exceptions) ────────────────
    ("null_reference", [
        r"Value cannot be null",
        r"Object reference not set to an instance",
        r"Input string was not in a correct format",
        r"Parameter name: source",
    ]),

    # ── Autenticação / permissão ─────────────────────────────────────────
    ("auth_expirada", [
        r"\b401\b", r"\b403\b", r"unauthorized",
        r"token.*expir", r"credencial.*inv[aá]lida",
    ]),

    # ── Timeout / rede ───────────────────────────────────────────────────
    ("timeout_rede", [
        r"\btimeout\b", r"connection.*refused", r"unreachable",
        r"timed?.?out", r"network.*error", r"socket.*error",
    ]),

    # ── Reserva não encontrada ───────────────────────────────────────────
    ("reserva_nao_encontrada", [
        r"reserva n[aã]o encontrada", r"booking.*not.*found",
    ]),

    # ── XML malformado ────────────────────────────────────────────────────
    ("xml_malformado", [
        r"xml.*inv[aá]lid", r"parse.*error", r"malformed",
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
    "crash_dll":               "Crash TurVendas.dll",
    "envision_usuario":        "Envision — usuário não encontrado",
    "cliente_nao_identificado":"Cliente não identificado",
    "contrato_nao_localizado": "Contrato não localizado",
    "fornecedor_nao_localizado":"Fornecedor não localizado",
    "fee_pendente":            "Fee pendente",
    "localizador_ausente":     "Localizador ausente",
    "null_reference":          "Referência nula (.NET)",
    "auth_expirada":           "Auth expirada",
    "timeout_rede":            "Timeout / Rede",
    "reserva_nao_encontrada":  "Reserva não encontrada",
    "xml_malformado":          "XML malformado",
    "outros":                  "Outros",
}

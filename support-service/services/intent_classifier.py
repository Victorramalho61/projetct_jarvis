import re
from enum import Enum


class Intent(str, Enum):
    OPEN_TICKET = "open_ticket"
    CHECK_STATUS = "check_status"
    LIST_TICKETS = "list_tickets"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    UNKNOWN = "unknown"


_OPEN_KEYWORDS = [
    "abrir", "criar", "novo chamado", "preciso de ajuda", "problema",
    "não consigo", "nao consigo", "erro", "solicitação", "solicitacao",
    "solicitar", "quero abrir", "não funciona", "nao funciona",
    "parou de funcionar", "travou", "não abre", "nao abre",
    "não liga", "nao liga", "help", "ajuda",
]

_CHECK_KEYWORDS = [
    "status", "andamento", "como está", "como esta", "atualização",
    "atualizacao", "chamado", "ticket", "protocolo", "meu chamado",
]

_LIST_KEYWORDS = [
    "listar", "meus chamados", "ver todos", "quais", "abertos",
    "todos os chamados", "lista",
]

_YES_KEYWORDS = [
    "sim", "1", "s", "yes", "pode", "ok", "confirma", "confirmo",
    "isso", "certo", "correto", "confirmar",
]

_NO_KEYWORDS = [
    "não", "nao", "2", "n", "no", "cancelar", "voltar", "desistir",
    "cancela", "cancelo",
]

_TICKET_ID_RE = re.compile(r"#(\d+)")


def classify(text: str, state: str = "idle") -> Intent:
    normalized = text.strip().lower()

    # In confirmation states, map "1"/"2" directly
    if state in ("confirming_ticket",):
        if normalized in ("1", "sim", "s", "yes", "pode", "ok", "confirma", "confirmo"):
            return Intent.CONFIRM_YES
        if normalized in ("2", "não", "nao", "n", "no", "cancelar", "voltar"):
            return Intent.CONFIRM_NO

    # In ticket selection state, a digit selects a ticket (treat as check_status)
    if state == "awaiting_ticket_selection":
        if normalized.isdigit():
            return Intent.CHECK_STATUS

    # Ticket ID shorthand (#NNNN)
    if _TICKET_ID_RE.search(normalized):
        return Intent.CHECK_STATUS

    for kw in _LIST_KEYWORDS:
        if kw in normalized:
            return Intent.LIST_TICKETS

    for kw in _CHECK_KEYWORDS:
        if kw in normalized:
            return Intent.CHECK_STATUS

    for kw in _OPEN_KEYWORDS:
        if kw in normalized:
            return Intent.OPEN_TICKET

    for kw in _YES_KEYWORDS:
        if normalized == kw:
            return Intent.CONFIRM_YES

    for kw in _NO_KEYWORDS:
        if normalized == kw:
            return Intent.CONFIRM_NO

    return Intent.UNKNOWN

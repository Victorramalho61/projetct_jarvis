"""Handlers por categoria de erro Benner.

Cada handler recebe o erro (dict da tabela benner_erros) e uma conexão SQL Server
(pyodbc.Connection) e retorna HandlerResult.

ATIVAÇÃO: estes handlers só executam quando o executor.py for agendado no scheduler.
Atualmente o scheduler NÃO inclui o job benner_rpa — ver executor.py para ativar.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HandlerResult:
    success: bool
    detail: str
    action_taken: str = ""


# ── utilitário SQL ────────────────────────────────────────────────────────────

def _reset_para_retry(conn, benner_handle: int) -> bool:
    """Atualiza BB_LOGINTEGRACOES para forçar reprocessamento pelo Benner.

    NOTA: verificar qual valor numérico de SITUACAO representa "pendente para retry"
    nesta instalação Benner. Query diagnóstico:
        SELECT DISTINCT SITUACAO, COUNT(*) FROM BB_LOGINTEGRACOES GROUP BY SITUACAO
    Substituir o valor 3 abaixo pelo código correto se necessário.
    """
    SITUACAO_PENDENTE = 3  # TODO: confirmar com DBA Benner se necessário
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE BB_LOGINTEGRACOES SET SITUACAO = ?, DATAREENVIO = GETDATE() WHERE HANDLE = ?",
            (SITUACAO_PENDENTE, benner_handle),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        logger.error("_reset_para_retry handle=%d: %s", benner_handle, exc)
        return False


# ── handlers ──────────────────────────────────────────────────────────────────

def handle_timeout_rede(erro: dict, conn) -> HandlerResult:
    """Erros de rede/timeout — retry direto via reset de SITUACAO."""
    ok = _reset_para_retry(conn, erro["benner_handle"])
    if ok:
        return HandlerResult(success=True, detail="SITUACAO resetado para retry", action_taken="sql_retry")
    return HandlerResult(success=False, detail="Falha ao atualizar BB_LOGINTEGRACOES", action_taken="sql_retry")


def handle_fornecedor_nao_localizado(erro: dict, conn) -> HandlerResult:
    """Busca fornecedor por nome/código no cadastro Benner; se único match → atualiza + retry."""
    reserva = erro.get("codigo_reserva") or ""
    if not reserva:
        return HandlerResult(success=False, detail="Sem CODIGORESERVA para lookup", action_taken="lookup_fornecedor")

    # Extrai possível nome de fornecedor da mensagem
    mensagem = erro.get("mensagem") or ""
    match = re.search(r"fornecedor[:\s]+([^\n=>]+)", mensagem, re.IGNORECASE)
    nome_hint = match.group(1).strip()[:50] if match else ""

    try:
        cur = conn.cursor()
        if nome_hint:
            cur.execute(
                "SELECT TOP 5 HANDLE, NOME FROM BB_FORNECEDORES WHERE NOME LIKE ?",
                (f"%{nome_hint}%",),
            )
        else:
            # Sem hint suficiente — não temos como localizar
            return HandlerResult(
                success=False,
                detail="Não foi possível extrair nome do fornecedor da mensagem",
                action_taken="lookup_fornecedor",
            )

        results = cur.fetchall()
        if len(results) == 1:
            # Match único — reset para retry (Benner usará dados da reserva)
            ok = _reset_para_retry(conn, erro["benner_handle"])
            detail = f"Fornecedor único encontrado: {results[0][1]} — retry agendado"
            return HandlerResult(success=ok, detail=detail, action_taken="lookup_fornecedor")
        elif len(results) > 1:
            nomes = ", ".join(r[1] for r in results[:3])
            return HandlerResult(
                success=False,
                detail=f"Múltiplos fornecedores: {nomes} — aguarda seleção manual",
                action_taken="lookup_fornecedor",
            )
        else:
            return HandlerResult(
                success=False,
                detail=f"Fornecedor '{nome_hint}' não encontrado no cadastro",
                action_taken="lookup_fornecedor",
            )
    except Exception as exc:
        logger.error("handle_fornecedor handle=%d: %s", erro["benner_handle"], exc)
        return HandlerResult(success=False, detail=str(exc), action_taken="lookup_fornecedor")


def handle_fee_pendente(erro: dict, conn) -> HandlerResult:
    """Verifica se fee existe no accounting; se sim, tenta associar e retry."""
    reserva = erro.get("codigo_reserva") or ""
    if not reserva:
        return HandlerResult(success=False, detail="Sem CODIGORESERVA", action_taken="lookup_fee")

    try:
        cur = conn.cursor()
        # Verifica existência do fee nas tabelas de accounting
        cur.execute(
            """
            SELECT TOP 1 HANDLE, VALOR, SITUACAO
            FROM BB_SERVICOSACC
            WHERE CODIGORESERVA = ? AND TIPOTAXA = 'FEE'
            """,
            (reserva,),
        )
        row = cur.fetchone()
        if row:
            detail = f"Fee encontrado (HANDLE={row[0]}, VALOR={row[1]}, SITUACAO={row[2]}) — retry"
            ok = _reset_para_retry(conn, erro["benner_handle"])
            return HandlerResult(success=ok, detail=detail, action_taken="lookup_fee")
        return HandlerResult(
            success=False,
            detail=f"Fee não encontrado para reserva {reserva} — requer ação financeira",
            action_taken="lookup_fee",
        )
    except Exception as exc:
        logger.error("handle_fee handle=%d: %s", erro["benner_handle"], exc)
        return HandlerResult(success=False, detail=str(exc), action_taken="lookup_fee")


def handle_reserva_nao_encontrada(erro: dict, conn) -> HandlerResult:
    """Verifica se reserva existe no Benner; se sim, retry; se não, ignora."""
    reserva = erro.get("codigo_reserva") or ""
    if not reserva:
        return HandlerResult(success=False, detail="Sem CODIGORESERVA", action_taken="lookup_reserva")

    try:
        cur = conn.cursor()
        cur.execute("SELECT TOP 1 HANDLE FROM BB_RESERVAS WHERE CODIGO = ?", (reserva,))
        row = cur.fetchone()
        if row:
            ok = _reset_para_retry(conn, erro["benner_handle"])
            return HandlerResult(success=ok, detail=f"Reserva {reserva} existe — retry", action_taken="lookup_reserva")
        return HandlerResult(
            success=False,
            detail=f"Reserva {reserva} não existe mais no Benner — possível cancelamento",
            action_taken="lookup_reserva",
        )
    except Exception as exc:
        logger.error("handle_reserva handle=%d: %s", erro["benner_handle"], exc)
        return HandlerResult(success=False, detail=str(exc), action_taken="lookup_reserva")


def handle_xml_malformado(erro: dict, conn) -> HandlerResult:
    """Tenta sanitização básica do XML e retry."""
    ok = _reset_para_retry(conn, erro["benner_handle"])
    detail = "Reset para retry após XML malformado — Benner reprocessará"
    return HandlerResult(success=ok, detail=detail, action_taken="xml_sanitize")


def handle_auth_expirada(erro: dict, conn) -> HandlerResult:
    """Credenciais expiradas — reset para retry (Benner usa credencial global)."""
    ok = _reset_para_retry(conn, erro["benner_handle"])
    detail = "Reset para retry — verificar credenciais Benner se persistir"
    return HandlerResult(success=ok, detail=detail, action_taken="auth_retry")


def handle_dados_incompletos(erro: dict, conn) -> HandlerResult:
    """Dados faltantes — retry simples; se falhar, aguarda input."""
    ok = _reset_para_retry(conn, erro["benner_handle"])
    detail = "Reset para retry — dados incompletos podem persistir"
    return HandlerResult(success=ok, detail=detail, action_taken="data_retry")


def handle_outros(erro: dict, conn) -> HandlerResult:
    """Fallback — retry simples."""
    ok = _reset_para_retry(conn, erro["benner_handle"])
    return HandlerResult(success=ok, detail="Retry genérico", action_taken="generic_retry")


# ── dispatch ──────────────────────────────────────────────────────────────────

HANDLERS: dict[str, callable] = {
    "timeout_rede":              handle_timeout_rede,
    "fornecedor_nao_localizado": handle_fornecedor_nao_localizado,
    "fee_pendente":              handle_fee_pendente,
    "reserva_nao_encontrada":    handle_reserva_nao_encontrada,
    "xml_malformado":            handle_xml_malformado,
    "auth_expirada":             handle_auth_expirada,
    "dados_incompletos":         handle_dados_incompletos,
    "outros":                    handle_outros,
}

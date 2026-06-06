import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_cards_perfil
from db import get_supabase
from limiter import limiter
from services.crypto import decrypt

router = APIRouter(prefix="/api/cards")
_logger = logging.getLogger(__name__)

_PRODUTOS = {"aereo", "hotel", "locacao"}


class RevealRequest(BaseModel):
    localizador_os: str
    nome_cliente: str
    produto: str          # aereo | hotel | locacao
    data_reserva: date
    nome_pax: str
    fornecedor: str
    valor_transacao: float


def _user_fields(user: dict) -> tuple[str, str, str]:
    uid = user.get("user_id") or user.get("sub") or ""
    login = user.get("email") or user.get("username") or ""
    nome = user.get("display_name") or user.get("name") or login
    return uid, login, nome


def _format_number(numero: str) -> str:
    n = numero.replace(" ", "")
    return " ".join(n[i:i + 4] for i in range(0, len(n), 4))


@router.get("/cards")
@limiter.limit("60/minute")
def list_cards(
    request: Request,
    search: str | None = None,
    user: dict = Depends(get_cards_perfil),
):
    """Lista cartões ativos com 4 últimos dígitos, bandeira e cliente.
    Exposição de card IDs é intencional: colaboradores precisam para solicitar reveal.
    Rate-limited para mitigar enumeração massiva.
    """
    sb = get_supabase()
    q = (
        sb.table("cards_cartoes")
        .select("id, bandeira, numero_final, ativo, cards_clientes(id, nome)")
        .eq("ativo", True)
    )
    if search:
        q = q.ilike("numero_final", f"%{search}%")
    q = q.order("created_at", desc=True)
    res = q.execute()
    return res.data or []


@router.get("/cards/me")
def get_my_perfil(user: dict = Depends(get_cards_perfil)):
    """Retorna o perfil do usuário atual no módulo de cartões."""
    return {"perfil": user.get("cards_perfil")}


@router.post("/cards/{card_id}/reveal")
@limiter.limit("15/minute")
def reveal_card(
    request: Request,
    card_id: str,
    body: RevealRequest,
    user: dict = Depends(get_cards_perfil),
):
    """
    Revela os dados do cartão.
    - Par (cartao_id + localizador_os) inédito: revela imediatamente.
    - Par já usado antes: cria solicitação para aprovação do supervisor.
    - Fechar o popup e reabrir exige preencher todos os dados novamente.
    """
    if body.produto not in _PRODUTOS:
        raise HTTPException(400, "produto inválido: use aereo, hotel ou locacao")

    loc = body.localizador_os.strip()
    if not loc:
        raise HTTPException(400, "localizador_os obrigatório")

    sb = get_supabase()
    uid, login, nome = _user_fields(user)
    ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else None)
    )

    # Busca o cartão
    card = (
        sb.table("cards_cartoes")
        .select("id, cliente_id, bandeira, numero_final, "
                "numero_encrypted, cvv_encrypted, expiracao_encrypted, titular_encrypted, ativo")
        .eq("id", card_id)
        .maybe_single()
        .execute()
    )
    if not card.data:
        raise HTTPException(404, "Cartão não encontrado")
    if not card.data.get("ativo"):
        raise HTTPException(403, "Cartão inativo")

    # Antirreuso atômico via cards_reveal_grants com UNIQUE (cartao_id, localizador_os).
    # INSERT falha com 409 (unique_violation) se par já existe → reuso detectado atomicamente.
    # Elimina a race condition de dois reveals simultâneos para o mesmo par inédito.
    reuse_detected = False
    try:
        sb.table("cards_reveal_grants").insert({
            "cartao_id": card_id,
            "localizador_os": loc,
        }).execute()
    except Exception:
        # Conflito UNIQUE ou erro de DB — ambos tratados como reuso para segurança
        reuse_detected = True

    if reuse_detected:
        # Verifica se já existe solicitação pendente ou aprovada (ainda não consumida)
        pending = (
            sb.table("cards_solicitacoes")
            .select("id, status")
            .eq("cartao_id", card_id)
            .eq("user_id", uid)
            .eq("localizador_os", loc)
            .in_("status", ["pendente", "aprovada"])
            .limit(1)
            .execute()
        )
        if pending.data:
            return {
                "status": "pending_approval",
                "solicitacao_id": pending.data[0]["id"],
                "message": "Solicitação já enviada. Aguardando aprovação do supervisor.",
            }

        sol = sb.table("cards_solicitacoes").insert({
            "cartao_id": card_id,
            "cliente_id": card.data.get("cliente_id"),
            "user_id": uid,
            "user_login": login,
            "user_nome": nome,
            "ip_origem": ip,
            "localizador_os": loc,
            "nome_cliente": body.nome_cliente.strip(),
            "produto": body.produto,
            "data_reserva": str(body.data_reserva),
            "nome_pax": body.nome_pax.strip(),
            "fornecedor": body.fornecedor.strip(),
            "valor_transacao": body.valor_transacao,
        }).execute()

        return {
            "status": "pending_approval",
            "solicitacao_id": sol.data[0]["id"] if sol.data else None,
            "message": "Localizador já utilizado anteriormente para este cartão. Solicitação enviada para aprovação do supervisor.",
        }

    # Par inédito — decripta e revela imediatamente
    try:
        numero = decrypt(card.data["numero_encrypted"])
        cvv = decrypt(card.data["cvv_encrypted"])
        expiracao = decrypt(card.data["expiracao_encrypted"])
        titular = decrypt(card.data["titular_encrypted"])
    except Exception as e:
        _logger.error("Erro ao decriptar cartão %s: tipo=%s", card_id, type(e).__name__)
        raise HTTPException(500, "Erro ao processar dados do cartão")

    # Grava log de acesso
    sb.table("cards_acessos").insert({
        "cartao_id": card_id,
        "cliente_id": card.data.get("cliente_id"),
        "user_id": uid,
        "user_login": login,
        "user_nome": nome,
        "ip_origem": ip,
        "localizador_os": loc,
        "nome_cliente": body.nome_cliente.strip(),
        "produto": body.produto,
        "data_reserva": str(body.data_reserva),
        "nome_pax": body.nome_pax.strip(),
        "fornecedor": body.fornecedor.strip(),
        "valor_transacao": body.valor_transacao,
    }).execute()

    return {
        "status": "revealed",
        "numero": _format_number(numero),
        "cvv": cvv,
        "expiracao": expiracao,
        "titular": titular,
        "bandeira": card.data.get("bandeira"),
    }

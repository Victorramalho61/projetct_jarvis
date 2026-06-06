import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_cards_perfil, require_supervisor
from db import get_supabase
from services.crypto import decrypt

router = APIRouter(prefix="/api/cards")
_logger = logging.getLogger(__name__)

_APPROVAL_EXPIRY_MINUTES = 10


def _format_number(numero: str) -> str:
    n = numero.replace(" ", "")
    return " ".join(n[i:i + 4] for i in range(0, len(n), 4))


@router.get("/approvals")
def list_pending_approvals(_sup: dict = Depends(require_supervisor)):
    """Lista solicitações pendentes de aprovação."""
    sb = get_supabase()
    res = (
        sb.table("cards_solicitacoes")
        .select("*, cards_cartoes(bandeira, numero_final, cards_clientes(nome))")
        .eq("status", "pendente")
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []


@router.get("/approvals/{solicitacao_id}/status")
def get_approval_status(
    solicitacao_id: str,
    user: dict = Depends(get_cards_perfil),
):
    """Polling do colaborador para saber se a solicitação foi aprovada/rejeitada."""
    sb = get_supabase()
    row = (
        sb.table("cards_solicitacoes")
        .select("id, status, motivo_rejeicao, aprovado_em, aprovacao_expira_em, aprovado_por_nome")
        .eq("id", solicitacao_id)
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Solicitação não encontrada")
    return row.data


@router.post("/approvals/{solicitacao_id}/approve")
def approve_request(solicitacao_id: str, sup: dict = Depends(require_supervisor)):
    """Supervisor aprova a solicitação. Colaborador tem 10 minutos para confirmar."""
    sb = get_supabase()
    row = (
        sb.table("cards_solicitacoes")
        .select("id, status")
        .eq("id", solicitacao_id)
        .eq("status", "pendente")
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Solicitação pendente não encontrada")

    now = datetime.now(timezone.utc)
    expira = now + timedelta(minutes=_APPROVAL_EXPIRY_MINUTES)

    sb.table("cards_solicitacoes").update({
        "status": "aprovada",
        "aprovado_por": sup.get("user_id") or sup.get("sub"),
        "aprovado_por_nome": sup.get("display_name") or sup.get("name") or "",
        "aprovado_em": now.isoformat(),
        "aprovacao_expira_em": expira.isoformat(),
    }).eq("id", solicitacao_id).execute()

    return {"ok": True, "expira_em": expira.isoformat()}


class RejectBody(BaseModel):
    motivo: str


@router.post("/approvals/{solicitacao_id}/reject")
def reject_request(
    solicitacao_id: str,
    body: RejectBody,
    sup: dict = Depends(require_supervisor),
):
    """Supervisor rejeita a solicitação com motivo obrigatório."""
    if not body.motivo.strip():
        raise HTTPException(400, "Motivo de rejeição obrigatório")
    sb = get_supabase()
    row = (
        sb.table("cards_solicitacoes")
        .select("id")
        .eq("id", solicitacao_id)
        .eq("status", "pendente")
        .maybe_single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Solicitação pendente não encontrada")
    sb.table("cards_solicitacoes").update({
        "status": "rejeitada",
        "aprovado_por": sup.get("user_id") or sup.get("sub"),
        "aprovado_por_nome": sup.get("display_name") or sup.get("name") or "",
        "aprovado_em": datetime.now(timezone.utc).isoformat(),
        "motivo_rejeicao": body.motivo.strip(),
    }).eq("id", solicitacao_id).execute()
    return {"ok": True}


@router.post("/approvals/{solicitacao_id}/confirm")
def confirm_reveal(
    solicitacao_id: str,
    user: dict = Depends(get_cards_perfil),
):
    """
    Colaborador confirma o reveal após aprovação do supervisor.
    One-time use: marca a solicitação como 'consumida' após revelar.
    """
    uid = user.get("user_id") or user.get("sub") or ""
    sb = get_supabase()

    sol = (
        sb.table("cards_solicitacoes")
        .select("*")
        .eq("id", solicitacao_id)
        .eq("user_id", uid)
        .maybe_single()
        .execute()
    )
    if not sol.data:
        raise HTTPException(404, "Solicitação não encontrada")

    s = sol.data
    match s["status"]:
        case "consumida":
            raise HTTPException(409, "Solicitação já utilizada — dados não podem ser exibidos novamente")
        case "rejeitada":
            raise HTTPException(403, f"Solicitação rejeitada: {s.get('motivo_rejeicao', '')}")
        case "pendente":
            raise HTTPException(400, "Solicitação ainda aguarda aprovação do supervisor")
        case status if status != "aprovada":
            raise HTTPException(400, "Estado inválido da solicitação")

    # Verifica expiração da aprovação
    expira_str = s.get("aprovacao_expira_em")
    if expira_str:
        expira_dt = datetime.fromisoformat(expira_str.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expira_dt:
            raise HTTPException(
                410,
                "Aprovação expirada. Feche o popup e solicite novamente.",
            )

    # Busca e decripta o cartão
    card = (
        sb.table("cards_cartoes")
        .select("bandeira, numero_encrypted, cvv_encrypted, expiracao_encrypted, titular_encrypted")
        .eq("id", s["cartao_id"])
        .maybe_single()
        .execute()
    )
    if not card.data:
        raise HTTPException(404, "Cartão não encontrado")

    try:
        numero = decrypt(card.data["numero_encrypted"])
        cvv = decrypt(card.data["cvv_encrypted"])
        expiracao = decrypt(card.data["expiracao_encrypted"])
        titular = decrypt(card.data["titular_encrypted"])
    except Exception as e:
        _logger.error("Erro ao decriptar via confirm %s: %s", s["cartao_id"], e)
        raise HTTPException(500, "Erro ao processar dados do cartão")

    # Grava log de acesso
    sb.table("cards_acessos").insert({
        "cartao_id": s["cartao_id"],
        "cliente_id": s.get("cliente_id"),
        "user_id": uid,
        "user_login": user.get("email") or user.get("username") or "",
        "user_nome": user.get("display_name") or user.get("name") or "",
        "localizador_os": s["localizador_os"],
        "nome_cliente": s["nome_cliente"],
        "produto": s["produto"],
        "data_reserva": s["data_reserva"],
        "nome_pax": s["nome_pax"],
        "fornecedor": s["fornecedor"],
        "valor_transacao": s["valor_transacao"],
    }).execute()

    # Marca como consumida (one-time)
    sb.table("cards_solicitacoes").update({"status": "consumida"}).eq("id", solicitacao_id).execute()

    return {
        "status": "revealed",
        "numero": _format_number(numero),
        "cvv": cvv,
        "expiracao": expiracao,
        "titular": titular,
        "bandeira": card.data.get("bandeira"),
    }

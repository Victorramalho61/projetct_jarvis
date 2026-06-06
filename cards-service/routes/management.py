import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import require_supervisor
from db import get_supabase
from limiter import limiter
from services.crypto import encrypt

router = APIRouter(prefix="/api/cards")
_logger = logging.getLogger(__name__)

_BANDEIRAS = {"VISA", "MASTER", "ELO", "AMEX", "HIPERCARD"}


class CartaoCreate(BaseModel):
    cliente_id: str
    bandeira: str
    numero: str    # plaintext — criptografado antes de salvar, NUNCA armazenado
    cvv: str
    expiracao: str  # formato MM/AA
    titular: str


class CartaoUpdate(BaseModel):
    bandeira: str | None = None
    cvv: str | None = None
    expiracao: str | None = None
    titular: str | None = None
    ativo: bool | None = None


def _safe(data: dict) -> dict:
    """Remove campos criptografados antes de retornar ao cliente."""
    for f in ("numero_encrypted", "cvv_encrypted", "expiracao_encrypted", "titular_encrypted"):
        data.pop(f, None)
    return data


@router.get("/management")
def list_cards(
    search: str | None = None,
    cliente_id: str | None = None,
    _sup: dict = Depends(require_supervisor),
):
    sb = get_supabase()
    q = sb.table("cards_cartoes").select(
        "id, cliente_id, bandeira, numero_final, ativo, created_at, "
        "cards_clientes(id, nome)"
    )
    if cliente_id:
        q = q.eq("cliente_id", cliente_id)
    if search:
        # Pesquisa pelos 4 dígitos finais
        q = q.ilike("numero_final", f"%{search}%")
    q = q.order("created_at", desc=True)
    res = q.execute()
    return res.data or []


@router.post("/management", status_code=201)
@limiter.limit("30/minute")
def create_card(request: Request, body: CartaoCreate, sup: dict = Depends(require_supervisor)):
    numero_clean = body.numero.replace(" ", "").replace("-", "")
    if len(numero_clean) < 13 or not numero_clean.isdigit():
        raise HTTPException(400, "Número de cartão inválido")
    if body.bandeira.upper() not in _BANDEIRAS:
        raise HTTPException(400, f"Bandeira inválida. Use: {', '.join(_BANDEIRAS)}")

    numero_final = numero_clean[-4:]
    sb = get_supabase()

    cli = (
        sb.table("cards_clientes")
        .select("id")
        .eq("id", body.cliente_id)
        .maybe_single()
        .execute()
    )
    if not cli.data:
        raise HTTPException(404, "Cliente não encontrado")

    try:
        res = sb.table("cards_cartoes").insert({
            "cliente_id": body.cliente_id,
            "bandeira": body.bandeira.upper(),
            "numero_final": numero_final,
            "numero_encrypted": encrypt(numero_clean),
            "cvv_encrypted": encrypt(body.cvv),
            "expiracao_encrypted": encrypt(body.expiracao),
            "titular_encrypted": encrypt(body.titular.strip().upper()),
            "criado_por": sup.get("user_id") or sup.get("sub"),
        }).execute()
    except Exception as e:
        _logger.error("Erro ao cadastrar cartão: %s", type(e).__name__)
        raise HTTPException(500, "Erro ao salvar cartão")

    return _safe(res.data[0]) if res.data else {}


@router.put("/management/{card_id}")
@limiter.limit("30/minute")
def update_card(
    request: Request,
    card_id: str,
    body: CartaoUpdate,
    _sup: dict = Depends(require_supervisor),
):
    sb = get_supabase()
    exists = (
        sb.table("cards_cartoes")
        .select("id")
        .eq("id", card_id)
        .maybe_single()
        .execute()
    )
    if not exists.data:
        raise HTTPException(404, "Cartão não encontrado")

    patch: dict = {}
    if body.bandeira is not None and body.bandeira.strip():
        if body.bandeira.upper() not in _BANDEIRAS:
            raise HTTPException(400, f"Bandeira inválida. Use: {', '.join(_BANDEIRAS)}")
        patch["bandeira"] = body.bandeira.upper()
    if body.cvv is not None and body.cvv.strip():
        patch["cvv_encrypted"] = encrypt(body.cvv)
    if body.expiracao is not None and body.expiracao.strip():
        patch["expiracao_encrypted"] = encrypt(body.expiracao)
    if body.titular is not None and body.titular.strip():
        patch["titular_encrypted"] = encrypt(body.titular.strip().upper())
    if body.ativo is not None:
        patch["ativo"] = body.ativo
    if not patch:
        raise HTTPException(400, "Nenhum campo válido para atualizar")

    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = sb.table("cards_cartoes").update(patch).eq("id", card_id).execute()
    return _safe(res.data[0]) if res.data else {}


@router.delete("/management/{card_id}", status_code=200)
@limiter.limit("30/minute")
def deactivate_card(request: Request, card_id: str, _sup: dict = Depends(require_supervisor)):
    sb = get_supabase()
    res = (
        sb.table("cards_cartoes")
        .update({"ativo": False, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", card_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(404, "Cartão não encontrado")
    return {"ok": True}

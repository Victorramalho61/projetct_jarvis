import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_supervisor
from db import get_supabase

router = APIRouter(prefix="/api/cards")
_logger = logging.getLogger(__name__)


class ClienteCreate(BaseModel):
    nome: str
    cnpj: str | None = None


class ClienteUpdate(BaseModel):
    nome: str | None = None
    cnpj: str | None = None
    ativo: bool | None = None


@router.get("/clients")
def list_clients(_sup: dict = Depends(require_supervisor)):
    sb = get_supabase()
    res = sb.table("cards_clientes").select("*").order("nome").execute()
    return res.data or []


@router.post("/clients", status_code=201)
def create_client(body: ClienteCreate, sup: dict = Depends(require_supervisor)):
    if not body.nome.strip():
        raise HTTPException(400, "Nome obrigatório")
    sb = get_supabase()
    res = sb.table("cards_clientes").insert({
        "nome": body.nome.strip(),
        "cnpj": body.cnpj,
        "criado_por": sup.get("user_id") or sup.get("id") or sup.get("sub"),
    }).execute()
    return res.data[0] if res.data else {}


@router.put("/clients/{client_id}")
def update_client(
    client_id: str,
    body: ClienteUpdate,
    _sup: dict = Depends(require_supervisor),
):
    patch: dict = {}
    if body.nome is not None:
        patch["nome"] = body.nome.strip()
    if body.cnpj is not None:
        patch["cnpj"] = body.cnpj
    if body.ativo is not None:
        patch["ativo"] = body.ativo
    if not patch:
        raise HTTPException(400, "Nenhum campo válido para atualizar")
    sb = get_supabase()
    res = sb.table("cards_clientes").update(patch).eq("id", client_id).execute()
    if not res.data:
        raise HTTPException(404, "Cliente não encontrado")
    return res.data[0]

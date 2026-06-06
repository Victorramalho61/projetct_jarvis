import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_supervisor
from db import get_supabase

router = APIRouter(prefix="/api/cards")
_logger = logging.getLogger(__name__)


class PermissaoBody(BaseModel):
    user_id: str
    user_login: str
    user_nome: str
    perfil: str  # colaborador | supervisor


class PermissaoUpdate(BaseModel):
    perfil: str | None = None   # colaborador | supervisor
    ativo: bool | None = None


@router.get("/permissions")
def list_permissions(_sup: dict = Depends(require_supervisor)):
    sb = get_supabase()
    res = sb.table("cards_permissoes").select("*").order("user_nome").execute()
    return res.data or []


@router.post("/permissions", status_code=201)
def grant_permission(body: PermissaoBody, _sup: dict = Depends(require_supervisor)):
    if body.perfil not in ("colaborador", "supervisor"):
        raise HTTPException(400, "perfil inválido: use 'colaborador' ou 'supervisor'")
    sb = get_supabase()
    try:
        res = sb.table("cards_permissoes").upsert(
            {
                "user_id": body.user_id,
                "user_login": body.user_login,
                "user_nome": body.user_nome,
                "perfil": body.perfil,
                "ativo": True,
            },
            on_conflict="user_id",
        ).execute()
    except Exception as e:
        _logger.error("Erro ao salvar permissão: %s", type(e).__name__)
        raise HTTPException(500, "Erro ao salvar permissão")
    return res.data[0] if res.data else {}


@router.put("/permissions/{perm_id}")
def update_permission(
    perm_id: str,
    body: PermissaoUpdate,
    _sup: dict = Depends(require_supervisor),
):
    patch: dict = {}
    if body.perfil is not None:
        if body.perfil not in ("colaborador", "supervisor"):
            raise HTTPException(400, "perfil inválido: use 'colaborador' ou 'supervisor'")
        patch["perfil"] = body.perfil
    if body.ativo is not None:
        patch["ativo"] = body.ativo
    if not patch:
        raise HTTPException(400, "Nenhum campo válido para atualizar")
    sb = get_supabase()
    res = sb.table("cards_permissoes").update(patch).eq("id", perm_id).execute()
    if not res.data:
        raise HTTPException(404, "Permissão não encontrada")
    return res.data[0]

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/users")
logger = logging.getLogger(__name__)

_VALID_ROLES = {"admin", "user"}


class UpdateRoleRequest(BaseModel):
    role: str


class UpdateActiveRequest(BaseModel):
    active: bool


@router.get("")
async def list_users(
    _: Annotated[dict, Depends(require_role("admin"))],
) -> list[dict]:
    db = get_supabase()
    result = db.table("profiles").select("*").order("created_at").execute()
    return result.data


@router.patch("/{username}/role")
async def update_role(
    username: str,
    body: UpdateRoleRequest,
    current_user: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    if username == current_user["username"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível alterar seu próprio perfil")
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role inválida. Aceitos: {sorted(_VALID_ROLES)}")

    db = get_supabase()
    result = db.table("profiles").update({"role": body.role}).eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    logger.info("Role de %s alterada para %s por %s", username, body.role, current_user["username"])
    return result.data[0]


@router.patch("/{username}/active")
async def update_active(
    username: str,
    body: UpdateActiveRequest,
    current_user: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    if username == current_user["username"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível desativar seu próprio usuário")

    db = get_supabase()
    result = db.table("profiles").update({"active": body.active}).eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    logger.info("Usuário %s %s por %s", username, "ativado" if body.active else "desativado", current_user["username"])
    return result.data[0]

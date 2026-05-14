import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/users")
logger = logging.getLogger(__name__)

_VALID_ROLES = {
    "admin", "user",
    "rh", "gestor", "coordenador", "supervisor", "colaborador",
}


class UpdateRoleRequest(BaseModel):
    role: str


class UpdateActiveRequest(BaseModel):
    active: bool


class UpdateProfileRequest(BaseModel):
    display_name: str = ""
    whatsapp_phone: str = ""


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


@router.get("/{username}/profile")
async def get_user_profile(
    username: str,
    _: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    db = get_supabase()
    result = db.table("profiles").select("display_name,email,whatsapp_phone").eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return result.data[0]


@router.patch("/{username}/profile")
async def update_user_profile(
    username: str,
    body: UpdateProfileRequest,
    _: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    db = get_supabase()
    updates: dict = {}
    if body.display_name.strip():
        updates["display_name"] = body.display_name.strip()
    if body.whatsapp_phone.strip():
        updates["whatsapp_phone"] = body.whatsapp_phone.strip()
    if updates:
        result = db.table("profiles").update(updates).eq("username", username).execute()
        if not result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return {"ok": True}


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


class UpdateModulesRequest(BaseModel):
    allowed_modules: list[str]


@router.get("/{username}/modules")
async def get_user_modules(
    username: str,
    _: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    db = get_supabase()
    result = db.table("profiles").select("allowed_modules").eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return {"allowed_modules": result.data[0].get("allowed_modules") or []}


@router.patch("/{username}/modules")
async def update_user_modules(
    username: str,
    body: UpdateModulesRequest,
    _: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    db = get_supabase()
    result = db.table("profiles").update({"allowed_modules": body.allowed_modules}).eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return {"allowed_modules": result.data[0].get("allowed_modules") or []}


@router.delete("/{username}")
async def delete_user(
    username: str,
    current_user: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    if username == current_user["username"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível excluir seu próprio usuário")

    db = get_supabase()
    result = db.table("profiles").select("active").eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if result.data[0]["active"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Só é possível recusar solicitações pendentes")

    db.table("profiles").delete().eq("username", username).execute()
    logger.info("Solicitação de %s recusada e removida por %s", username, current_user["username"])
    return {"ok": True}

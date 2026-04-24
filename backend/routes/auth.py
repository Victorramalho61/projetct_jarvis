import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import create_access_token, get_current_user
from db import get_settings, get_supabase
from ldap_client import authenticate_ldap

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    username: str
    display_name: str
    email: str
    role: str
    active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


def _get_or_create_profile(username: str, display_name: str, email: str) -> dict:
    db = get_supabase()

    result = db.table("profiles").select("*").eq("username", username).execute()
    if result.data:
        profile = result.data[0]
        if not profile["active"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário desativado")
        db.table("profiles").update({"display_name": display_name, "email": email}).eq("username", username).execute()
        return profile

    count = db.table("profiles").select("id", count="exact").execute()
    role = "admin" if (count.count or 0) == 0 else "user"

    created = db.table("profiles").insert({
        "username": username,
        "display_name": display_name,
        "email": email,
        "role": role,
        "active": True,
    }).execute()

    logger.info("Novo perfil: %s (role=%s)", username, role)
    return created.data[0]


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    settings = get_settings()

    if settings.ldap_server:
        user_info = authenticate_ldap(
            username=body.username,
            password=body.password,
            server_url=settings.ldap_server,
            domain=settings.ldap_domain,
            base_dn=settings.ldap_base_dn,
        )
        if not user_info:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    else:
        logger.warning("LDAP não configurado — modo dev ativo")
        if not body.username or not body.password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
        user_info = {
            "username": body.username,
            "display_name": body.username.capitalize(),
            "email": f"{body.username}@dev.local",
        }

    profile = _get_or_create_profile(**user_info)

    payload = {
        "username": profile["username"],
        "display_name": profile["display_name"],
        "email": profile["email"],
        "role": profile["role"],
        "active": profile["active"],
    }
    return LoginResponse(access_token=create_access_token(payload), user=UserInfo(**payload))


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[dict, Depends(get_current_user)]) -> UserInfo:
    return UserInfo(**current_user)

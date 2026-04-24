import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import create_access_token, get_current_user
from db import get_settings, get_supabase
from ldap_client import authenticate_ldap
from services.azure_auth import ALLOWED_DOMAINS, authenticate_azure_ad

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class AccessRequest(BaseModel):
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


def _authenticate(username: str, password: str) -> dict:
    """
    Tenta autenticar na ordem: LDAP → Azure AD → dev mode.
    Retorna dict com username, display_name, email.
    Lança HTTPException 401 se falhar.
    """
    settings = get_settings()

    if settings.ldap_server:
        user_info = authenticate_ldap(
            username=username,
            password=password,
            server_url=settings.ldap_server,
            domain=settings.ldap_domain,
            base_dn=settings.ldap_base_dn,
        )
        if user_info:
            return user_info
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    if settings.microsoft_client_id:
        user_info = authenticate_azure_ad(username, password)
        if user_info:
            return user_info
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas ou domínio não autorizado. Use @voetur.com.br ou @vtclog.com.br",
        )

    # Dev mode
    logger.warning("Sem LDAP/Azure AD configurado — modo dev ativo")
    if not username.strip() or not password.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    return {
        "username": username.strip(),
        "display_name": username.strip().capitalize(),
        "email": f"{username.strip()}@dev.local",
    }


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    user_info = _authenticate(body.username, body.password)
    db = get_supabase()

    # Busca perfil pelo username ou email
    result = db.table("profiles").select("*").eq("username", user_info["username"]).execute()
    if not result.data:
        result = db.table("profiles").select("*").eq("email", user_info["email"]).execute()

    if not result.data:
        # Primeiro usuário vira admin automaticamente
        count = db.table("profiles").select("id", count="exact").execute()
        if (count.count or 0) == 0:
            created = db.table("profiles").insert({
                "username": user_info["username"],
                "display_name": user_info["display_name"],
                "email": user_info["email"],
                "role": "admin",
                "active": True,
            }).execute()
            profile = created.data[0]
            logger.info("Primeiro usuário criado como admin: %s", profile["username"])
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso não solicitado. Use 'Solicitar Acesso' na página de login.",
            )
    else:
        profile = result.data[0]
        if not profile["active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seu acesso está pendente de aprovação pelo administrador.",
            )
        db.table("profiles").update({
            "display_name": user_info["display_name"],
            "email": user_info["email"],
        }).eq("id", profile["id"]).execute()

    payload = {
        "id": profile["id"],
        "username": profile["username"],
        "display_name": profile["display_name"],
        "email": profile["email"],
        "role": profile["role"],
        "active": profile["active"],
    }
    return LoginResponse(access_token=create_access_token(payload), user=UserInfo(**payload))


@router.post("/request-access")
async def request_access(body: AccessRequest) -> dict:
    user_info = _authenticate(body.username, body.password)
    db = get_supabase()

    # Verifica se já existe perfil
    result = db.table("profiles").select("*").eq("username", user_info["username"]).execute()
    if not result.data:
        result = db.table("profiles").select("*").eq("email", user_info["email"]).execute()

    if result.data:
        profile = result.data[0]
        if profile["active"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Você já tem acesso. Faça login normalmente.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sua solicitação já está pendente de aprovação.")

    count = db.table("profiles").select("id", count="exact").execute()
    is_first = (count.count or 0) == 0

    db.table("profiles").insert({
        "username": user_info["username"],
        "display_name": user_info["display_name"],
        "email": user_info["email"],
        "role": "admin" if is_first else "user",
        "active": is_first,
    }).execute()

    logger.info("Solicitação de acesso: %s (%s)", user_info["username"], user_info["email"])
    if is_first:
        return {"message": "Acesso concedido como administrador. Faça login."}
    return {"message": "Solicitação enviada. Aguardando aprovação do administrador."}


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[dict, Depends(get_current_user)]) -> UserInfo:
    return UserInfo(**current_user)

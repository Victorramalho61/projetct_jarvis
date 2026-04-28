import logging
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import create_access_token, get_current_user
from db import get_supabase
from limiter import limiter
from services.app_logger import log_event

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = ["voetur.com.br", "vtclog.com.br"]


class LoginRequest(BaseModel):
    username: str
    password: str


class AccessRequest(BaseModel):
    username: str
    password: str
    whatsapp_phone: str = ""


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


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _lookup_profile(identifier: str) -> dict | None:
    db = get_supabase()
    result = db.table("profiles").select("*").or_(f"username.eq.{identifier},email.eq.{identifier}").execute()
    return result.data[0] if result.data else None


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    identifier = body.username.strip().lower()
    profile = _lookup_profile(identifier)

    if not profile or not profile.get("password_hash"):
        log_event("warning", "auth", f"Falha de login: {identifier}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    if not _verify_password(body.password, profile["password_hash"]):
        log_event("warning", "auth", f"Falha de login: {identifier}", user_id=profile["id"])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    if not profile["active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu acesso está pendente de aprovação pelo administrador.",
        )

    payload = {
        "id": profile["id"],
        "username": profile["username"],
        "display_name": profile["display_name"],
        "email": profile["email"],
        "role": profile["role"],
        "active": profile["active"],
    }
    log_event("info", "auth", f"Login: {profile['username']}", user_id=profile["id"])
    return LoginResponse(access_token=create_access_token(payload), user=UserInfo(**payload))


@router.post("/request-access")
@limiter.limit("5/minute")
async def request_access(request: Request, body: AccessRequest) -> dict:
    email = body.username.strip().lower()

    if "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use seu e-mail corporativo completo (@voetur.com.br ou @vtclog.com.br).",
        )

    domain = email.split("@")[1]
    if domain not in ALLOWED_DOMAINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Domínio não autorizado. Use @voetur.com.br ou @vtclog.com.br.",
        )

    if not body.password or len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Senha deve ter no mínimo 8 caracteres.",
        )

    db = get_supabase()
    result = db.table("profiles").select("*").eq("email", email).execute()

    if result.data:
        profile = result.data[0]
        if profile["active"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Você já tem acesso. Faça login normalmente.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sua solicitação já está pendente de aprovação.")

    username = email.split("@")[0]
    display_name = username.replace(".", " ").title()
    password_hash = _hash_password(body.password)

    count = db.table("profiles").select("id", count="exact").execute()
    is_first = (count.count or 0) == 0

    db.table("profiles").insert({
        "username": username,
        "display_name": display_name,
        "email": email,
        "role": "admin" if is_first else "user",
        "active": is_first,
        "password_hash": password_hash,
        "whatsapp_phone": body.whatsapp_phone.strip(),
    }).execute()

    logger.info("Solicitação de acesso: %s", email)
    if is_first:
        return {"message": "Acesso concedido como administrador. Faça login."}
    return {"message": "Solicitação enviada. Aguardando aprovação do administrador."}


@router.post("/initialize")
async def initialize_password(body: LoginRequest) -> dict:
    """Define senha para contas sem senha. Só funciona enquanto nenhuma senha estiver configurada."""
    db = get_supabase()

    existing = db.table("profiles").select("id").not_.is_("password_hash", "null").execute()
    if existing.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inicialização já concluída.")

    identifier = body.username.strip().lower()
    profile = _lookup_profile(identifier)

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    if not profile["active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta inativa.")

    if not body.password or len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Senha deve ter no mínimo 8 caracteres.",
        )

    db.table("profiles").update({"password_hash": _hash_password(body.password)}).eq("id", profile["id"]).execute()
    logger.info("Senha inicializada para: %s", profile["username"])
    return {"message": "Senha definida com sucesso. Faça login normalmente."}


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[dict, Depends(get_current_user)]) -> UserInfo:
    return UserInfo(**current_user)


class ProfileUpdate(BaseModel):
    display_name: str = ""
    whatsapp_phone: str = ""


@router.get("/profile")
async def get_profile(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    db = get_supabase()
    result = db.table("profiles").select("display_name,email,whatsapp_phone").eq("id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return result.data[0]


@router.put("/profile")
async def update_profile(body: ProfileUpdate, current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    db = get_supabase()
    updates: dict = {}
    if body.display_name.strip():
        updates["display_name"] = body.display_name.strip()
    if body.whatsapp_phone.strip():
        updates["whatsapp_phone"] = body.whatsapp_phone.strip()
    if updates:
        db.table("profiles").update(updates).eq("id", current_user["id"]).execute()
    return {"ok": True}

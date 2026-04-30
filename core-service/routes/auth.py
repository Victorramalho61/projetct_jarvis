import asyncio
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Annotated

import bcrypt
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel

from auth import create_access_token, get_current_user
from db import get_settings, get_supabase
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


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[dict, Depends(get_current_user)]) -> UserInfo:
    return UserInfo(**current_user)


class ProfileUpdate(BaseModel):
    display_name: str = ""
    whatsapp_phone: str = ""
    anthropic_api_key: str | None = None


@router.get("/profile")
async def get_profile(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    db = get_supabase()
    result = db.table("profiles").select(
        "display_name,email,whatsapp_phone,anthropic_api_key"
    ).eq("id", current_user["id"]).execute()
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
    if body.anthropic_api_key is not None:
        updates["anthropic_api_key"] = body.anthropic_api_key.strip()
    if updates:
        db.table("profiles").update(updates).eq("id", current_user["id"]).execute()
    return {"ok": True}


class ForgotPasswordRequest(BaseModel):
    email: str
    channel: str = "both"


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


def _send_reset_email(to_email: str, display_name: str, reset_url: str) -> None:
    s = get_settings()
    if not s.smtp_user:
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Redefinição de senha — JARVIS"
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to_email
    html = (
        f"<p>Olá, {display_name}!</p>"
        f"<p>Clique no link para redefinir sua senha. Válido por <strong>10 minutos</strong>.</p>"
        f'<p><a href="{reset_url}">{reset_url}</a></p>'
        f"<p>Se você não solicitou, ignore este e-mail.</p>"
    )
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_user, s.smtp_password)
            smtp.sendmail(s.smtp_from or s.smtp_user, to_email, msg.as_string())
    except Exception:
        logger.exception("Erro ao enviar e-mail de reset para %s", to_email)


async def _send_reset_whatsapp(phone: str, display_name: str, reset_url: str) -> None:
    s = get_settings()
    if not s.whatsapp_api_url:
        return
    text = f"Olá, {display_name}! Acesse o link para redefinir sua senha JARVIS (válido por 10 min): {reset_url}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{s.whatsapp_api_url}/message/sendText/{s.whatsapp_instance}",
                headers={"apikey": s.whatsapp_api_key},
                json={"number": phone, "text": text},
            )
    except Exception:
        logger.exception("Erro ao enviar WhatsApp de reset para %s", phone)


def _send_reset_whatsapp_bg(phone: str, display_name: str, reset_url: str) -> None:
    asyncio.run(_send_reset_whatsapp(phone, display_name, reset_url))


@router.post("/auth/forgot-password")
@limiter.limit("3/15minutes")
async def forgot_password(request: Request, body: ForgotPasswordRequest, bg: BackgroundTasks) -> dict:
    email = body.email.strip().lower()
    profile = _lookup_profile(email)
    if not profile or not profile.get("active"):
        return {"ok": True}
    db = get_supabase()
    db.table("password_reset_tokens").delete().eq("user_id", profile["id"]).is_("used_at", "null").execute()
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    db.table("password_reset_tokens").insert({
        "user_id": profile["id"],
        "token": token,
        "expires_at": expires_at,
    }).execute()
    reset_url = f"{get_settings().frontend_url}/redefinir-senha?token={token}"
    display_name = profile.get("display_name", "")
    phone = profile.get("whatsapp_phone", "")
    if body.channel in ("email", "both"):
        bg.add_task(_send_reset_email, email, display_name, reset_url)
    if body.channel in ("whatsapp", "both") and phone:
        bg.add_task(_send_reset_whatsapp_bg, phone, display_name, reset_url)
    return {"ok": True}


@router.post("/auth/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest) -> dict:
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 8 caracteres.")
    db = get_supabase()
    result = db.table("password_reset_tokens").select("*").eq("token", body.token).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Link inválido ou expirado.")
    token_row = result.data[0]
    if token_row.get("used_at"):
        raise HTTPException(status_code=400, detail="Link inválido ou expirado.")
    expires_at = datetime.fromisoformat(token_row["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Link inválido ou expirado.")
    new_hash = _hash_password(body.new_password)
    db.table("profiles").update({"password_hash": new_hash}).eq("id", token_row["user_id"]).execute()
    db.table("password_reset_tokens").update({"used_at": datetime.now(timezone.utc).isoformat()}).eq("id", token_row["id"]).execute()
    log_event("info", "auth", "Senha redefinida", user_id=token_row["user_id"])
    return {"ok": True}

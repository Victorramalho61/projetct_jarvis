from functools import lru_cache

from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    jwt_secret: str
    jwt_expire_minutes: int = 480
    allowed_origins: str = "http://localhost:5173"
    card_encryption_key: str = ""
    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)


def validate_startup() -> None:
    """Valida dependências críticas na inicialização. Falha rápido se CARD_ENCRYPTION_KEY ausente."""
    from cryptography.fernet import Fernet, InvalidToken
    key = get_settings().card_encryption_key
    if not key:
        raise RuntimeError("CARD_ENCRYPTION_KEY não configurada — serviço não pode iniciar")
    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        # Testa round-trip para confirmar que a chave é válida
        token = f.encrypt(b"test")
        f.decrypt(token)
    except Exception as e:
        raise RuntimeError(f"CARD_ENCRYPTION_KEY inválida: {type(e).__name__}") from None

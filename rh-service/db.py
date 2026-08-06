from functools import lru_cache

from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    jwt_secret: str
    jwt_expire_minutes: int = 480
    allowed_origins: str = "http://localhost:5173"

    # D4Sign — assinatura eletrônica (Fase 2 do módulo de RH)
    d4sign_base_url: str = "https://sandbox.d4sign.com.br/api/v1"
    d4sign_token_api: str = ""
    d4sign_crypt_key: str = ""
    d4sign_secret_key_hmac: str = ""
    d4sign_safe_uuid: str = ""
    d4sign_template_uuid: str = ""
    d4sign_template_aditivo_uuid: str = ""

    model_config = {"env_file": ".env"}

    @property
    def d4sign_configurado(self) -> bool:
        return bool(
            self.d4sign_token_api
            and self.d4sign_crypt_key
            and self.d4sign_safe_uuid
            and self.d4sign_template_uuid
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)

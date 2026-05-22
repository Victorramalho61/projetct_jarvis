from functools import lru_cache

from pydantic_settings import BaseSettings
from supabase import Client, create_client


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    jwt_secret: str
    jwt_expire_minutes: int = 480
    allowed_origins: str = "http://localhost:5173"
    anthropic_api_key: str = ""
    cert_encryption_key: str = ""
    sefaz_ambiente: str = "1"
    # ND Digital portal (NFSe recebidas via portal centralizador)
    ndd_client_id: str = ""          # OAuth client_id — capturar do DevTools Network
    ndd_username: str = ""           # login do portal NDD
    ndd_password: str = ""           # senha do portal NDD
    # Portal Nacional NFS-e (ADN — adn.nfse.gov.br)
    portal_nfse_ambiente: str = "1"  # 1=produção, 2=homologação
    portal_nfse_base_url: str = "https://adn.nfse.gov.br"
    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_key)

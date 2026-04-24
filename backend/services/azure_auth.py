import logging

import msal

from db import get_settings

logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = ["voetur.com.br", "vtclog.com.br"]


def _build_msal_app() -> msal.ConfidentialClientApplication:
    s = get_settings()
    return msal.ConfidentialClientApplication(
        s.microsoft_client_id,
        authority=f"https://login.microsoftonline.com/{s.microsoft_tenant_id}",
        client_credential=s.microsoft_client_secret,
    )


def _emails_to_try(username: str) -> list[str]:
    u = username.lower().strip()
    if "@" in u:
        return [u]
    return [f"{u}@{d}" for d in ALLOWED_DOMAINS]


def authenticate_azure_ad(username: str, password: str) -> dict | None:
    """Autentica via ROPC no Azure AD. Retorna dados do usuário ou None."""
    if "@" in username:
        domain = username.lower().split("@")[1]
        if domain not in ALLOWED_DOMAINS:
            return None

    app = _build_msal_app()

    for email in _emails_to_try(username):
        try:
            result = app.acquire_token_by_username_password(
                username=email,
                password=password,
                scopes=["User.Read"],
            )
            if "error" in result:
                logger.debug("Azure AD falhou para %s: %s", email, result.get("error_description", result.get("error")))
                continue

            claims = result.get("id_token_claims", {})
            actual_email = (claims.get("preferred_username") or email).lower()
            display_name = claims.get("name") or actual_email.split("@")[0].replace(".", " ").title()
            username_slug = actual_email.split("@")[0]

            return {
                "username": username_slug,
                "display_name": display_name,
                "email": actual_email,
            }
        except Exception:
            logger.exception("Erro ROPC Azure AD para %s", email)

    return None

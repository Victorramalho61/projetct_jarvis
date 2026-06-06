import logging

from cryptography.fernet import Fernet

_logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    from db import get_settings
    key = get_settings().card_encryption_key
    if not key:
        raise ValueError("CARD_ENCRYPTION_KEY não configurada")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()

import os
import tempfile
from contextlib import contextmanager
from datetime import date
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, NoEncryption, PublicFormat
)


def encrypt_cert(pfx_bytes: bytes, password: str, fernet_key: str) -> tuple[str, str]:
    f = Fernet(fernet_key.encode())
    return f.encrypt(pfx_bytes).decode(), f.encrypt(password.encode()).decode()


def decrypt_cert(pfx_encrypted: str, pass_encrypted: str, fernet_key: str) -> tuple[bytes, bytes]:
    f = Fernet(fernet_key.encode())
    pfx_bytes = f.decrypt(pfx_encrypted.encode())
    password = f.decrypt(pass_encrypted.encode())
    return pfx_bytes, password


def get_cert_expiry(pfx_bytes: bytes, password: str) -> Optional[date]:
    try:
        private_key, certificate, additional = pkcs12.load_key_and_certificates(
            pfx_bytes, password.encode()
        )
        if certificate:
            return certificate.not_valid_after_utc.date()
    except Exception:
        pass
    return None


@contextmanager
def extract_pem_for_requests(pfx_encrypted: str, pass_encrypted: str, fernet_key: str):
    pfx_bytes, password = decrypt_cert(pfx_encrypted, pass_encrypted, fernet_key)

    private_key, certificate, _ = pkcs12.load_key_and_certificates(pfx_bytes, password)

    cert_pem = certificate.public_bytes(Encoding.PEM)
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())

    cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    try:
        cert_file.write(cert_pem)
        cert_file.flush()
        key_file.write(key_pem)
        key_file.flush()
        cert_file.close()
        key_file.close()
        yield cert_file.name, key_file.name
    finally:
        try:
            os.unlink(cert_file.name)
        except OSError:
            pass
        try:
            os.unlink(key_file.name)
        except OSError:
            pass

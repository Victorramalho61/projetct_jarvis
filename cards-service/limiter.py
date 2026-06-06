import re

from slowapi import Limiter
from starlette.requests import Request


def _key_by_user_then_ip(request: Request) -> str:
    """Rate limit por user_id (JWT) com fallback para IP real.
    Usa X-Real-IP (setado pelo Kong/nginx) para evitar bypass via X-Forwarded-For.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            import jwt as _jwt
            from db import get_settings
            payload = _jwt.decode(
                auth[7:],
                get_settings().jwt_secret,
                algorithms=["HS256"],
            )
            uid = payload.get("user_id") or payload.get("sub")
            if uid:
                return f"user:{uid}"
        except Exception:
            pass
    # Fallback: IP real via header confiável do proxy
    real_ip = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if real_ip and re.match(r"^[\d\.a-fA-F:]+$", real_ip):
        return f"ip:{real_ip}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


limiter = Limiter(key_func=_key_by_user_then_ip)

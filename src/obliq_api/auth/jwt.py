from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt

from obliq_api.compat import UTC
from obliq_api.config import get_settings
from obliq_api.exceptions import AuthenticationError

settings = get_settings()


def create_access_token(
    subject: str | UUID,
    *,
    organisation_id: str | UUID,
    role: str,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "org": str(organisation_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str | UUID) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(subject),
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

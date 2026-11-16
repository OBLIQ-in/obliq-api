import hashlib
import secrets
from datetime import UTC, datetime

from passlib.context import CryptContext

from obliq_api.config import get_settings

settings = get_settings()
pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.bcrypt_rounds
)


def generate_api_key(*, internal: bool = False) -> tuple[str, str, str]:
    """Return (full_key, prefix, hash)."""
    prefix_base = settings.internal_key_prefix if internal else settings.api_key_prefix
    random_part = secrets.token_urlsafe(24)
    full_key = f"{prefix_base}{random_part}"
    # Store a short recognisable prefix for display
    display_prefix = full_key[: len(prefix_base) + 8]
    key_hash = hash_api_key(full_key)
    return full_key, display_prefix, key_hash


def hash_api_key(key: str) -> str:
    # Fast keyed hash for high-volume lookup (not password hashing)
    # codeql[py/weak-sensitive-data-hashing]
    return hashlib.blake2b(
        key.encode("utf-8"),
        key=settings.secret_key.encode("utf-8")[:64],
        digest_size=32,
    ).hexdigest()


def verify_api_key(plain_key: str, stored_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key(plain_key), stored_hash)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def utcnow() -> datetime:
    return datetime.now(UTC)

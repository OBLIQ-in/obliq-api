from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.auth.jwt import decode_token
from obliq_api.auth.keys import verify_api_key
from obliq_api.config import get_settings
from obliq_api.db.session import get_db
from obliq_api.exceptions import AuthenticationError, AuthorizationError, RateLimitExceededError
from obliq_api.models.api_key import ApiKey
from obliq_api.models.user import User
from obliq_api.protocols import JobStore, OCREngine, RateLimiter
from obliq_api.services.ocr import create_ocr_engine
from obliq_api.stores.redis_job_store import RedisJobStore
from obliq_api.stores.redis_rate_limiter import RedisRateLimiter

settings = get_settings()

# ---------------------------------------------------------------------------
# Singletons (created lazily on first use)
# ---------------------------------------------------------------------------
_job_store: JobStore | None = None
_ocr_engine: OCREngine | None = None
_rate_limiter: RateLimiter | None = None


def get_job_store() -> JobStore:
    global _job_store
    if _job_store is None:
        _job_store = RedisJobStore()
    return _job_store


def get_ocr_engine() -> OCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = create_ocr_engine()
    return _ocr_engine


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RedisRateLimiter()
    return _rate_limiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


# ---------------------------------------------------------------------------
# Auth context
# ---------------------------------------------------------------------------


class AuthContext:
    def __init__(
        self,
        *,
        organisation_id: UUID,
        api_key: ApiKey | None = None,
        user: User | None = None,
        is_internal: bool = False,
    ) -> None:
        self.organisation_id = organisation_id
        self.api_key = api_key
        self.user = user
        self.is_internal = is_internal


# ---------------------------------------------------------------------------
# Rate-limit helper (not a FastAPI dependency — called explicitly in routes)
# ---------------------------------------------------------------------------


async def check_rate_limits(
    request: Request,
    ctx: AuthContext,
    limiter: RateLimiter,
    *,
    page_count: int = 1,
) -> None:
    """Check per-organisation request-rate and page-rate limits.

    Raises RateLimitExceededError (429) if either limit is breached.
    Internal keys are exempt.  Call this inside route handlers after
    resolving AuthContext.
    """
    if ctx.is_internal:
        return

    org_key = str(ctx.organisation_id)

    # Request-rate check
    allowed, retry_after = await limiter.is_allowed(
        f"{org_key}:req",
        limit=settings.rate_limit_requests_per_minute,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitExceededError(retry_after=retry_after)

    # Page-rate check (guard against large-document abuse)
    allowed, retry_after = await limiter.is_allowed(
        f"{org_key}:pages",
        limit=settings.rate_limit_pages_per_minute,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitExceededError(retry_after=retry_after)


# ---------------------------------------------------------------------------
# FastAPI auth dependencies
# ---------------------------------------------------------------------------


async def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    if not (
        token.startswith(settings.api_key_prefix) or token.startswith(settings.internal_key_prefix)
    ):
        raise AuthenticationError("Invalid API key format")

    # Look up by prefix first for speed
    prefix_len = (
        len(settings.internal_key_prefix) + 8
        if token.startswith(settings.internal_key_prefix)
        else len(settings.api_key_prefix) + 8
    )
    prefix = token[:prefix_len]
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.status == "active",
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None or not verify_api_key(token, api_key.key_hash):
        raise AuthenticationError("Invalid or revoked API key")

    return AuthContext(
        organisation_id=api_key.organisation_id,
        api_key=api_key,
        is_internal=api_key.is_internal,
    )


async def require_dashboard_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    user_id = UUID(payload["sub"])
    org_id = UUID(payload["org"])

    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None or user.organisation_id != org_id:
        raise AuthenticationError("User not found or inactive")

    return AuthContext(organisation_id=org_id, user=user)


async def require_admin(ctx: AuthContext = Depends(require_dashboard_user)) -> AuthContext:
    if ctx.user is None or ctx.user.role not in ("owner", "admin"):
        raise AuthorizationError("Admin role required")
    return ctx

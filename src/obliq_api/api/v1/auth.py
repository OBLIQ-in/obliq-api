from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.auth.jwt import create_access_token, create_refresh_token, decode_token
from obliq_api.auth.keys import hash_password, utcnow, verify_password
from obliq_api.config import get_settings
from obliq_api.db.session import get_db
from obliq_api.exceptions import AuthenticationError, ValidationError
from obliq_api.models.organisation import Organisation
from obliq_api.models.user import User
from obliq_api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from obliq_api.services.credits import CreditService

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Check existing email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise ValidationError("Email already registered")

    org = Organisation(
        name=body.organisation_name,
        credit_balance=0,
        starting_grant=settings.starting_credits,
        status="active",
    )
    db.add(org)
    await db.flush()

    user = User(
        organisation_id=org.id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="owner",
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    # Grant starting credits
    credits = CreditService(db)
    await credits.grant_starting_credits(org.id)

    access = create_access_token(user.id, organisation_id=org.id, role=user.role)
    refresh = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if (
        user is None
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
    ):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationError("Account is inactive")

    user.last_login_at = utcnow()
    await db.flush()

    access = create_access_token(user.id, organisation_id=user.organisation_id, role=user.role)
    refresh = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")

    from uuid import UUID

    user_id = UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("User not found")

    access = create_access_token(user.id, organisation_id=user.organisation_id, role=user.role)
    new_refresh = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserPublic)
async def me(
    ctx=Depends(
        __import__(
            "obliq_api.dependencies", fromlist=["require_dashboard_user"]
        ).require_dashboard_user
    ),
) -> UserPublic:
    assert ctx.user
    return UserPublic(
        id=ctx.user.id,
        email=ctx.user.email,
        full_name=ctx.user.full_name,
        role=ctx.user.role,
        organisation_id=ctx.user.organisation_id,
        email_verified=ctx.user.email_verified,
    )

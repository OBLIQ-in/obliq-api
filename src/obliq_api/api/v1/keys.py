from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.auth.keys import generate_api_key, utcnow
from obliq_api.db.session import get_db
from obliq_api.dependencies import AuthContext, require_dashboard_user
from obliq_api.exceptions import NotFoundError
from obliq_api.models.api_key import ApiKey
from obliq_api.schemas.keys import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyList,
    ApiKeyPublic,
    ApiKeyRotate,
)

router = APIRouter(prefix="/keys", tags=["keys"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(
    body: ApiKeyCreate,
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    full_key, prefix, key_hash = generate_api_key(internal=False)
    expires_at = utcnow() + timedelta(days=body.expires_in_days) if body.expires_in_days else None

    api_key = ApiKey(
        organisation_id=ctx.organisation_id,
        created_by=ctx.user.id if ctx.user else None,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        expires_at=expires_at,
        is_internal=False,
        status="active",
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=full_key,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        is_internal=False,
        created_at=api_key.created_at,
    )


@router.get("", response_model=ApiKeyList)
async def list_keys(
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyList:
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.organisation_id == ctx.organisation_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return ApiKeyList(keys=[ApiKeyPublic.model_validate(k) for k in keys])


@router.post("/{key_id}/rotate", response_model=ApiKeyCreated, status_code=201)
async def rotate_key(
    key_id: UUID,
    body: ApiKeyRotate = ApiKeyRotate(),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.organisation_id == ctx.organisation_id,
        )
    )
    old_key = result.scalar_one_or_none()
    if old_key is None or old_key.status == "revoked":
        raise NotFoundError("Active API key not found")

    full_key, prefix, key_hash = generate_api_key(internal=old_key.is_internal)
    new_key = ApiKey(
        organisation_id=ctx.organisation_id,
        created_by=ctx.user.id if ctx.user else None,
        name=f"{old_key.name} (Rotated)",
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=old_key.scopes,
        expires_at=old_key.expires_at,
        is_internal=old_key.is_internal,
        status="active",
    )
    db.add(new_key)

    if body.grace_period_hours > 0:
        old_key.status = "expiring"
        old_key.expires_at = utcnow() + timedelta(hours=body.grace_period_hours)
    else:
        old_key.status = "revoked"
        old_key.revoked_at = utcnow()

    await db.flush()
    await db.refresh(new_key)

    return ApiKeyCreated(
        id=new_key.id,
        name=new_key.name,
        key_prefix=new_key.key_prefix,
        key=full_key,
        scopes=new_key.scopes,
        expires_at=new_key.expires_at,
        is_internal=new_key.is_internal,
        created_at=new_key.created_at,
    )


@router.post("/{key_id}/revoke", status_code=204)
async def revoke_key(
    key_id: UUID,
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.organisation_id == ctx.organisation_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise NotFoundError("API key not found")
    api_key.status = "revoked"
    api_key.revoked_at = utcnow()
    await db.flush()

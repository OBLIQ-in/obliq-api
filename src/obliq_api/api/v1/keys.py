from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.auth.keys import generate_api_key, utcnow
from obliq_api.db.session import get_db
from obliq_api.dependencies import AuthContext, require_dashboard_user
from obliq_api.exceptions import NotFoundError
from obliq_api.models.api_key import ApiKey
from obliq_api.schemas.keys import ApiKeyCreate, ApiKeyCreated, ApiKeyList, ApiKeyPublic

router = APIRouter(prefix="/keys", tags=["keys"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(
    body: ApiKeyCreate,
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    full_key, prefix, key_hash = generate_api_key(internal=False)
    api_key = ApiKey(
        organisation_id=ctx.organisation_id,
        created_by=ctx.user.id if ctx.user else None,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
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

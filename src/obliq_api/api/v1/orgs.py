from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.db.session import get_db
from obliq_api.dependencies import AuthContext, require_dashboard_user
from obliq_api.models.credit_ledger import CreditLedger
from obliq_api.models.organisation import Organisation
from obliq_api.models.usage_record import UsageRecord
from obliq_api.schemas.common import PaginatedResponse
from obliq_api.schemas.orgs import CreditLedgerEntry, OrganisationPublic, UsageRecordPublic

router = APIRouter(prefix="/orgs", tags=["organisations"])


@router.get("/me", response_model=OrganisationPublic)
async def get_my_org(
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> OrganisationPublic:
    result = await db.execute(select(Organisation).where(Organisation.id == ctx.organisation_id))
    org = result.scalar_one()
    return OrganisationPublic.model_validate(org)


@router.get("/me/ledger", response_model=PaginatedResponse[CreditLedgerEntry])
async def get_ledger(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CreditLedgerEntry]:
    offset = (page - 1) * page_size
    result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.organisation_id == ctx.organisation_id)
        .order_by(CreditLedger.created_at.desc())
        .offset(offset)
        .limit(page_size + 1)
    )
    rows = result.scalars().all()
    has_more = len(rows) > page_size
    items = [CreditLedgerEntry.model_validate(r) for r in rows[:page_size]]
    return PaginatedResponse(
        items=items,
        total=-1,  # optional count query omitted for speed
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/me/usage", response_model=PaginatedResponse[UsageRecordPublic])
async def get_usage(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UsageRecordPublic]:
    offset = (page - 1) * page_size
    result = await db.execute(
        select(UsageRecord)
        .where(UsageRecord.organisation_id == ctx.organisation_id)
        .order_by(UsageRecord.created_at.desc())
        .offset(offset)
        .limit(page_size + 1)
    )
    rows = result.scalars().all()
    has_more = len(rows) > page_size
    items = [UsageRecordPublic.model_validate(r) for r in rows[:page_size]]
    return PaginatedResponse(
        items=items,
        total=-1,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )

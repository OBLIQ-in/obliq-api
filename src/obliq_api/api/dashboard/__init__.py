"""Dashboard aggregate endpoints.

These endpoints are designed for the developer dashboard UI.  They return
pre-joined summaries so the frontend doesn't need to make multiple round-trips.

All routes require a valid dashboard JWT (require_dashboard_user).

Routes
------
GET /v1/dashboard/summary
    One-call overview: org details, credit balance, active key count,
    30-day usage totals, and the last 5 jobs.

GET /v1/dashboard/usage/daily
    Per-day aggregated usage for the last N days (default 30).
    Returns pages_processed, credits_charged, and job counts per day.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.db.session import get_db
from obliq_api.dependencies import AuthContext, require_dashboard_user
from obliq_api.models.api_key import ApiKey
from obliq_api.models.organisation import Organisation
from obliq_api.models.usage_record import UsageRecord
from obliq_api.schemas.orgs import OrganisationPublic, UsageRecordPublic

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class KeySummary(BaseModel):
    total: int
    active: int


class UsageTotals(BaseModel):
    jobs: int
    pages_processed: int
    credits_charged: int
    failed_jobs: int


class DashboardSummary(BaseModel):
    organisation: OrganisationPublic
    keys: KeySummary
    usage_last_30_days: UsageTotals
    recent_jobs: list[UsageRecordPublic]


class DailyUsage(BaseModel):
    date: str  # ISO date string, e.g. "2026-11-15"
    jobs: int
    pages_processed: int
    credits_charged: int
    failed_jobs: int


class DailyUsageResponse(BaseModel):
    days: list[DailyUsage]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    org_id: UUID = ctx.organisation_id
    since = datetime.now(UTC) - timedelta(days=30)

    # Organisation
    org_row = await db.execute(select(Organisation).where(Organisation.id == org_id))
    org = org_row.scalar_one()

    # Key counts
    keys_row = await db.execute(
        select(
            func.count(ApiKey.id).label("total"),
            func.count(ApiKey.id).filter(ApiKey.status == "active").label("active"),
        ).where(ApiKey.organisation_id == org_id)
    )
    keys_data = keys_row.one()

    # 30-day usage totals
    totals_row = await db.execute(
        select(
            func.count(UsageRecord.id).label("jobs"),
            func.coalesce(func.sum(UsageRecord.pages_processed), 0).label("pages_processed"),
            func.coalesce(func.sum(UsageRecord.credits_charged), 0).label("credits_charged"),
            func.count(UsageRecord.id).filter(UsageRecord.status == "failed").label("failed_jobs"),
        ).where(
            UsageRecord.organisation_id == org_id,
            UsageRecord.created_at >= since,
        )
    )
    totals = totals_row.one()

    # Last 5 jobs
    recent_rows = await db.execute(
        select(UsageRecord)
        .where(UsageRecord.organisation_id == org_id)
        .order_by(UsageRecord.created_at.desc())
        .limit(5)
    )
    recent = [UsageRecordPublic.model_validate(r) for r in recent_rows.scalars().all()]

    return DashboardSummary(
        organisation=OrganisationPublic.model_validate(org),
        keys=KeySummary(total=keys_data.total, active=keys_data.active),
        usage_last_30_days=UsageTotals(
            jobs=totals.jobs,
            pages_processed=int(totals.pages_processed),
            credits_charged=int(totals.credits_charged),
            failed_jobs=totals.failed_jobs,
        ),
        recent_jobs=recent,
    )


@router.get("/usage/daily", response_model=DailyUsageResponse)
async def get_daily_usage(
    days: int = Query(30, ge=1, le=90),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> DailyUsageResponse:
    """Return per-day aggregated usage for the last ``days`` days (max 90)."""
    org_id: UUID = ctx.organisation_id
    since = datetime.now(UTC) - timedelta(days=days)

    # Truncate created_at to day for grouping
    day_col = func.date_trunc("day", UsageRecord.created_at).label("day")

    rows = await db.execute(
        select(
            day_col,
            func.count(UsageRecord.id).label("jobs"),
            func.coalesce(func.sum(UsageRecord.pages_processed), 0).label("pages_processed"),
            func.coalesce(func.sum(UsageRecord.credits_charged), 0).label("credits_charged"),
            func.count(UsageRecord.id).filter(UsageRecord.status == "failed").label("failed_jobs"),
        )
        .where(
            UsageRecord.organisation_id == org_id,
            UsageRecord.created_at >= since,
        )
        .group_by(day_col)
        .order_by(day_col)
    )

    result_days = [
        DailyUsage(
            date=row.day.strftime("%Y-%m-%d"),
            jobs=row.jobs,
            pages_processed=int(row.pages_processed),
            credits_charged=int(row.credits_charged),
            failed_jobs=row.failed_jobs,
        )
        for row in rows
    ]

    return DailyUsageResponse(days=result_days)

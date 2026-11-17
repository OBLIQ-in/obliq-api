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

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.compat import UTC
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


class HourlyUsage(BaseModel):
    hour: str  # ISO hour string, e.g. "2026-11-17 12:00"
    jobs: int
    pages_processed: int
    failed_jobs: int
    avg_duration_ms: int


class HourlyUsageResponse(BaseModel):
    hours: list[HourlyUsage]


class HeatmapResponse(BaseModel):
    days: list[str]
    slots: list[str]
    matrix: dict[str, list[int]]
    total_requests: int
    max_density: int


class BreakdownItem(BaseModel):
    label: str
    count: int
    percentage: float
    color: str


class BreakdownResponse(BaseModel):
    total: int
    items: list[BreakdownItem]


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
    key_id: UUID | None = Query(None),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> DailyUsageResponse:
    """Return per-day aggregated usage for the last ``days`` days (max 90)."""
    org_id: UUID = ctx.organisation_id
    since = datetime.now(UTC) - timedelta(days=days)

    day_col = func.date_trunc("day", UsageRecord.created_at).label("day")

    query = select(
        day_col,
        func.count(UsageRecord.id).label("jobs"),
        func.coalesce(func.sum(UsageRecord.pages_processed), 0).label("pages_processed"),
        func.coalesce(func.sum(UsageRecord.credits_charged), 0).label("credits_charged"),
        func.count(UsageRecord.id).filter(UsageRecord.status == "failed").label("failed_jobs"),
    ).where(
        UsageRecord.organisation_id == org_id,
        UsageRecord.created_at >= since,
    )
    if key_id:
        query = query.where(UsageRecord.api_key_id == key_id)

    query = query.group_by(day_col).order_by(day_col)
    rows = await db.execute(query)

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


@router.get("/usage/hourly", response_model=HourlyUsageResponse)
async def get_hourly_usage(
    hours: int = Query(24, ge=1, le=72),
    key_id: UUID | None = Query(None),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> HourlyUsageResponse:
    """Return per-hour aggregated usage for recent operational monitoring."""
    org_id: UUID = ctx.organisation_id
    since = datetime.now(UTC) - timedelta(hours=hours)

    hour_col = func.date_trunc("hour", UsageRecord.created_at).label("hour")

    query = select(
        hour_col,
        func.count(UsageRecord.id).label("jobs"),
        func.coalesce(func.sum(UsageRecord.pages_processed), 0).label("pages_processed"),
        func.count(UsageRecord.id).filter(UsageRecord.status == "failed").label("failed_jobs"),
        func.coalesce(func.avg(UsageRecord.duration_ms), 0).label("avg_duration_ms"),
    ).where(
        UsageRecord.organisation_id == org_id,
        UsageRecord.created_at >= since,
    )
    if key_id:
        query = query.where(UsageRecord.api_key_id == key_id)

    query = query.group_by(hour_col).order_by(hour_col)
    rows = await db.execute(query)

    result_hours = [
        HourlyUsage(
            hour=row.hour.strftime("%Y-%m-%d %H:00"),
            jobs=row.jobs,
            pages_processed=int(row.pages_processed),
            failed_jobs=row.failed_jobs,
            avg_duration_ms=int(row.avg_duration_ms),
        )
        for row in rows
    ]

    return HourlyUsageResponse(hours=result_hours)


@router.get("/usage/heatmap", response_model=HeatmapResponse)
async def get_usage_heatmap(
    days: int = Query(30, ge=1, le=90),
    key_id: UUID | None = Query(None),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    """Return day-of-week by hour-of-day traffic distribution matrix for telemetry."""
    org_id: UUID = ctx.organisation_id
    since = datetime.now(UTC) - timedelta(days=days)

    query = select(UsageRecord.created_at).where(
        UsageRecord.organisation_id == org_id,
        UsageRecord.created_at >= since,
    )
    if key_id:
        query = query.where(UsageRecord.api_key_id == key_id)

    result = await db.execute(query)
    timestamps = result.scalars().all()

    day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    slot_labels = ["12a", "3a", "6a", "9a", "12p", "3p", "6p", "9p"]
    matrix: dict[str, list[int]] = {d: [0] * 8 for d in day_labels}

    total_requests = 0
    max_density = 0
    for ts in timestamps:
        if ts is not None:
            # Map Python weekday (0=Mon..6=Sun) to Sun=0..Sat=6
            dow = (ts.weekday() + 1) % 7
            slot = min(7, ts.hour // 3)
            matrix[day_labels[dow]][slot] += 1
            total_requests += 1

    for row_counts in matrix.values():
        for c in row_counts:
            if c > max_density:
                max_density = c

    return HeatmapResponse(
        days=day_labels,
        slots=slot_labels,
        matrix=matrix,
        total_requests=total_requests,
        max_density=max_density,
    )


@router.get("/usage/breakdown", response_model=BreakdownResponse)
async def get_usage_breakdown(
    days: int = Query(30, ge=1, le=90),
    key_id: UUID | None = Query(None),
    ctx: AuthContext = Depends(require_dashboard_user),
    db: AsyncSession = Depends(get_db),
) -> BreakdownResponse:
    """Return job execution breakdown by processing outcome for telemetry."""
    org_id: UUID = ctx.organisation_id
    since = datetime.now(UTC) - timedelta(days=days)

    query = (
        select(
            UsageRecord.status,
            func.count(UsageRecord.id).label("count"),
        )
        .where(
            UsageRecord.organisation_id == org_id,
            UsageRecord.created_at >= since,
        )
        .group_by(UsageRecord.status)
    )
    if key_id:
        query = query.where(UsageRecord.api_key_id == key_id)

    rows = await db.execute(query)
    raw_counts = {row.status: row.count for row in rows}

    total = sum(raw_counts.values())

    # Map known statuses with consistent labels and colors
    category_config = [
        ("succeeded", "Successful extractions", "#3ecf8e"),
        ("partial", "Partial / degraded", "#a78bfa"),
        ("failed", "Failed jobs", "#f0616d"),
    ]

    items: list[BreakdownItem] = []
    for status_key, label, color in category_config:
        cnt = raw_counts.pop(status_key, 0)
        pct = round((cnt / total * 100), 1) if total > 0 else 0.0
        items.append(BreakdownItem(label=label, count=cnt, percentage=pct, color=color))

    # Any remaining statuses
    for other_status, cnt in raw_counts.items():
        pct = round((cnt / total * 100), 1) if total > 0 else 0.0
        items.append(
            BreakdownItem(
                label=f"Other ({other_status})",
                count=cnt,
                percentage=pct,
                color="#5aa9f0",
            )
        )

    return BreakdownResponse(total=total, items=items)

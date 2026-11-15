from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganisationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str | None
    credit_balance: int
    starting_grant: int
    status: str
    created_at: datetime


class CreditLedgerEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_type: str
    amount: int
    balance_after: int
    reference_type: str | None
    reference_id: str | None
    created_at: datetime


class UsageRecordPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: str
    job_id: UUID | None
    endpoint: str
    status: str
    http_status: int | None
    pages_processed: int
    credits_charged: int
    duration_ms: int | None
    error_code: str | None
    created_at: datetime

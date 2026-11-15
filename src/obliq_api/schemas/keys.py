from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    key: str  # full key shown only once
    is_internal: bool
    created_at: datetime


class ApiKeyPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    is_internal: bool
    status: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyList(BaseModel):
    keys: list[ApiKeyPublic]

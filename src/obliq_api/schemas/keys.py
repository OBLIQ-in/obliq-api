from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scopes: list[str] = Field(default_factory=lambda: ["ocr:read", "ocr:write"])
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    key: str  # full key shown only once
    scopes: list[str] = Field(default_factory=lambda: ["ocr:read", "ocr:write"])
    expires_at: datetime | None = None
    is_internal: bool
    created_at: datetime


class ApiKeyRotate(BaseModel):
    grace_period_hours: int = Field(default=24, ge=0, le=168)


class ApiKeyPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str] = Field(default_factory=lambda: ["ocr:read", "ocr:write"])
    expires_at: datetime | None = None
    is_internal: bool
    status: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyList(BaseModel):
    keys: list[ApiKeyPublic]

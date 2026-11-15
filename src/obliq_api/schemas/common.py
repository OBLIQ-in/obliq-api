from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, bool]


class PageResult(BaseModel):
    page_number: int
    text: str | None = None
    confidence: float | None = None
    # "ok" | "blank" | "low_confidence" | "failed"
    status: str = "ok"
    # Fields populated by obliq-ocr; None when using the stub
    method: str | None = None          # "text_layer" | "ocr" | "blank"
    reason: str | None = None          # human-readable routing reason
    n_chars: int | None = None         # character count on the page
    seconds: float | None = None       # per-page processing time
    bounding_boxes: list[dict[str, Any]] | None = None
    error: str | None = None


class OCRResult(BaseModel):
    job_id: UUID | None = None
    page_count: int
    pages: list[PageResult]
    status: str  # succeeded | partial | failed
    processing_time_ms: int | None = None
    device: str | None = None          # "CPU" | "CUDA" | "stub" etc.


class JobStatusResponse(BaseModel):
    id: UUID
    status: str  # queued | processing | succeeded | failed | expired
    page_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class CreditsInfo(BaseModel):
    remaining: int
    charged: int | None = None


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool

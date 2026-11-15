from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class OCREngine(Protocol):
    """Protocol for the OCR engine (obliq-ocr wrapper)."""

    async def extract(
        self,
        file_path: str,
        *,
        max_pages: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Extract text and metadata from a document.

        Returns a dict with at least:
        - pages: list of page results
        - page_count: int
        - status: str
        """
        ...

    async def health_check(self) -> bool:
        """Return True if the engine is ready."""
        ...


@runtime_checkable
class JobStore(Protocol):
    """Protocol for external job state store (Redis)."""

    async def create_job(
        self,
        job_id: UUID,
        payload: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> None: ...

    async def get_job(self, job_id: UUID) -> dict[str, Any] | None: ...

    async def update_job(
        self,
        job_id: UUID,
        updates: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> None: ...

    async def set_result(
        self,
        job_id: UUID,
        result: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> None: ...

    async def get_result(self, job_id: UUID) -> dict[str, Any] | None: ...

    async def delete_job(self, job_id: UUID) -> None: ...

    async def health_check(self) -> bool: ...


@runtime_checkable
class RateLimiter(Protocol):
    async def is_allowed(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        ...

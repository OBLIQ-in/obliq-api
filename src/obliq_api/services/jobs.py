from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.config import get_settings
from obliq_api.db.session import AsyncSessionLocal
from obliq_api.exceptions import JobError, NotFoundError
from obliq_api.models.usage_record import UsageRecord
from obliq_api.observability import record_ocr_metrics
from obliq_api.protocols import JobStore, OCREngine
from obliq_api.services.credits import CreditService
from obliq_api.services.storage import save_upload_temporarily

settings = get_settings()
log = structlog.get_logger(__name__)


class JobService:
    def __init__(
        self,
        session: AsyncSession,
        job_store: JobStore,
        ocr_engine: OCREngine,
    ) -> None:
        self.session = session
        self.job_store = job_store
        self.ocr = ocr_engine
        self.credits = CreditService(session)

    async def submit(
        self,
        upload: UploadFile,
        *,
        organisation_id: UUID,
        api_key_id: UUID | None,
        is_internal: bool,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        job_id = uuid4()
        now = datetime.now(UTC).isoformat()

        async with save_upload_temporarily(upload) as tmp_path:
            size = tmp_path.stat().st_size
            estimated_pages = max(1, min(size // 40_000, settings.max_pages_per_job))

            reserved = await self.credits.reserve(
                organisation_id,
                estimated_pages,
                reference_id=str(job_id),
                idempotency_key=idempotency_key,
                is_internal=is_internal,
            )

            # Commit the credit reservation now, before we return 202.
            # The background task opens its own session, so the HTTP session
            # must commit here — otherwise the reservation is invisible to it.
            await self.session.commit()

            # Persist a copy for the background task
            fd, work_name = tempfile.mkstemp(suffix=tmp_path.suffix)
            import os

            os.close(fd)
            work_path = Path(work_name)
            shutil.copy2(tmp_path, work_path)

            payload = {
                "id": str(job_id),
                "status": "queued",
                "organisation_id": str(organisation_id),
                "api_key_id": str(api_key_id) if api_key_id else None,
                "is_internal": is_internal,
                "estimated_pages": estimated_pages,
                "reserved_credits": reserved,
                "request_id": request_id,
                "created_at": now,
                "updated_at": now,
            }
            await self.job_store.create_job(
                job_id,
                payload,
                ttl=settings.job_result_ttl_seconds * 2,
            )

            log.info(
                "job.queued",
                job_id=str(job_id),
                org=str(organisation_id),
                estimated_pages=estimated_pages,
                file_size_bytes=size,
                request_id=request_id,
            )

            # Fire background task. It opens its own DB session so it is
            # completely decoupled from this HTTP request's session lifecycle.
            asyncio.create_task(
                _process_job(
                    job_store=self.job_store,
                    ocr_engine=self.ocr,
                    job_id=job_id,
                    file_path=work_path,
                    organisation_id=organisation_id,
                    api_key_id=api_key_id,
                    is_internal=is_internal,
                    reserved=reserved,
                    estimated_pages=estimated_pages,
                    request_id=request_id,
                )
            )

        return payload

    async def get_status(self, job_id: UUID, organisation_id: UUID) -> dict[str, Any]:
        job = await self.job_store.get_job(job_id)
        if job is None:
            raise NotFoundError("Job not found or expired")
        if job.get("organisation_id") != str(organisation_id):
            raise NotFoundError("Job not found or expired")
        return job

    async def get_result(self, job_id: UUID, organisation_id: UUID) -> dict[str, Any]:
        job = await self.get_status(job_id, organisation_id)
        if job["status"] not in ("succeeded", "partial"):
            raise JobError("job_not_ready", f"Job is in status '{job['status']}'")
        result = await self.job_store.get_result(job_id)
        if result is None:
            raise NotFoundError("Result expired or not available")
        return result


# ---------------------------------------------------------------------------
# Background task — runs with its own DB session, completely independent of
# the HTTP request that spawned it.
# ---------------------------------------------------------------------------


async def _process_job(
    *,
    job_store: JobStore,
    ocr_engine: OCREngine,
    job_id: UUID,
    file_path: Path,
    organisation_id: UUID,
    api_key_id: UUID | None,
    is_internal: bool,
    reserved: int,
    estimated_pages: int,
    request_id: str,
) -> None:
    start = datetime.now(UTC)
    actual_pages = 0
    charged = 0
    error_code: str | None = None
    final_status = "failed"

    bound_log = log.bind(
        job_id=str(job_id),
        org=str(organisation_id),
        request_id=request_id,
    )

    # Open a fresh DB session owned entirely by this background task.
    async with AsyncSessionLocal() as db:
        credits = CreditService(db)

        try:
            await job_store.update_job(
                job_id,
                {
                    "status": "processing",
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
            bound_log.info("job.processing")

            result = await asyncio.wait_for(
                ocr_engine.extract(
                    str(file_path),
                    max_pages=settings.max_pages_per_job,
                    timeout=settings.processing_timeout_seconds,
                ),
                timeout=settings.processing_timeout_seconds,
            )

            actual_pages = result.get("page_count", estimated_pages)
            charged = await credits.settle(
                organisation_id,
                reserved,
                actual_pages,
                reference_id=str(job_id),
                is_internal=is_internal,
            )

            final_status = result.get("status", "succeeded")

            low_conf_pages = [
                p for p in result.get("pages", []) if p.get("status") == "low_confidence"
            ]
            if low_conf_pages:
                bound_log.warning(
                    "job.low_confidence_pages",
                    low_confidence_count=len(low_conf_pages),
                    total_pages=actual_pages,
                    page_numbers=[p["page_number"] for p in low_conf_pages],
                )

            await job_store.set_result(job_id, result)
            await job_store.update_job(
                job_id,
                {
                    "status": final_status,
                    "page_count": actual_pages,
                    "charged_credits": charged,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )

            bound_log.info(
                "job.succeeded",
                status=final_status,
                actual_pages=actual_pages,
                charged_credits=charged,
                device=result.get("device"),
                processing_time_ms=result.get("processing_time_ms"),
            )

            record_ocr_metrics(
                status=final_status,
                actual_pages=actual_pages,
                charged_credits=charged,
                low_confidence_pages=len(low_conf_pages),
                page_durations_seconds=[p.get("seconds", 0.0) for p in result.get("pages", [])],
            )

        except Exception as exc:
            error_code = "processing_error"
            final_status = "failed"
            bound_log.error("job.failed", error=str(exc), exc_info=True)

            try:
                await credits.refund(
                    organisation_id,
                    reserved,
                    reference_id=str(job_id),
                    is_internal=is_internal,
                )
            except Exception as refund_exc:
                bound_log.error("job.refund_failed", error=str(refund_exc))

            await job_store.update_job(
                job_id,
                {
                    "status": "failed",
                    "error_code": error_code,
                    "error_message": str(exc)[:200],
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )

            record_ocr_metrics(
                status="failed",
                actual_pages=actual_pages,
                charged_credits=0,
                low_confidence_pages=0,
                page_durations_seconds=[],
            )

        finally:
            try:
                if file_path.exists():
                    file_path.unlink()
            except OSError:
                pass

            duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            usage = UsageRecord(
                organisation_id=organisation_id,
                api_key_id=api_key_id,
                request_id=request_id,
                job_id=job_id,
                endpoint="/v1/jobs",
                status=final_status,
                http_status=200 if final_status != "failed" else 500,
                pages_processed=actual_pages,
                credits_charged=charged,
                duration_ms=duration_ms,
                error_code=error_code,
            )
            db.add(usage)
            try:
                await db.commit()
            except Exception as commit_exc:
                bound_log.error("job.usage_record_failed", error=str(commit_exc))
                await db.rollback()

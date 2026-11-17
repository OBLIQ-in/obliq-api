from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.db.session import get_db
from obliq_api.dependencies import (
    AuthContext,
    check_rate_limits,
    get_job_store,
    get_ocr_engine,
    get_rate_limiter,
    get_request_id,
    require_scope,
)
from obliq_api.protocols import JobStore, OCREngine, RateLimiter
from obliq_api.schemas.common import JobStatusResponse, OCRResult
from obliq_api.services.jobs import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=202)
async def submit_job(
    request: Request,
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ctx: AuthContext = Depends(require_scope("ocr:write")),
    db: AsyncSession = Depends(get_db),
    job_store: JobStore = Depends(get_job_store),
    ocr: OCREngine = Depends(get_ocr_engine),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    request_id = await get_request_id(request)
    await check_rate_limits(request, ctx, limiter)
    service = JobService(db, job_store, ocr)
    job = await service.submit(
        file,
        organisation_id=ctx.organisation_id,
        api_key_id=ctx.api_key.id if ctx.api_key else None,
        is_internal=ctx.is_internal,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )
    return {"id": job["id"], "status": job["status"]}


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    ctx: AuthContext = Depends(require_scope("ocr:read")),
    db: AsyncSession = Depends(get_db),
    job_store: JobStore = Depends(get_job_store),
    ocr: OCREngine = Depends(get_ocr_engine),
) -> JobStatusResponse:
    service = JobService(db, job_store, ocr)
    job = await service.get_status(job_id, ctx.organisation_id)
    return JobStatusResponse(
        id=job_id,
        status=job["status"],
        page_count=job.get("page_count") or job.get("estimated_pages"),
        created_at=job.get("created_at"),
        updated_at=job.get("updated_at"),
        error_code=job.get("error_code"),
        error_message=job.get("error_message"),
    )


@router.get("/{job_id}/result", response_model=OCRResult)
async def get_job_result(
    job_id: UUID,
    ctx: AuthContext = Depends(require_scope("ocr:read")),
    db: AsyncSession = Depends(get_db),
    job_store: JobStore = Depends(get_job_store),
    ocr: OCREngine = Depends(get_ocr_engine),
) -> OCRResult:
    service = JobService(db, job_store, ocr)
    result = await service.get_result(job_id, ctx.organisation_id)
    return OCRResult(
        job_id=job_id,
        page_count=result["page_count"],
        pages=result["pages"],
        status=result["status"],
        processing_time_ms=result.get("processing_time_ms"),
        device=result.get("device"),
    )

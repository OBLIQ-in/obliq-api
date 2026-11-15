from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from obliq_api.db.session import get_db
from obliq_api.dependencies import get_job_store, get_ocr_engine
from obliq_api.protocols import JobStore, OCREngine
from obliq_api.schemas.common import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready(
    db: AsyncSession = Depends(get_db),
    job_store: JobStore = Depends(get_job_store),
    ocr: OCREngine = Depends(get_ocr_engine),
) -> ReadyResponse:
    checks: dict[str, bool] = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Job store
    checks["job_store"] = await job_store.health_check()

    # OCR engine
    checks["ocr_engine"] = await ocr.health_check()

    status = "ok" if all(checks.values()) else "degraded"
    return ReadyResponse(status=status, checks=checks)

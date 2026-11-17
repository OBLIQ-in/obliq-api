from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from obliq_api.api.dashboard import router as dashboard_router
from obliq_api.api.health import router as health_router
from obliq_api.api.ui import router as ui_router
from obliq_api.api.v1.auth import router as auth_router
from obliq_api.api.v1.jobs import router as jobs_router
from obliq_api.api.v1.keys import router as keys_router
from obliq_api.api.v1.orgs import router as orgs_router
from obliq_api.config import get_settings
from obliq_api.dependencies import get_job_store, get_ocr_engine, get_rate_limiter
from obliq_api.exceptions import ObliqError
from obliq_api.logging_config import configure_logging
from obliq_api.middleware.request_id import RequestIdMiddleware
from obliq_api.observability import configure_telemetry
from obliq_api.schemas.common import ErrorDetail, ErrorResponse

# Configure structured logging as early as possible so every log call
# (including those that fire during import) uses the right format.
configure_logging()

settings = get_settings()
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm OCR engine and Redis connection
    log.info("startup.begin", env=settings.app_env)
    ocr = get_ocr_engine()
    ocr_ok = await ocr.health_check()
    log.info("startup.ocr_engine", ok=ocr_ok)

    store = get_job_store()
    store_ok = await store.health_check()
    log.info("startup.job_store", ok=store_ok)

    yield

    # Shutdown
    log.info("shutdown.begin")
    if hasattr(store, "close"):
        await store.close()  # type: ignore[union-attr]
    limiter = get_rate_limiter()
    if hasattr(limiter, "close"):
        await limiter.close()  # type: ignore[union-attr]
    log.info("shutdown.complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Obliq API",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    # OpenTelemetry — must happen after the app object exists
    configure_telemetry(app)

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────

    @app.exception_handler(ObliqError)
    async def obliq_error_handler(request: Request, exc: ObliqError) -> ORJSONResponse:
        request_id = getattr(request.state, "request_id", None)
        log.warning(
            "request.error",
            code=exc.code,
            status=exc.status_code,
            request_id=request_id,
            path=request.url.path,
        )
        body = ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                details=exc.details,
                request_id=request_id,
            )
        )
        headers = {}
        if exc.code == "rate_limit_exceeded" and "retry_after" in exc.details:
            headers["Retry-After"] = str(exc.details["retry_after"])
        return ORJSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> ORJSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            error=ErrorDetail(
                code="http_error",
                message=str(exc.detail),
                request_id=request_id,
            )
        )
        return ORJSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> ORJSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            error=ErrorDetail(
                code="validation_error",
                message="Request validation failed",
                details={"errors": exc.errors()},
                request_id=request_id,
            )
        )
        return ORJSONResponse(status_code=422, content=body.model_dump())

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(ui_router)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(jobs_router, prefix=settings.api_v1_prefix)
    app.include_router(keys_router, prefix=settings.api_v1_prefix)
    app.include_router(orgs_router, prefix=settings.api_v1_prefix)
    app.include_router(dashboard_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()


# Required on Windows: multiprocessing 'spawn' re-imports this module in
# each worker process. Without this guard the entire app would initialise
# (including settings validation) inside every OCR worker process.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("obliq_api.main:app", host="0.0.0.0", port=8000, reload=True)

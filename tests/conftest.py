import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

from obliq_api import dependencies
from obliq_api.db.session import get_db
import obliq_api.main
from obliq_api.main import create_app


def pytest_sessionfinish(session, exitstatus):
    """Shutdown OpenTelemetry background exporters so they don't log on closed stdout."""
    try:
        from opentelemetry import metrics, trace
        tp = trace.get_tracer_provider()
        if hasattr(tp, "shutdown"):
            tp.shutdown()
        mp = metrics.get_meter_provider()
        if hasattr(mp, "shutdown"):
            mp.shutdown()
    except Exception:
        pass


class MockJobStore:
    """In-memory stub for RedisJobStore so tests don't touch live Redis."""
    def __init__(self):
        self.jobs = {}
        self.results = {}

    async def health_check(self) -> bool:
        return True

    async def create_job(self, job_id, payload, ttl=None):
        self.jobs[str(job_id)] = payload

    async def get_job(self, job_id):
        return self.jobs.get(str(job_id))

    async def update_job(self, job_id, updates, ttl=None):
        if str(job_id) in self.jobs:
            self.jobs[str(job_id)].update(updates)

    async def set_result(self, job_id, result, ttl=None):
        self.results[str(job_id)] = result

    async def get_result(self, job_id):
        return self.results.get(str(job_id))

    async def delete_job(self, job_id):
        self.jobs.pop(str(job_id), None)
        self.results.pop(str(job_id), None)

    async def close(self):
        pass


class MockRateLimiter:
    """In-memory stub for RateLimiter so tests don't connect to Upstash."""
    async def is_allowed(self, key: str, *, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        return True, 0

    async def health_check(self) -> bool:
        return True

    async def close(self):
        pass


class MockOCREngine:
    """Fast stub for OCR engine."""
    async def health_check(self) -> bool:
        return True

    async def extract(self, file_path, max_pages=None, timeout=None):
        return {
            "page_count": 1,
            "status": "succeeded",
            "device": "cpu",
            "source": file_path,
            "processing_time_ms": 100,
            "pages": [
                {
                    "page_number": 1,
                    "text": "mock text",
                    "confidence": 0.99,
                    "method": "text_layer",
                    "reason": "native text",
                    "n_chars": 9,
                    "seconds": 0.05,
                    "status": "ok",
                }
            ],
        }


@pytest.fixture(autouse=True)
def mock_dependencies_globally(monkeypatch):
    """Automatically patch singletons and OTel so tests run cleanly and fast."""
    job_store = MockJobStore()
    rate_limiter = MockRateLimiter()
    ocr_engine = MockOCREngine()

    monkeypatch.setattr(dependencies, "get_job_store", lambda: job_store)
    monkeypatch.setattr(dependencies, "get_rate_limiter", lambda: rate_limiter)
    monkeypatch.setattr(dependencies, "get_ocr_engine", lambda: ocr_engine)
    monkeypatch.setattr(obliq_api.main, "get_job_store", lambda: job_store)
    monkeypatch.setattr(obliq_api.main, "get_rate_limiter", lambda: rate_limiter)
    monkeypatch.setattr(obliq_api.main, "get_ocr_engine", lambda: ocr_engine)
    monkeypatch.setattr(obliq_api.main, "configure_telemetry", lambda app: None)

    return job_store, rate_limiter, ocr_engine


@pytest.fixture
def app(mock_dependencies_globally):
    job_store, rate_limiter, ocr_engine = mock_dependencies_globally
    app_instance = create_app()

    # Mock DB session in dependency overrides
    async def override_get_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        yield mock_session

    app_instance.dependency_overrides[get_db] = override_get_db
    app_instance.dependency_overrides[dependencies.get_job_store] = lambda: job_store
    app_instance.dependency_overrides[dependencies.get_rate_limiter] = lambda: rate_limiter
    app_instance.dependency_overrides[dependencies.get_ocr_engine] = lambda: ocr_engine

    return app_instance


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

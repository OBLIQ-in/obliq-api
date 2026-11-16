"""Contract tests for /v1/jobs endpoints matching obliq-in-app expectations."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from obliq_api import dependencies
from obliq_api.dependencies import AuthContext
from obliq_api.models.api_key import ApiKey
from tests.contract.client import ObliqClient


@pytest.fixture
def auth_override(app):
    """Overrides require_api_key dependency so authentication succeeds."""
    org_id = uuid4()
    dummy_key = ApiKey(
        id=uuid4(), organisation_id=org_id, name="contract-test-key", key_prefix="obliq_live_"
    )
    auth_ctx = AuthContext(organisation_id=org_id, api_key=dummy_key, is_internal=False)
    app.dependency_overrides[dependencies.require_api_key] = lambda: auth_ctx
    return auth_ctx


@pytest.mark.asyncio
async def test_submit_job_contract_shape(
    client: AsyncClient, auth_override, monkeypatch: pytest.MonkeyPatch
):
    """
    Contract: POST /v1/jobs
    - Status code: 202 Accepted
    - Body fields: 'id' (UUID string), 'status' ('queued')
    """
    mock_job_id = uuid4()

    async def mock_submit(*args, **kwargs):
        return {"id": str(mock_job_id), "status": "queued"}

    monkeypatch.setattr("obliq_api.services.jobs.JobService.submit", mock_submit)

    obliq_client = ObliqClient(client, api_key="obliq_live_mock_key")
    resp = await obliq_client.submit_job(
        b"%PDF-1.4 mock pdf content",
        filename="contract_test.pdf",
        idempotency_key="idemp_12345",
    )

    assert "id" in resp
    assert UUID(resp["id"])
    assert resp["status"] == "queued"


@pytest.mark.asyncio
async def test_get_job_status_contract_shape(
    client: AsyncClient, auth_override, monkeypatch: pytest.MonkeyPatch
):
    """
    Contract: GET /v1/jobs/{job_id}
    - Status code: 200 OK
    - Fields: id, status, page_count, created_at, updated_at
    """
    job_id = uuid4()

    async def mock_get_status(*args, **kwargs):
        return {
            "id": str(job_id),
            "status": "processing",
            "page_count": 3,
            "created_at": "2026-11-15T12:00:00Z",
            "updated_at": "2026-11-15T12:00:05Z",
            "error_code": None,
            "error_message": None,
        }

    monkeypatch.setattr("obliq_api.services.jobs.JobService.get_status", mock_get_status)

    obliq_client = ObliqClient(client, api_key="obliq_live_mock_key")
    status_data = await obliq_client.get_job_status(job_id)

    assert status_data["id"] == str(job_id)
    assert status_data["status"] == "processing"
    assert status_data["page_count"] == 3
    assert "created_at" in status_data
    assert "updated_at" in status_data


@pytest.mark.asyncio
async def test_get_job_result_contract_shape(
    client: AsyncClient, auth_override, monkeypatch: pytest.MonkeyPatch
):
    """
    Contract: GET /v1/jobs/{job_id}/result
    - Status code: 200 OK
    - Fields: job_id, status, page_count, pages (page_number, text, confidence, method)
    """
    job_id = uuid4()

    sample_result = {
        "job_id": str(job_id),
        "status": "succeeded",
        "page_count": 1,
        "processing_time_ms": 420,
        "device": "cpu",
        "source": "contract_test.pdf",
        "pages": [
            {
                "page_number": 1,
                "text": "Sample Extracted Invoice Text",
                "confidence": 0.98,
                "method": "text_layer",
                "reason": "native text",
                "n_chars": 28,
                "seconds": 0.12,
                "status": "ok",
            }
        ],
    }

    async def async_get_result(*a, **k):
        return sample_result

    monkeypatch.setattr("obliq_api.services.jobs.JobService.get_result", async_get_result)

    obliq_client = ObliqClient(client, api_key="obliq_live_mock_key")
    result = await obliq_client.get_job_result(job_id)

    assert result["job_id"] == str(job_id)
    assert result["status"] == "succeeded"
    assert result["page_count"] == 1
    assert len(result["pages"]) == 1

    page = result["pages"][0]
    assert page["page_number"] == 1
    assert "text" in page
    assert page["confidence"] == 0.98
    assert page["method"] == "text_layer"
    assert page["status"] == "ok"


@pytest.mark.asyncio
async def test_client_poll_until_complete(
    client: AsyncClient, auth_override, monkeypatch: pytest.MonkeyPatch
):
    """Tests the client poll_until_complete lifecycle (queued -> succeeded -> fetch result)."""
    job_id = uuid4()
    calls = 0

    async def mock_get_status(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {"id": str(job_id), "status": "processing" if calls == 1 else "succeeded"}

    async def mock_get_result(*args, **kwargs):
        return {
            "job_id": str(job_id),
            "status": "succeeded",
            "page_count": 0,
            "pages": [],
            "processing_time_ms": 150,
            "device": "cpu",
        }

    monkeypatch.setattr("obliq_api.services.jobs.JobService.get_status", mock_get_status)
    monkeypatch.setattr("obliq_api.services.jobs.JobService.get_result", mock_get_result)

    obliq_client = ObliqClient(client, api_key="obliq_live_mock_key")
    result = await obliq_client.poll_until_complete(job_id, poll_interval_seconds=0.01)

    assert result["job_id"] == str(job_id)
    assert result["status"] == "succeeded"
    assert calls >= 2

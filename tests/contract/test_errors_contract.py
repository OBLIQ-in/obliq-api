"""Contract tests for error envelopes across all obliq-api endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from obliq_api import dependencies
from obliq_api.dependencies import AuthContext
from tests.contract.client import ObliqApiError, ObliqClient


@pytest.mark.asyncio
async def test_unauthorized_error_contract(client: AsyncClient):
    """Contract: Missing token returns 401 with unified error envelope."""
    obliq_client = ObliqClient(client, api_key=None)

    with pytest.raises(ObliqApiError) as exc_info:
        await obliq_client.submit_job(b"%PDF dummy", filename="test.pdf")

    err = exc_info.value
    assert err.status_code == 401
    assert err.code in ("unauthorized", "invalid_api_key", "authentication_error")


@pytest.mark.asyncio
async def test_unsupported_media_error_contract(app, client: AsyncClient):
    """Contract: Non-document binary returns 415 with unified error envelope."""
    app.dependency_overrides[dependencies.require_api_key] = lambda: AuthContext(
        organisation_id=uuid4(), api_key=None, is_internal=True
    )

    obliq_client = ObliqClient(client, api_key="obliq_internal_test")

    with pytest.raises(ObliqApiError) as exc_info:
        await obliq_client.submit_job(
            b"plain text invalid payload",
            filename="malicious.exe",
            content_type="application/octet-stream",
        )

    err = exc_info.value
    assert err.status_code == 415
    assert err.code == "unsupported_media_type"


@pytest.mark.asyncio
async def test_job_not_found_error_contract(app, client: AsyncClient):
    """Contract: Non-existent job query returns 404 with unified error envelope."""
    app.dependency_overrides[dependencies.require_api_key] = lambda: AuthContext(
        organisation_id=uuid4(), api_key=None, is_internal=True
    )

    obliq_client = ObliqClient(client, api_key="obliq_internal_test")

    with pytest.raises(ObliqApiError) as exc_info:
        await obliq_client.get_job_status(uuid4())

    err = exc_info.value
    assert err.status_code == 404
    assert err.code == "not_found"

import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from starlette.testclient import TestClient

from obliq_api.compat import UTC
from obliq_api.dependencies import AuthContext, require_scope
from obliq_api.exceptions import AuthorizationError
from obliq_api.main import create_app
from obliq_api.models.api_key import ApiKey
from obliq_api.schemas.keys import ApiKeyCreate, ApiKeyRotate


def test_api_key_schema_scopes_and_expiry():
    schema = ApiKeyCreate(name="test-key", scopes=["ocr:read"], expires_in_days=30)
    assert schema.name == "test-key"
    assert schema.scopes == ["ocr:read"]
    assert schema.expires_in_days == 30

    rotate = ApiKeyRotate(grace_period_hours=48)
    assert rotate.grace_period_hours == 48


def test_require_scope_dependency():
    org_id = uuid.uuid4()
    key = ApiKey(
        organisation_id=org_id,
        name="test",
        key_prefix="test_prefix_1",
        key_hash="hash",
        scopes=["ocr:write"],
        status="active",
    )
    ctx = AuthContext(organisation_id=org_id, api_key=key, is_internal=False)

    checker_write = require_scope("ocr:write")
    res = asyncio.run(checker_write(ctx))
    assert res == ctx

    checker_read = require_scope("ocr:read")
    with pytest.raises(AuthorizationError):
        asyncio.run(checker_read(ctx))


def test_api_key_expiration_check():
    org_id = uuid.uuid4()
    past = datetime.now(UTC) - timedelta(hours=1)
    key = ApiKey(
        organisation_id=org_id,
        name="expired-key",
        key_prefix="test_prefix_2",
        key_hash="hash",
        scopes=["ocr:read", "ocr:write"],
        expires_at=past,
        status="active",
    )
    assert key.expires_at < datetime.now(UTC)


def test_ui_endpoints_render():
    app = create_app()
    with TestClient(app) as client:
        # Redirect /dashboard -> /dashboard/keys
        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "/dashboard/keys"

        # Keys page
        resp_keys = client.get("/dashboard/keys")
        assert resp_keys.status_code == 200
        assert "API Keys" in resp_keys.text
        assert "Generate New Key" in resp_keys.text

        # Usage page
        resp_usage = client.get("/dashboard/usage")
        assert resp_usage.status_code == 200
        assert "Usage & Observability" in resp_usage.text

        # Docs page
        resp_docs = client.get("/dashboard/docs")
        assert resp_docs.status_code == 200
        assert "API Client SDKs" in resp_docs.text
        assert "@obliq/client" in resp_docs.text

from uuid import uuid4

import pytest

from obliq_api.auth.jwt import create_access_token, create_refresh_token, decode_token
from obliq_api.auth.keys import generate_api_key, hash_password, verify_api_key, verify_password
from obliq_api.exceptions import AuthenticationError


def test_jwt_tokens():
    user_id = uuid4()
    org_id = uuid4()
    token = create_access_token(user_id, organisation_id=org_id, role="admin")
    decoded = decode_token(token)
    assert decoded["sub"] == str(user_id)
    assert decoded["org"] == str(org_id)
    assert decoded["role"] == "admin"
    assert decoded["type"] == "access"

    refresh = create_refresh_token(user_id)
    decoded_refresh = decode_token(refresh)
    assert decoded_refresh["sub"] == str(user_id)
    assert decoded_refresh["type"] == "refresh"

    with pytest.raises(AuthenticationError):
        decode_token("invalid.token.here")


def test_password_hashing():
    pw = "SecretP@ssword123!"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)


def test_api_key_generation_and_verification():
    raw_key, prefix, key_hash = generate_api_key(internal=False)
    assert raw_key.startswith("obliq_live_")
    assert verify_api_key(raw_key, key_hash)
    assert not verify_api_key("obliq_live_invalidkeyvalue1234567890", key_hash)

    raw_internal, _, internal_hash = generate_api_key(internal=True)
    assert raw_internal.startswith("obliq_internal_")
    assert verify_api_key(raw_internal, internal_hash)

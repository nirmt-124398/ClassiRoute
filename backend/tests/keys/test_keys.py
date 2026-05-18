from __future__ import annotations

import pytest

from tests.helpers import api_call


@pytest.mark.integration
@pytest.mark.asyncio
async def test_keys_list_requires_auth(client):
    call = await api_call(client, "GET", "/keys/list")
    assert call.status_code in {401, 422}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_keys_create_list_revoke_delete_roundtrip(jwt_headers, encryption_key, client):
    payload = {
        "name": "test-key",
        "weak_model": "gpt-4o-mini",
        "weak_api_key": "sk-test-weak",
        "weak_base_url": "https://example.com",
        "mid_model": "gpt-4o-mini",
        "mid_api_key": "sk-test-mid",
        "mid_base_url": "https://example.com",
        "strong_model": "gpt-4o-mini",
        "strong_api_key": "sk-test-strong",
        "strong_base_url": "https://example.com",
    }
    created = await api_call(client, "POST", "/keys/create", headers=jwt_headers, json_body=payload)
    assert created.status_code == 200
    assert isinstance(created.response_json, dict)
    key_id = created.response_json.get("key_id")
    raw_key = created.response_json.get("key")
    assert key_id
    assert raw_key and raw_key.startswith("lmr-")

    listed = await api_call(client, "GET", "/keys/list", headers=jwt_headers)
    assert listed.status_code == 200
    assert any(item.get("key_id") == key_id for item in (listed.response_json or []))

    revoked = await api_call(client, "POST", "/keys/revoke", headers=jwt_headers, json_body={"key_id": key_id})
    assert revoked.status_code == 200
    assert revoked.response_json == {"success": True} or (isinstance(revoked.response_json, dict) and revoked.response_json.get("success") is True)

    deleted = await api_call(client, "DELETE", f"/keys/{key_id}", headers=jwt_headers)
    assert deleted.status_code == 200
    assert isinstance(deleted.response_json, dict)
    assert deleted.response_json.get("success") is True

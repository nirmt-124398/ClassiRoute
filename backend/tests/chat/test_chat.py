from __future__ import annotations

import pytest

from tests.helpers import api_call


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_requires_virtual_key_header(client):
    call = await api_call(client, "POST", "/v1/chat/completions", json_body={"messages": [{"role": "user", "content": "hi"}]})
    assert call.status_code in {401, 422}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_rejects_jwt_on_virtual_key_route(jwt_headers, client):
    call = await api_call(client, "POST", "/v1/chat/completions", headers=jwt_headers, json_body={"messages": [{"role": "user", "content": "hi"}]})
    assert call.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_with_virtual_key_structure(vkey_headers, client):
    # This may return 502 if upstream model credentials/base_url are not valid; we still validate auth passed.
    call = await api_call(
        client,
        "POST",
        "/v1/chat/completions",
        headers=vkey_headers,
        json_body={
            "model": "ignored-by-router",
            "messages": [{"role": "user", "content": "Say 'ok'"}],
            "stream": False,
        },
        timeout=40.0,
    )
    assert call.status_code in {200, 502}
    if call.status_code == 200:
        assert isinstance(call.response_json, dict)
        assert "x-llmrouter" in call.response_json


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_streaming(vkey_headers, client):
    response = await client.post(
        "/v1/chat/completions",
        headers=vkey_headers,
        json={
            "model": "ignored-by-router",
            "messages": [{"role": "user", "content": "stream test"}],
            "stream": True,
        },
        timeout=40.0,
    )
    # If upstream fails, API returns 502. Otherwise, we expect streaming SSE content.
    assert response.status_code in {200, 502}
    if response.status_code == 200:
        text = response.text
        assert text.startswith("data:")
        assert text.endswith("\n\n")

from __future__ import annotations

import pytest

from tests.helpers import api_call


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unsupported_method_returns_405(client):
    call = await api_call(client, "PUT", "/health")
    assert call.status_code == 405


@pytest.mark.integration
@pytest.mark.asyncio
async def test_keys_create_validation_error(jwt_headers, client):
    call = await api_call(client, "POST", "/keys/create", headers=jwt_headers, json_body={"name": "x"})
    assert call.status_code == 422

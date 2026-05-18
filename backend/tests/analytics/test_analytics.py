from __future__ import annotations

import pytest

from tests.helpers import api_call


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analytics_requires_auth(client):
    call = await api_call(client, "GET", "/analytics/summary")
    assert call.status_code in {401, 422}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analytics_summary(jwt_headers, client):
    call = await api_call(client, "GET", "/analytics/summary?days=1", headers=jwt_headers)
    assert call.status_code == 200
    assert isinstance(call.response_json, dict)
    assert "total_requests" in call.response_json


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analytics_requests(jwt_headers, client):
    call = await api_call(client, "GET", "/analytics/requests?limit=5&offset=0", headers=jwt_headers)
    assert call.status_code == 200
    assert isinstance(call.response_json, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analytics_daily(jwt_headers, client):
    call = await api_call(client, "GET", "/analytics/daily?days=1", headers=jwt_headers)
    assert call.status_code == 200
    assert isinstance(call.response_json, list)

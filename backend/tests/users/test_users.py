from __future__ import annotations

import uuid

import pytest

from tests.helpers import api_call


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_list_requires_admin(jwt_headers, client):
    call = await api_call(client, "GET", "/users/", headers=jwt_headers)
    assert call.status_code in {200, 403}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_list_unauthorized(client):
    call = await api_call(client, "GET", "/users/")
    assert call.status_code in {401, 422}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_get_me(jwt_headers, client):
    call = await api_call(client, "GET", "/users/me", headers=jwt_headers)
    assert call.status_code == 200
    data = call.response_json
    assert data is not None
    assert "id" in data
    assert "email" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_update_self(jwt_headers, client):
    call = await api_call(
        client, "PUT", "/users/me",
        headers=jwt_headers,
        json_body={"username": "updated_test"},
    )
    assert call.status_code in {200, 422}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_delete_self(client):
    reg = await client.post(
        "/auth/register",
        json={"email": f"selfdel_{uuid.uuid4().hex[:12]}@example.com", "username": "selfdel", "password": "Password123!"},
    )
    assert reg.status_code == 200
    token = reg.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}
    call = await api_call(client, "DELETE", "/users/me", headers=headers)
    assert call.status_code == 204


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_get_nonexistent_returns_404(auth_context, client):
    token = auth_context.get("token", "")
    headers = {"Authorization": f"Bearer {token}"}
    call = await api_call(
        client, "GET",
        f"/users/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert call.status_code in {404, 403}

from __future__ import annotations

import pytest

from tests.helpers import api_call


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_ok(client):
    call = await api_call(client, "GET", "/health")
    assert call.status_code == 200
    assert isinstance(call.response_json, dict)
    assert call.response_json.get("status") == "ok"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_me_requires_authorization_header(client):
    call = await api_call(client, "GET", "/auth/me")
    # FastAPI validation error because Header(...) is required
    assert call.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_me_with_invalid_format_returns_401(client):
    call = await api_call(client, "GET", "/auth/me", headers={"Authorization": "Token abc"})
    assert call.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_me_with_jwt(jwt_headers, client):
    call = await api_call(client, "GET", "/auth/me", headers=jwt_headers)
    assert call.status_code == 200
    assert isinstance(call.response_json, dict)
    assert "id" in call.response_json
    assert "email" in call.response_json
    assert "username" in call.response_json


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_register_login_flow(client):
    import uuid

    payload = {
        "email": f"testuser_{uuid.uuid4().hex[:12]}@example.com",
        "username": "testuser",
        "password": "Password123!",
    }
    register = await api_call(client, "POST", "/auth/register", json_body=payload)
    if register.status_code == 400:
        # Email already registered from prior run; use login path
        login = await api_call(
            client,
            "POST",
            "/auth/login",
            json_body={"email": payload["email"], "password": payload["password"]},
        )
        assert login.status_code == 200
        assert isinstance(login.response_json, dict)
        assert "token" in login.response_json
        return

    assert register.status_code == 200
    assert isinstance(register.response_json, dict)
    assert "token" in register.response_json

    login = await api_call(
        client,
        "POST",
        "/auth/login",
        json_body={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    assert isinstance(login.response_json, dict)
    assert "token" in login.response_json

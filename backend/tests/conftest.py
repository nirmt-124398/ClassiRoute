from __future__ import annotations

import os
from pathlib import Path
import httpx
import pytest
import pytest_asyncio
import uuid
from dotenv import load_dotenv

from tests.config import load_config
from tests.helpers import next_report_dir, should_run_integration


def pytest_configure(config: pytest.Config) -> None:
    load_dotenv(override=False)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if should_run_integration():
        return

    skip = pytest.mark.skip(reason="Set RUN_INTEGRATION=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--report-dir",
        action="store",
        default=None,
        help="Directory to write reports into (default: reports/vN)",
    )


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def report_dir(request: pytest.FixtureRequest) -> Path:
    # If caller provided explicit report dir, use it as-is.
    # Otherwise allocate versioned directory reports/vN.
    opt = request.config.getoption("--report-dir")
    env_opt = os.getenv("PYTEST_REPORT_DIR")
    chosen = opt or env_opt
    if chosen:
        out = Path(chosen)
        out.mkdir(parents=True, exist_ok=True)
        return out

    root = Path("reports")
    return next_report_dir(root)


@pytest.fixture(scope="session")
def json_report_path(report_dir: Path) -> Path:
    return report_dir / "pytest-report.json"


@pytest_asyncio.fixture(scope="session")
async def client(cfg):
    async with httpx.AsyncClient(base_url=cfg.base_url) as c:
        yield c


@pytest.fixture(autouse=True, scope="session")
def _wire_pytest_json_report(json_report_path: Path) -> None:
    # pytest-json-report reads its file path from CLI; we also set env var used by our helper tests.
    os.environ.setdefault("PYTEST_JSON_REPORT_FILE", str(json_report_path))


@pytest_asyncio.fixture(scope="session")
async def auth_context(cfg, client) -> dict[str, str]:
    if cfg.jwt_token:
        return {"token": cfg.jwt_token, "email": "", "password": ""}

    email = f"test_{uuid.uuid4().hex[:12]}@example.com"
    password = "Password123!"
    register = await client.post(
        "/auth/register",
        json={"email": email, "username": "testuser", "password": password},
    )
    if register.status_code == 200:
        token = register.json().get("token")
        return {"token": token, "email": email, "password": password}

    login = await client.post("/auth/login", json={"email": email, "password": password})
    if login.status_code == 200:
        token = login.json().get("token")
        return {"token": token, "email": email, "password": password}

    pytest.fail(f"Unable to register or login test user. register={register.status_code} login={login.status_code}")
    return {"token": "", "email": "", "password": ""}


@pytest_asyncio.fixture(scope="session")
async def jwt_headers(auth_context) -> dict[str, str]:
    token = auth_context.get("token")
    if not token:
        pytest.skip("TEST_JWT not set and auth setup failed")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="session")
async def vkey_headers(cfg, client, jwt_headers) -> dict[str, str]:
    if cfg.virtual_key:
        return {"Authorization": f"Bearer {cfg.virtual_key}"}

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
    created = await client.post("/keys/create", headers=jwt_headers, json=payload)
    if created.status_code != 200:
        pytest.skip(f"Unable to create virtual key: {created.status_code}")
    raw_key = created.json().get("key")
    if not raw_key:
        pytest.skip("Virtual key missing from response")
    return {"Authorization": f"Bearer {raw_key}"}


@pytest.fixture(scope="session")
def encryption_key(cfg) -> str:
    if not cfg.encryption_key:
        pytest.skip("ENCRYPTION_KEY not set")
    return cfg.encryption_key

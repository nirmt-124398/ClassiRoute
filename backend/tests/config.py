from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TestConfig:
    base_url: str
    jwt_token: str | None
    virtual_key: str | None
    encryption_key: str | None


def load_config() -> TestConfig:
    return TestConfig(
        base_url=os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000"),
        jwt_token=os.getenv("TEST_JWT"),
        virtual_key=os.getenv("TEST_VIRTUAL_KEY"),
        encryption_key=os.getenv("ENCRYPTION_KEY"),
    )

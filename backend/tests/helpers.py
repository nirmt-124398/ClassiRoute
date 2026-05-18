from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class ApiCall:
    method: str
    url: str
    request_headers: dict[str, str]
    request_json: Any | None
    status_code: int
    response_headers: dict[str, str]
    response_json: Any | None
    response_text: str
    elapsed_ms: int


def auth_header_jwt(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def auth_header_virtual_key(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def should_run_integration() -> bool:
    return os.getenv("RUN_INTEGRATION", "0") in {"1", "true", "True"}


def next_report_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    existing = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("v")]
    max_n = 0
    for p in existing:
        try:
            n = int(p.name[1:])
        except ValueError:
            continue
        max_n = max(max_n, n)
    out = root / f"v{max_n + 1}"
    out.mkdir(parents=True, exist_ok=True)
    return out


async def api_call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    timeout: float = 20.0,
) -> ApiCall:
    url = str(client.base_url) + path
    req_headers = headers or {}
    resp = await client.request(method, path, headers=req_headers, json=json_body, timeout=timeout)

    try:
        resp_json = resp.json()
    except Exception:
        resp_json = None

    elapsed_ms = int(resp.elapsed.total_seconds() * 1000)

    call = ApiCall(
        method=method.upper(),
        url=url,
        request_headers=req_headers,
        request_json=json_body,
        status_code=resp.status_code,
        response_headers=dict(resp.headers),
        response_json=resp_json,
        response_text=resp.text,
        elapsed_ms=elapsed_ms,
    )

    report_dir = os.getenv("PYTEST_REPORT_DIR")
    if report_dir:
        out = Path(report_dir) / "api-calls.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text("", encoding="utf-8")
        with out.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "method": call.method,
                        "url": call.url,
                        "request_headers": call.request_headers,
                        "request_json": call.request_json,
                        "status_code": call.status_code,
                        "response_headers": call.response_headers,
                        "response_json": call.response_json,
                        "response_text": call.response_text,
                        "elapsed_ms": call.elapsed_ms,
                    },
                    default=str,
                )
                + "\n"
            )

    return call


def json_dumps_safe(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)

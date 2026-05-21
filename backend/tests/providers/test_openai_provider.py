from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.providers.openai import OpenAIProvider


@pytest.fixture
def fake_openai_module() -> MagicMock:
    """Provide a fake openai module so that `from openai import AsyncOpenAI`
    works at runtime inside the adapter methods."""
    mod = MagicMock()
    # Must be a class, not a Mock, so ``isinstance`` protocol checks pass
    mod.AsyncOpenAI = MagicMock(name="AsyncOpenAI")
    return mod


@pytest.fixture
def provider(fake_openai_module: MagicMock) -> OpenAIProvider:
    return OpenAIProvider()


@pytest.fixture(autouse=True)
def _patch_openai_module(fake_openai_module: MagicMock):
    """Inject the fake openai module into sys.modules for every test."""
    with patch.dict("sys.modules", {"openai": fake_openai_module}):
        yield


@pytest.fixture
def mock_openai_response() -> MagicMock:
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = "Hello from OpenAI"
    mock.model = "gpt-4o-mini"
    mock.usage = MagicMock()
    mock.usage.prompt_tokens = 10
    mock.usage.completion_tokens = 20
    mock.usage.total_tokens = 30
    return mock


@pytest.fixture
def mock_openai_stream_chunks() -> list[MagicMock]:
    chunk1 = MagicMock()
    chunk1.model_dump.return_value = {
        "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]
    }
    chunk2 = MagicMock()
    chunk2.model_dump.return_value = {
        "choices": [{"delta": {"content": " world"}, "finish_reason": None}]
    }
    chunk3 = MagicMock()
    chunk3.model_dump.return_value = {
        "choices": [{"delta": {"content": ""}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    return [chunk1, chunk2, chunk3]


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_chat_returns_normalized_dict(
        self, provider: OpenAIProvider, mock_openai_response: MagicMock
    ) -> None:
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_response
            )

            result = await provider.chat(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
                api_key="test-key",
                base_url="https://api.openai.com/v1",
            )

        assert result["content"] == "Hello from OpenAI"
        assert result["model"] == "gpt-4o-mini"
        assert result["provider"] == "openai"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 20
        assert result["usage"]["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_chat_passes_provider_label(
        self, provider: OpenAIProvider, mock_openai_response: MagicMock
    ) -> None:
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_response
            )

            result = await provider.chat(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
                api_key="test-key",
                base_url="https://api.nvidia.com/v1",
                provider_label="nvidia",
            )

        assert result["provider"] == "nvidia"

    @pytest.mark.asyncio
    async def test_chat_stream_yields_dicts(
        self, provider: OpenAIProvider, mock_openai_stream_chunks: list[MagicMock]
    ) -> None:
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            async def async_iter():
                for c in mock_openai_stream_chunks:
                    yield c

            mock_stream = async_iter()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_stream
            )

            chunks = []
            async for chunk in provider.chat_stream(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
                api_key="test-key",
                base_url="https://api.openai.com/v1",
            ):
                chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
        assert chunks[2].get("usage") is not None

    @pytest.mark.asyncio
    async def test_chat_normalizes_sdk_error(
        self, provider: OpenAIProvider
    ) -> None:
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "401 Unauthorized",
                    request=httpx.Request("POST", "http://test"),
                    response=httpx.Response(401),
                )
            )

            with pytest.raises(httpx.HTTPStatusError):
                await provider.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="gpt-4o-mini",
                    api_key="bad-key",
                )

    def test_provider_registered(self) -> None:
        from core.providers.registry import PROVIDER_MAP

        import core.providers.openai  # noqa: F401

        assert "openai" in PROVIDER_MAP
        assert PROVIDER_MAP["openai"] is OpenAIProvider

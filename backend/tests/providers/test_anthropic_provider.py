from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.providers.anthropic import AnthropicProvider


@pytest.fixture
def provider():
    return AnthropicProvider()


@pytest.fixture
def mock_anthropic_response():
    """Simulate an Anthropic Message response."""
    mock = MagicMock()
    mock.content = [MagicMock()]
    mock.content[0].text = "Hello from Claude"
    mock.model = "claude-3-haiku-20240307"
    mock.usage = MagicMock()
    mock.usage.input_tokens = 15
    mock.usage.output_tokens = 25
    return mock


class TestAnthropicProvider:
    @pytest.mark.asyncio
    async def test_chat_returns_normalized_dict(self, provider, mock_anthropic_response):
        with patch("core.providers.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

            result = await provider.chat(
                messages=[{"role": "user", "content": "hi"}],
                model="claude-3-haiku-20240307",
                api_key="test-key",
            )

            assert result["content"] == "Hello from Claude"
            assert result["model"] == "claude-3-haiku-20240307"
            assert result["provider"] == "anthropic"
            assert result["usage"]["prompt_tokens"] == 15
            assert result["usage"]["completion_tokens"] == 25
            assert result["usage"]["total_tokens"] == 40

    @pytest.mark.asyncio
    async def test_chat_extracts_system_prompt(self, provider, mock_anthropic_response):
        with patch("core.providers.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

            result = await provider.chat(
                messages=[
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "hi"},
                ],
                model="claude-3-haiku-20240307",
                api_key="test-key",
            )

            assert result["content"] == "Hello from Claude"

    @pytest.mark.asyncio
    async def test_chat_stream_yields_dicts(self, provider):
        with patch("core.providers.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            # Async generator for text stream (async for requires async iterable)
            async def _text_stream():
                yield "Hello"
                yield " world"

            mock_final = MagicMock()
            mock_final.usage.input_tokens = 10
            mock_final.usage.output_tokens = 20

            mock_stream = AsyncMock()
            mock_stream.__aenter__.return_value = mock_stream
            mock_stream.text_stream = _text_stream()
            mock_stream.get_final_message = AsyncMock(return_value=mock_final)

            # Use explicit MagicMock for messages to avoid AsyncMock child creating
            # AsyncMock children (which return coroutines instead of direct values)
            mock_messages = MagicMock()
            mock_messages.stream.return_value = mock_stream
            mock_client.messages = mock_messages

            chunks = []
            async for chunk in provider.chat_stream(
                messages=[{"role": "user", "content": "hi"}],
                model="claude-3-haiku-20240307",
                api_key="test-key",
            ):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
            assert chunks[1]["choices"][0]["delta"]["content"] == " world"
            assert chunks[2]["choices"][0]["finish_reason"] == "stop"
            assert chunks[2]["usage"]["prompt_tokens"] == 10
            assert chunks[2]["usage"]["completion_tokens"] == 20

    @pytest.mark.asyncio
    async def test_chat_normalizes_api_error(self, provider):
        from anthropic import APIStatusError

        with patch("core.providers.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_response = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com"))
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=APIStatusError(
                    "401 Unauthorized",
                    response=mock_response,
                    body={"error": "invalid api key"},
                )
            )

            with pytest.raises(httpx.HTTPStatusError):
                await provider.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="claude-3-haiku-20240307",
                    api_key="bad-key",
                )

    def test_provider_registered(self):
        from core.providers.registry import PROVIDER_MAP
        import core.providers.anthropic  # noqa: F401

        assert "anthropic" in PROVIDER_MAP
        assert PROVIDER_MAP["anthropic"] is AnthropicProvider

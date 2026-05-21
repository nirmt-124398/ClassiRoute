from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.providers.gemini import GeminiProvider


@pytest.fixture
def provider() -> GeminiProvider:
    return GeminiProvider()


@pytest.fixture
def mock_gemini_response():
    """Simulate a Gemini generate_content response."""
    mock = MagicMock()
    mock.text = "Hello from Gemini"
    mock.usage_metadata = MagicMock()
    mock.usage_metadata.prompt_token_count = 5
    mock.usage_metadata.candidates_token_count = 15
    mock.usage_metadata.total_token_count = 20
    return mock


class TestGeminiProvider:
    @pytest.mark.asyncio
    async def test_chat_returns_normalized_dict(self, provider, mock_gemini_response):
        with patch("core.providers.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                return_value=mock_gemini_response
            )

            result = await provider.chat(
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.0-flash",
                api_key="test-key",
            )

            assert result["content"] == "Hello from Gemini"
            assert result["model"] == "gemini-2.0-flash"
            assert result["provider"] == "gemini"
            assert result["usage"]["prompt_tokens"] == 5
            assert result["usage"]["completion_tokens"] == 15
            assert result["usage"]["total_tokens"] == 20

    @pytest.mark.asyncio
    async def test_chat_with_system_instruction(self, provider, mock_gemini_response):
        with patch("core.providers.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                return_value=mock_gemini_response
            )

            result = await provider.chat(
                messages=[
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "hi"},
                ],
                model="gemini-2.0-flash",
                api_key="test-key",
            )

            assert result["content"] == "Hello from Gemini"
            # Verify system instruction was extracted from messages
            # (message with role=system should not be in the contents list)
            called_args = mock_client.aio.models.generate_content.call_args
            contents = called_args.kwargs.get("contents", called_args[1])
            assert len(contents) == 1
            assert contents[0]["role"] == "user"
            assert contents[0]["parts"][0]["text"] == "hi"

    @pytest.mark.asyncio
    async def test_chat_stream_yields_text_deltas_and_usage(self, provider):
        with patch("core.providers.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            # Simulate streaming chunks
            chunk1 = MagicMock()
            chunk1.text = "Hello"
            chunk1.usage_metadata = None

            chunk2 = MagicMock()
            chunk2.text = " world"
            chunk2.usage_metadata = None

            chunk3 = MagicMock()
            chunk3.text = ""
            chunk3.usage_metadata = MagicMock()
            chunk3.usage_metadata.prompt_token_count = 5
            chunk3.usage_metadata.candidates_token_count = 15
            chunk3.usage_metadata.total_token_count = 20

            mock_stream = AsyncMock()
            mock_stream.__aiter__.return_value = iter([chunk1, chunk2, chunk3])

            mock_client.aio.models.generate_content_stream = AsyncMock(
                return_value=mock_stream
            )

            chunks = []
            async for chunk in provider.chat_stream(
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.0-flash",
                api_key="test-key",
            ):
                chunks.append(chunk)

            # Text deltas
            assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
            assert chunks[1]["choices"][0]["delta"]["content"] == " world"

            # Final chunk with usage
            final = chunks[-1]
            assert final["choices"][0]["delta"]["content"] == ""
            assert final["choices"][0]["finish_reason"] == "stop"
            assert final["usage"]["prompt_tokens"] == 5
            assert final["usage"]["completion_tokens"] == 15
            assert final["usage"]["total_tokens"] == 20

    @pytest.mark.asyncio
    async def test_chat_raises_httpx_error(self, provider):
        with patch("core.providers.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "403 Forbidden",
                    request=MagicMock(spec=httpx.Request),
                    response=MagicMock(spec=httpx.Response, status_code=403),
                )
            )

            with pytest.raises(httpx.HTTPStatusError):
                await provider.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.0-flash",
                    api_key="bad-key",
                )

    @pytest.mark.asyncio
    async def test_chat_wraps_unknown_errors(self, provider):
        with patch("core.providers.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=ValueError("some internal error")
            )

            with pytest.raises(httpx.HTTPStatusError):
                await provider.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.0-flash",
                    api_key="test-key",
                )

    @pytest.mark.asyncio
    async def test_provider_registered(self):
        from core.providers.registry import PROVIDER_MAP

        import core.providers.gemini  # noqa: F401

        assert "gemini" in PROVIDER_MAP
        assert PROVIDER_MAP["gemini"] is GeminiProvider

    @pytest.mark.asyncio
    async def test_chat_stream_raises_httpx_error(self, provider):
        with patch("core.providers.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content_stream = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "403 Forbidden",
                    request=MagicMock(spec=httpx.Request),
                    response=MagicMock(spec=httpx.Response, status_code=403),
                )
            )

            with pytest.raises(httpx.HTTPStatusError):
                async for _ in provider.chat_stream(
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.0-flash",
                    api_key="bad-key",
                ):
                    pass

    @pytest.mark.asyncio
    async def test_chat_usage_defaults_to_zero_when_no_metadata(self, provider):
        with patch("core.providers.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            # Response with no usage_metadata
            resp = MagicMock()
            resp.text = "Hello"
            resp.usage_metadata = None

            mock_client.aio.models.generate_content = AsyncMock(
                return_value=resp
            )

            result = await provider.chat(
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.0-flash",
                api_key="test-key",
            )

            assert result["usage"]["prompt_tokens"] == 0
            assert result["usage"]["completion_tokens"] == 0
            assert result["usage"]["total_tokens"] == 0

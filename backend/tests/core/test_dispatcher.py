from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_virtual_key():
    """Create a VirtualKey-like object for testing."""
    key = MagicMock()
    key.weak_model = "gpt-4o-mini"
    key.weak_api_key = "enc_weak_key"
    key.weak_base_url = "https://api.weak.com"
    key.mid_model = "gpt-4o"
    key.mid_api_key = "enc_mid_key"
    key.mid_base_url = "https://api.mid.com"
    key.strong_model = "gpt-4o-strong"
    key.strong_api_key = "enc_strong_key"
    key.strong_base_url = "https://api.strong.com"
    return key


class TestGetClient:
    """Unit tests for get_client()."""

    def test_returns_client_and_model_for_tier_0(self, mock_virtual_key):
        """get_client returns AsyncOpenAI client and model for weak tier."""
        with patch("core.dispatcher.decrypt", return_value="decrypted_key"):
            with patch("core.dispatcher.AsyncOpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()
                from core.dispatcher import get_client

                client, model = get_client(mock_virtual_key, 0)
                assert model == "gpt-4o-mini"
                mock_openai.assert_called_once_with(
                    api_key="decrypted_key",
                    base_url="https://api.weak.com",
                )

    def test_returns_client_and_model_for_tier_1(self, mock_virtual_key):
        """get_client returns AsyncOpenAI client and model for mid tier."""
        with patch("core.dispatcher.decrypt", return_value="decrypted_key"):
            with patch("core.dispatcher.AsyncOpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()
                from core.dispatcher import get_client

                client, model = get_client(mock_virtual_key, 1)
                assert model == "gpt-4o"
                mock_openai.assert_called_once_with(
                    api_key="decrypted_key",
                    base_url="https://api.mid.com",
                )

    def test_returns_client_and_model_for_tier_2(self, mock_virtual_key):
        """get_client returns AsyncOpenAI client and model for strong tier."""
        with patch("core.dispatcher.decrypt", return_value="decrypted_key"):
            with patch("core.dispatcher.AsyncOpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()
                from core.dispatcher import get_client

                client, model = get_client(mock_virtual_key, 2)
                assert model == "gpt-4o-strong"
                mock_openai.assert_called_once_with(
                    api_key="decrypted_key",
                    base_url="https://api.strong.com",
                )

    def test_calls_decrypt_with_correct_key(self, mock_virtual_key):
        """decrypt is called with the encrypted API key from the virtual key."""
        from core.dispatcher import get_client

        with patch("core.dispatcher.decrypt") as mock_decrypt:
            mock_decrypt.return_value = "decrypted"
            with patch("core.dispatcher.AsyncOpenAI"):
                get_client(mock_virtual_key, 1)
                mock_decrypt.assert_called_once_with("enc_mid_key")

    def test_raises_on_invalid_tier(self, mock_virtual_key):
        """Invalid tier should raise KeyError."""
        from core.dispatcher import get_client

        with patch("core.dispatcher.decrypt", return_value="key"):
            with patch("core.dispatcher.AsyncOpenAI"):
                with pytest.raises(KeyError):
                    get_client(mock_virtual_key, 99)


class TestDispatchStream:
    """Unit tests for dispatch_stream()."""

    @pytest.mark.asyncio
    async def test_creates_streaming_chat(self, mock_virtual_key):
        """dispatch_stream should call create with stream=True."""
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = mock_stream
        mock_stream.__anext__.side_effect = [AsyncMock(), StopAsyncIteration()]

        with patch("core.dispatcher.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_stream
            mock_get_client.return_value = (mock_client, "gpt-4o")

            from core.dispatcher import dispatch_stream

            messages = [{"role": "user", "content": "hi"}]
            result, model = await dispatch_stream(messages, mock_virtual_key, 0)

            assert model == "gpt-4o"
            mock_client.chat.completions.create.assert_called_once_with(
                model="gpt-4o",
                messages=messages,
                stream=True,
            )

    @pytest.mark.asyncio
    async def test_passes_messages_correctly(self, mock_virtual_key):
        """dispatch_stream passes messages to the create call unchanged."""
        messages = [{"role": "system", "content": "be helpful"},
                    {"role": "user", "content": "hello"}]

        with patch("core.dispatcher.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = AsyncMock()
            mock_get_client.return_value = (mock_client, "gpt-4o-mini")

            from core.dispatcher import dispatch_stream
            await dispatch_stream(messages, mock_virtual_key, 0)

            mock_client.chat.completions.create.assert_called_once_with(
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
            )


class TestDispatchSync:
    """Unit tests for dispatch_sync()."""

    @pytest.mark.asyncio
    async def test_creates_non_streaming_chat(self, mock_virtual_key):
        """dispatch_sync should call create with stream=False."""
        mock_response = MagicMock()
        mock_response.choices = []

        with patch("core.dispatcher.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = (mock_client, "gpt-4o-mini")

            from core.dispatcher import dispatch_stream, dispatch_sync

            messages = [{"role": "user", "content": "hi"}]
            response, model = await dispatch_sync(messages, mock_virtual_key, 0)

            assert model == "gpt-4o-mini"
            mock_client.chat.completions.create.assert_called_once_with(
                model="gpt-4o-mini",
                messages=messages,
                stream=False,
            )

    @pytest.mark.asyncio
    async def test_returns_response_and_model(self, mock_virtual_key):
        """dispatch_sync returns a tuple of (response, model_name)."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]

        with patch("core.dispatcher.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = (mock_client, "gpt-4o-mini")

            from core.dispatcher import dispatch_sync
            result = await dispatch_sync([{"role": "user", "content": "hi"}], mock_virtual_key, 0)

            assert len(result) == 2
            response, model = result
            assert model == "gpt-4o-mini"
            assert response.choices is not None

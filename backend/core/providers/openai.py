from typing import Any, AsyncGenerator

import httpx

from core.providers.base import BaseProvider
from core.providers.registry import register_provider

try:
    from openai import APIError as OpenAIAPIError
except ImportError:
    OpenAIAPIError = None  # type: ignore


def _normalize_error(e: Exception) -> httpx.HTTPStatusError:
    """Convert an SDK exception to httpx.HTTPStatusError."""
    if OpenAIAPIError is not None and isinstance(e, OpenAIAPIError):
        request: Any = getattr(e, "request", None)
        response: Any = getattr(e, "response", None)
    else:
        request = None
        response = None
    return httpx.HTTPStatusError(str(e), request=request, response=response)


class OpenAIProvider(BaseProvider):
    """For any OpenAI-compatible provider (NIM, OpenAI, Together, Groq, etc.).
    Uses the existing AsyncOpenAI SDK pattern.
    """

    async def chat(self, messages: list, model: str, api_key: str, **kwargs) -> dict:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=kwargs.get("base_url"))
        try:
            response = await client.chat.completions.create(
                model=model, messages=messages, stream=False
            )
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            raise _normalize_error(e) from e

        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "provider": kwargs.get("provider_label", "openai"),
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
        }

    async def chat_stream(
        self, messages: list, model: str, api_key: str, **kwargs
    ) -> AsyncGenerator[dict, None]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=kwargs.get("base_url"))
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            raise _normalize_error(e) from e

        async for chunk in stream:
            yield chunk.model_dump()


# Register this provider
register_provider("openai", OpenAIProvider)

from typing import AsyncGenerator

from google import genai
from google.genai import types as genai_types

from core.providers.base import BaseProvider
from core.providers.registry import register_provider
import httpx


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini models via the google-genai SDK."""

    async def chat(self, messages: list, model: str, api_key: str, **kwargs) -> dict:
        client = genai.Client(api_key=api_key)
        system_instruction, gemini_contents = _convert_messages(messages)

        config = None
        if system_instruction:
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction
            )

        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=gemini_contents,
                config=config,
            )
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            raise httpx.HTTPStatusError(str(e), request=None, response=None) from e

        return {
            "content": response.text,
            "model": model,
            "provider": "gemini",
            "usage": {
                "prompt_tokens": (
                    response.usage_metadata.prompt_token_count
                    if response.usage_metadata
                    else 0
                ),
                "completion_tokens": (
                    response.usage_metadata.candidates_token_count
                    if response.usage_metadata
                    else 0
                ),
                "total_tokens": (
                    response.usage_metadata.total_token_count
                    if response.usage_metadata
                    else 0
                ),
            },
        }

    async def chat_stream(
        self, messages: list, model: str, api_key: str, **kwargs
    ) -> AsyncGenerator[dict, None]:
        client = genai.Client(api_key=api_key)
        system_instruction, gemini_contents = _convert_messages(messages)

        config = None
        if system_instruction:
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction
            )

        try:
            stream = await client.aio.models.generate_content_stream(
                model=model,
                contents=gemini_contents,
                config=config,
            )
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            raise httpx.HTTPStatusError(str(e), request=None, response=None) from e

        async for chunk in stream:
            if chunk.text:
                yield {"choices": [{"delta": {"content": chunk.text}, "finish_reason": None}]}

            if chunk.usage_metadata:
                yield {
                    "choices": [{"delta": {"content": ""}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": chunk.usage_metadata.prompt_token_count,
                        "completion_tokens": chunk.usage_metadata.candidates_token_count,
                        "total_tokens": chunk.usage_metadata.total_token_count,
                    },
                }


def _convert_messages(messages: list) -> tuple[str | None, list]:
    """Convert OpenAI-format messages to Gemini contents format.

    Returns (system_instruction, gemini_contents).
    """
    system_instruction = None
    gemini_contents = []

    for msg in messages:
        if msg.get("role") == "system":
            if system_instruction is None:
                system_instruction = msg["content"]
            continue

        role = "model" if msg["role"] == "assistant" else "user"
        gemini_contents.append(
            {
                "role": role,
                "parts": [{"text": msg["content"]}],
            }
        )

    return system_instruction, gemini_contents


# Register this provider
register_provider("gemini", GeminiProvider)

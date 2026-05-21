from typing import AsyncGenerator

import httpx
from anthropic import APIStatusError, AsyncAnthropic

from core.providers.base import BaseProvider
from core.providers.registry import register_provider


class AnthropicProvider(BaseProvider):
    """Anthropic API provider using the official anthropic SDK."""

    async def chat(self, messages: list, model: str, api_key: str, **kwargs) -> dict:
        client = AsyncAnthropic(
            api_key=api_key,
            base_url=kwargs.get("base_url"),
        )

        # Extract system prompt — must be top-level field, not in messages array
        system_msg = None
        non_system_messages = messages
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]["content"]
            non_system_messages = messages[1:]

        # Convert to Anthropic message format
        anthropic_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in non_system_messages
        ]

        max_tokens = kwargs.get("max_tokens", 4096)

        try:
            response = await client.messages.create(
                model=model,
                messages=anthropic_messages,
                system=system_msg,
                max_tokens=max_tokens,
                **{k: v for k, v in kwargs.items() if k not in ("max_tokens", "base_url", "provider_label")},
            )
        except APIStatusError as e:
            raise httpx.HTTPStatusError(
                str(e),
                request=e.request,
                response=e.response,
            ) from e

        return {
            "content": response.content[0].text,
            "model": response.model,
            "provider": "anthropic",
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
        }

    async def chat_stream(
        self, messages: list, model: str, api_key: str, **kwargs
    ) -> AsyncGenerator[dict, None]:
        client = AsyncAnthropic(
            api_key=api_key,
            base_url=kwargs.get("base_url"),
        )

        # Extract system prompt
        system_msg = None
        non_system_messages = messages
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]["content"]
            non_system_messages = messages[1:]

        anthropic_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in non_system_messages
        ]

        max_tokens = kwargs.get("max_tokens", 4096)

        try:
            async with client.messages.stream(
                model=model,
                messages=anthropic_messages,
                system=system_msg,
                max_tokens=max_tokens,
                **{k: v for k, v in kwargs.items() if k not in ("max_tokens", "base_url", "provider_label")},
            ) as stream:
                async for text in stream.text_stream:
                    yield {"choices": [{"delta": {"content": text}, "finish_reason": None}]}

                final = await stream.get_final_message()
                yield {
                    "choices": [{"delta": {"content": ""}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": final.usage.input_tokens,
                        "completion_tokens": final.usage.output_tokens,
                        "total_tokens": final.usage.input_tokens + final.usage.output_tokens,
                    },
                }
        except APIStatusError as e:
            raise httpx.HTTPStatusError(
                str(e),
                request=e.request,
                response=e.response,
            ) from e


# Register this provider
register_provider("anthropic", AnthropicProvider)

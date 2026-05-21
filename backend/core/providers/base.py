from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list, model: str, api_key: str, **kwargs) -> dict:
        """Non-streaming chat. Returns normalized response dict:
        { "content": str, "model": str, "provider": str, "usage": {
            "prompt_tokens": int, "completion_tokens": int, "total_tokens": int } }
        """

    @abstractmethod
    async def chat_stream(
        self, messages: list, model: str, api_key: str, **kwargs
    ) -> AsyncGenerator[dict, None]:
        """Streaming chat. Yields normalized dicts matching OpenAI chunk shape:
        { "choices": [{ "delta": { "content": "..." }, "finish_reason": None }] }
        Final chunk includes usage:
        { "choices": [{ "delta": { "content": "" }, "finish_reason": "stop" }],
          "usage": { "prompt_tokens": int, "completion_tokens": int, "total_tokens": int } }
        """

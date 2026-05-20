import logging
from openai import AsyncOpenAI, APIConnectionError
from db.crud import decrypt
from typing import AsyncIterator

logger = logging.getLogger(__name__)

TIER_MAP = {0: "weak", 1: "mid", 2: "strong"}

def get_client(virtual_key, tier: int) -> tuple[AsyncOpenAI, str]:
    t = TIER_MAP[tier]
    model    = getattr(virtual_key, f"{t}_model")
    api_key  = decrypt(getattr(virtual_key, f"{t}_api_key"))
    base_url = getattr(virtual_key, f"{t}_base_url")
    client   = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=None)
    return client, model

async def dispatch_stream(
    messages: list[dict],
    virtual_key,
    tier: int,
) -> AsyncIterator:
    client, model = get_client(virtual_key, tier)
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )
        return stream, model
    except APIConnectionError as e:
        raise ConnectionError(f"Failed to connect to provider for tier {tier} ({model}): {e}") from e

async def dispatch_sync(
    messages: list[dict],
    virtual_key,
    tier: int,
) -> dict:
    client, model = get_client(virtual_key, tier)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
        )
        return response, model
    except APIConnectionError as e:
        raise ConnectionError(f"Failed to connect to provider for tier {tier} ({model}): {e}") from e

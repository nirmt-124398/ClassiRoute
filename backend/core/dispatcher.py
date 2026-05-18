import os
import logging
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError
from db.crud import decrypt
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# Default timeout in seconds — can be overridden via env var
DISPATCH_TIMEOUT = int(os.getenv("DISPATCH_TIMEOUT", "300"))

TIER_MAP = {0: "weak", 1: "mid", 2: "strong"}

def get_client(virtual_key, tier: int) -> tuple[AsyncOpenAI, str]:
    t = TIER_MAP[tier]
    model    = getattr(virtual_key, f"{t}_model")
    api_key  = decrypt(getattr(virtual_key, f"{t}_api_key"))
    base_url = getattr(virtual_key, f"{t}_base_url")
    client   = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=DISPATCH_TIMEOUT)
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
        )
        return stream, model
    except APITimeoutError as e:
        raise TimeoutError(f"Provider call timed out after {DISPATCH_TIMEOUT}s for tier {tier} ({model})") from e
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
    except APITimeoutError as e:
        raise TimeoutError(f"Provider call timed out after {DISPATCH_TIMEOUT}s for tier {tier} ({model})") from e
    except APIConnectionError as e:
        raise ConnectionError(f"Failed to connect to provider for tier {tier} ({model}): {e}") from e

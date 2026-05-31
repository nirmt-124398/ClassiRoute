import logging
from db.crud import decrypt
from core.providers.registry import get_provider

logger = logging.getLogger(__name__)

TIER_MAP = {0: "weak", 1: "mid", 2: "strong"}


async def dispatch_stream(messages, virtual_key, tier: int):
    t = TIER_MAP[tier]
    model = getattr(virtual_key, f"{t}_model")
    api_key = decrypt(getattr(virtual_key, f"{t}_api_key"))
    provider_type = getattr(virtual_key, f"{t}_provider_type", "openai")
    base_url = getattr(virtual_key, f"{t}_base_url")

    provider = get_provider(provider_type)
    return provider.chat_stream(
        messages=messages,
        model=model,
        api_key=api_key,
        base_url=base_url,
        provider_label=provider_type,
    ), model


async def dispatch_sync(messages, virtual_key, tier: int):
    t = TIER_MAP[tier]
    model = getattr(virtual_key, f"{t}_model")
    api_key = decrypt(getattr(virtual_key, f"{t}_api_key"))
    provider_type = getattr(virtual_key, f"{t}_provider_type", "openai")
    base_url = getattr(virtual_key, f"{t}_base_url")

    provider = get_provider(provider_type)
    return await provider.chat(
        messages=messages,
        model=model,
        api_key=api_key,
        base_url=base_url,
        provider_label=provider_type,
    ), model

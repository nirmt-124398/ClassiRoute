from core.providers.base import BaseProvider

PROVIDER_MAP: dict[str, type[BaseProvider]] = {}


def register_provider(name: str, cls: type[BaseProvider]) -> None:
    PROVIDER_MAP[name] = cls


def get_provider(provider_type: str) -> BaseProvider:
    if provider_type not in PROVIDER_MAP:
        raise ValueError(f"Unknown provider: {provider_type}")
    return PROVIDER_MAP[provider_type]()

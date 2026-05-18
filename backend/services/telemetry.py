import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_enabled = False

_api_key = os.getenv("POSTHOG_API_KEY", "")
_host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")

if _api_key and _api_key != "dummy_key_for_dev":
    try:
        import posthog
        posthog.api_key = _api_key
        posthog.host = _host
        _enabled = True
    except Exception as exc:
        logger.warning("Failed to initialize PostHog: %s", exc)
else:
    logger.info("POSTHOG_API_KEY not set — PostHog telemetry disabled")


def capture_request(
    user_id: str,
    event: str = "llm_request",
    properties: dict | None = None,
) -> None:
    if not _enabled:
        return
    if properties is None:
        properties = {}
    try:
        import posthog
        posthog.capture(distinct_id=user_id, event=event, properties=properties)
    except Exception as exc:
        logger.debug("Failed to capture PostHog event: %s", exc)


def capture_error(
    user_id: str,
    error: str,
    context: dict | None = None,
) -> None:
    if not _enabled:
        return
    if context is None:
        context = {}
    try:
        import posthog
        posthog.capture(
            distinct_id=user_id,
            event="llm_request_error",
            properties={"error": error, **context},
        )
    except Exception as exc:
        logger.debug("Failed to capture PostHog error: %s", exc)

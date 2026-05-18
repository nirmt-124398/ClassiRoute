import os
import logging

logger = logging.getLogger(__name__)

_sentry_initialized = False


def init_sentry() -> None:
    """Initialize Sentry SDK if SENTRY_DSN is set. No-op otherwise."""
    global _sentry_initialized

    if _sentry_initialized:
        return

    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        logger.info("SENTRY_DSN not set — Sentry disabled")
        return

    environment = os.getenv("APP_ENV", "development")

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=0.1,
            send_default_pii=False,
            before_send=_before_send,
        )
        _sentry_initialized = True
        logger.info("Sentry initialized for environment=%s", environment)
    except Exception as exc:
        logger.warning("Failed to initialize Sentry: %s", exc)


def _before_send(event: dict, hint: dict) -> dict | None:
    """Filter out noise before sending to Sentry."""
    exc_info = hint.get("exc_info")
    if exc_info:
        exc = exc_info[1]
        # Skip health-check polling noise
        if hasattr(exc, "status_code") and exc.status_code in (404, 422):
            return None
    return event

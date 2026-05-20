# Monitoring: PostHog + Sentry

| Dashboard | Link |
|-----------|------|
| PostHog | <https://us.posthog.com/project/420037/activity/explore> |
| Sentry | <https://nothing-7b.sentry.io/projects/classiroute-api/?project=4511375196749824> |

## Overview

| Service | Purpose | Code |
|---------|---------|------|
| **PostHog** | Product analytics — LLM request events, usage trends | `services/telemetry.py` |
| **Sentry** | Error tracking — unhandled 500s with stack traces | `services/error_tracking.py` |

Both degrade gracefully — leave the env var blank and they're no-ops.

---

## PostHog

### What it tracks
- `llm_request` — every chat completion call (tier, model, latency, tokens)
- `llm_request_error` — failed requests from chat error handlers

### Setup
```env
POSTHOG_API_KEY=phc_xxxxxxxxxxxxxxxxxxxx
POSTHOG_HOST=https://app.posthog.com
```

Get the key at [app.posthog.com](https://app.posthog.com) → Project Settings → Project API Key.

### Verify
```bash
python -c "
from services.telemetry import capture_request
from dotenv import load_dotenv
load_dotenv()
capture_request('test-user', 'manual_test', {'source': 'cli'})
print('Sent!')
"
```
Check **app.posthog.com → Live events**.

---

## Sentry

### What it captures
- All unhandled 500 exceptions (with full stack trace, request URL)
- Skips 404 and 422 (client errors, not bugs)
- Logs `SENTRY_DSN not set — Sentry disabled` when disabled

### Setup
```env
SENTRY_DSN=https://xxxx@xxxx.ingest.us.sentry.io/xxxxx
```

Get the DSN at [sentry.io](https://sentry.io) → Create Project → Python SDK.

Sentinel initialisation runs inside FastAPI's `lifespan` — it only starts when the DSN is set.

### Verify
```bash
python -c "
from dotenv import load_dotenv
load_dotenv()
from services.error_tracking import init_sentry
init_sentry()
import sentry_sdk
sentry_sdk.capture_message('Test from CLI')
print('Sent!')
"
```
Check **sentry.io → Issues**.

---

## How it works

```
User request → API handler → Success → PostHog capture_request()
                             → Error  → Sentry captureException()
                                       → PostHog capture_error()
```

The global exception handler in `main.py` catches unhandled `Exception`s, sends to both Sentry and PostHog, and returns `{"detail": "An internal error occurred"}` with 500 status.

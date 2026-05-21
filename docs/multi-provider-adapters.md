# Multi-Provider Adapters

ClassiRoute now supports **three provider types** natively: OpenAI-compatible, Anthropic, and Gemini. Each tier of a Virtual Key can use a different provider — mix and match as needed.

## Why Multi-Provider?

Before this feature, every tier in a Virtual Key had to be an OpenAI-compatible endpoint (OpenAI, NVIDIA NIM, Together, Groq, etc.). Now you can:

- Use **Claude** (Anthropic) for your strong tier — best for complex reasoning
- Use **Gemini** for your mid tier — fast and cost-effective
- Use **OpenAI-compatible** for your weak tier — cheap and widely available
- Cascade fallback across providers — if Claude fails, it falls back to Gemini, then to OpenAI

All providers normalize to the same output format, so the rest of the system (chat UI, logging, analytics, fallback) works unchanged.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              Provider Registry               │
                    │  PROVIDER_MAP = {                            │
                    │    "openai":     OpenAIProvider,             │
                    │    "anthropic":  AnthropicProvider,          │
                    │    "gemini":     GeminiProvider,             │
                    │  }                                           │
                    └──────────────────┬──────────────────────────┘
                                       │ get_provider(type)
                    ┌──────────────────┼──────────────────────────┐
                    │                  │                          │
              ┌─────▼──────┐   ┌──────▼──────┐   ┌──────▼───────┐
              │  OpenAI     │   │ Anthropic    │   │   Gemini     │
              │  Provider   │   │ Provider     │   │   Provider   │
              │             │   │              │   │              │
              │ AsyncOpenAI │   │ AsyncAnthropic│  │ genai.Client │
              └─────┬───────┘   └──────┬───────┘   └──────┬──────┘
                    │                  │                   │
                    └──────────────────┼───────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │   Normalized OpenAI     │
                          │   Shaped Dict           │
                          │   {                     │
                          │     "content": "...",   │
                          │     "model": "...",     │
                          │     "provider": "...",  │
                          │     "usage": {...}      │
                          │   }                     │
                          └────────────┬────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │      dispatcher.py       │
                          │   (uses get_provider)    │
                          └────────────┬────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │       chat.py            │
                          │  (dict access, no SDK)   │
                          └─────────────────────────┘
```

### The Adapter Pattern

Every provider implements the same `BaseProvider` abstract class:

```python
class BaseProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list, model: str, api_key: str, **kwargs) -> dict:
        """Non-streaming chat. Returns normalized response dict."""

    @abstractmethod
    async def chat_stream(self, messages: list, model: str, api_key: str, **kwargs) -> AsyncGenerator[dict, None]:
        """Streaming chat. Yields normalized dicts matching OpenAI chunk shape."""
```

The dispatcher calls `get_provider(provider_type)` to get the right adapter, then calls `chat()` or `chat_stream()`. The adapter handles all SDK-specific logic and returns a normalized dict.

---

## Provider Types

### OpenAI-compatible (`"openai"`)

Wraps `AsyncOpenAI` from the `openai` SDK. Works with any OpenAI-compatible endpoint:

| Field | Required | Notes |
|---|---|---|
| `base_url` | Yes | e.g. `https://integrate.api.nvidia.com/v1` |
| `api_key` | Yes | Provider API key |
| `model` | Yes | Any model name supported by the endpoint |

**Known compatible endpoints**: OpenAI, NVIDIA NIM, Together AI, Groq, OpenRouter, and any other OpenAI-compatible API.

### Anthropic (`"anthropic"`)

Uses the official `anthropic` SDK (`AsyncAnthropic`). Key differences from OpenAI:

| Field | Required | Notes |
|---|---|---|
| `base_url` | No | Stored as `NULL` in DB. Optional for custom endpoints |
| `api_key` | Yes | Anthropic API key |
| `model` | Yes | Anthropic model name |

**Known models**:
- `claude-3-5-sonnet-20241022`
- `claude-3-5-haiku-20241022`
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

**How it normalizes**:
- Extracts the `system` prompt from the messages array (first message with `role: "system"`) and passes it as a top-level `system` parameter to the Anthropic API
- Converts messages to Anthropic's `{"role": ..., "content": ...}` format
- Maps `usage.input_tokens` / `usage.output_tokens` to the OpenAI shape

### Gemini (`"gemini"`)

Uses the official `google-genai` SDK (`genai.Client`). Key differences:

| Field | Required | Notes |
|---|---|---|
| `base_url` | No | Stored as `NULL` in DB |
| `api_key` | Yes | Google API key |
| `model` | Yes | Gemini model name |

**Known models**:
- `gemini-2.0-flash`
- `gemini-2.0-flash-lite`
- `gemini-2.0-pro`
- `gemini-1.5-flash`
- `gemini-1.5-pro`

**How it normalizes**:
- Converts OpenAI-style messages to Gemini's content format via `_convert_messages()`
- Maps system prompt to `config.system_instruction`
- Maps `usage_metadata.prompt_token_count` / `candidates_token_count` to the OpenAI shape

---

## Database Schema

Each tier now has two new fields:

| Column | Type | Default | Nullable |
|---|---|---|---|
| `weak_provider_type` | VARCHAR(20) | `"openai"` | No |
| `mid_provider_type` | VARCHAR(20) | `"openai"` | No |
| `strong_provider_type` | VARCHAR(20) | `"openai"` | No |
| `weak_base_url` | VARCHAR(500) | — | **Yes** (was No) |
| `mid_base_url` | VARCHAR(500) | — | **Yes** (was No) |
| `strong_base_url` | VARCHAR(500) | — | **Yes** (was No) |

**Backward compatibility**: Existing keys default to `"openai"` provider type, so they continue working without any changes.

Migration: `a775f2f90dcc_add_provider_types_and_make_base_url_nullable.py`

---

## API Changes

### Creating a Virtual Key

`POST /v1/keys` — `CreateKeyPayload` now includes optional provider fields per tier:

```json
{
  "name": "my-key",
  "weak_model": "claude-3-haiku-20240307",
  "weak_api_key": "sk-ant-...",
  "weak_provider_type": "anthropic",
  "mid_model": "gemini-2.0-flash",
  "mid_api_key": "AIza...",
  "mid_provider_type": "gemini",
  "strong_model": "gpt-4o",
  "strong_api_key": "sk-...",
  "strong_provider_type": "openai",
  "strong_base_url": "https://api.openai.com/v1"
}
```

### Provider Verification Endpoints

Two new endpoints for verifying API keys:

| Endpoint | Provider | Request Body | Response |
|---|---|---|---|
| `POST /v1/keys/anthropic/verify` | Anthropic | `{ "api_key": "..." }` | `{ "valid": true/false, "error": "..." }` |
| `POST /v1/keys/gemini/verify` | Gemini | `{ "api_key": "..." }` | `{ "valid": true/false, "error": "..." }` |

The existing `POST /v1/keys/openai/verify` endpoint handles OpenAI-compatible providers.

---

## Frontend Changes

### Keys Page

The Keys page now shows a **provider type dropdown** for each tier:

- **OpenAI-compatible** → shows `base_url` field + free-text model input
- **Anthropic** → hides `base_url`, shows model dropdown with known Claude models
- **Gemini** → hides `base_url`, shows model dropdown with known Gemini models

Each tier is independent — you can mix providers freely.

---

## Adding a New Provider

To add a 4th provider (e.g., Cohere):

1. **Create adapter**: `backend/core/providers/cohere.py`
   ```python
   from core.providers.base import BaseProvider
   from core.providers.registry import register_provider

   class CohereProvider(BaseProvider):
       async def chat(self, messages, model, api_key, **kwargs) -> dict:
           # SDK logic → normalized dict
           ...

       async def chat_stream(self, messages, model, api_key, **kwargs) -> AsyncGenerator[dict, None]:
           # SDK logic → normalized dicts
           ...

   register_provider("cohere", CohereProvider)
   ```

2. **Register in `main.py`**:
   ```python
   import core.providers.cohere  # triggers register_provider() at startup
   ```

3. **Add verification endpoint**: `backend/api/v1/keys_cohere.py`
4. **Register in `main.py`**: `app.include_router(keys_cohere.router, prefix="/v1/keys")`
5. **Update frontend**: Add `"cohere"` to `PROVIDER_OPTIONS` in `Keys.tsx` and `KNOWN_MODELS` if applicable

---

## Error Handling

Each adapter normalizes SDK-specific exceptions to `httpx.HTTPStatusError`. This means `chat.py` doesn't need to know about provider-specific error types — it catches one exception type for all providers.

```python
try:
    response = await client.messages.create(...)
except APIStatusError as e:
    raise httpx.HTTPStatusError(
        str(e),
        request=e.request,
        response=e.response,
    ) from e
```

---

## Testing

Unit tests for all adapters live in `backend/tests/providers/`:

| File | Tests |
|---|---|
| `test_openai_provider.py` | 5 tests — chat, streaming, error handling, registration |
| `test_anthropic_provider.py` | 5 tests — chat, system prompt extraction, streaming, error handling, registration |
| `test_gemini_provider.py` | 8 tests — chat, streaming, message conversion, error handling, registration |

Run all provider tests:

```bash
cd backend && uv run pytest tests/providers/ -v
```

Integration tests are gated behind `RUN_INTEGRATION=1` and require real API keys.

---

## File Structure

```
backend/
├── core/
│   ├── providers/
│   │   ├── __init__.py          # Empty package init
│   │   ├── base.py              # BaseProvider ABC
│   │   ├── registry.py          # PROVIDER_MAP + get_provider()
│   │   ├── openai.py            # OpenAIProvider
│   │   ├── anthropic.py         # AnthropicProvider
│   │   └── gemini.py            # GeminiProvider
│   └── dispatcher.py            # Uses get_provider() from registry
├── api/v1/
│   ├── chat.py                  # Dict access patterns (no SDK)
│   ├── keys.py                  # KeyCreateRequest with provider_type
│   ├── keys_anthropic.py        # Anthropic verification endpoint
│   └── keys_gemini.py           # Gemini verification endpoint
├── db/
│   ├── models.py                # VirtualKey with provider_type columns
│   └── crud.py                  # Updated with provider_type params
├── tests/providers/
│   ├── test_openai_provider.py
│   ├── test_anthropic_provider.py
│   └── test_gemini_provider.py
└── alembic/versions/
    └── a775f2f90dcc_add_provider_types_and_make_base_url_nullable.py

frontend/
├── src/api/
│   └── keys.ts                  # CreateKeyPayload with provider_type
└── src/pages/
    └── Keys.tsx                 # Provider dropdowns per tier
```

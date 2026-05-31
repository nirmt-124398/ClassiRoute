# ClassiRoute Architecture

> Cost-aware intelligent LLM routing engine. Classifies prompts via XGBoost and routes to the cheapest adequate model tier across OpenAI, Anthropic, and Gemini.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [The Request Journey](#2-the-request-journey)
3. [ML Pipeline](#3-ml-pipeline)
4. [Provider System](#4-provider-system)
5. [Data Model](#5-data-model)
6. [API Layer](#6-api-layer)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Deployment Architecture](#8-deployment-architecture)

---

## 1. System Overview

ClassiRoute is a two-tier application: a **React + Vite frontend** (deployed on Vercel) talks to a **FastAPI backend** (deployed on Render) backed by **PostgreSQL** (via Render Managed Postgres or Docker). ML models (XGBoost classifier + regression) sit on disk and load at startup.

### High-Level Architecture

```
                          ┌──────────────────────────────────────────┐
                          │              Frontend (Vercel)            │
                          │  React + Vite + Tailwind CSS + shadcn/ui │
                          │  SPA with react-router-dom               │
                          └──────────────┬───────────────────────────┘
                                          │ HTTP (REST + SSE streaming)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Backend (Render / Docker)                        │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │   Auth       │  │   Rate       │  │   Router     │  │  Provider  │  │
│  │   (JWT +     │─▶│   Limiter    │─▶│   (ML +      │─▶│  Dispatcher│  │
│  │   VirtualKey)│  │   (Sliding   │  │   Heuristic) │  │  (Registry │  │
│  │              │  │   Window)    │  │              │  │   Pattern) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────┬─────┘  │
│                                          │                      │       │
│                                          ▼                      ▼       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         Services Layer                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐    │   │
│  │  │   Telemetry  │  │ Error       │  │  Background Logging │    │   │
│  │  │   (PostHog)  │  │ Tracking    │  │  (RequestLog via    │    │   │
│  │  │              │  │ (Sentry)    │  │   BackgroundTasks)  │    │   │
│  │  └──────────────┘  └──────────────┘  └─────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ML Models (cold-loaded at startup, lazy fallback when absent)  │   │
│  │  router_classifier.pkl  │  router_regressor.pkl                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ SQLAlchemy (asyncpg)
                           ▼
              ┌─────────────────────────┐
              │     PostgreSQL 16       │
              │  users │ virtual_keys   │
              │  request_logs           │
              └─────────────────────────┘
```

### Layer Responsibilities

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| **API / Routes** | `backend/api/v1/` | HTTP endpoints, request parsing, response shaping |
| **Auth** | `backend/auth/` | JWT token creation/validation, Virtual Key auth, password hashing |
| **Core** | `backend/core/` | ML routing, feature extraction, rate limiting, provider abstraction |
| **DB** | `backend/db/` | SQLAlchemy models, async CRUD, connection pooling |
| **Services** | `backend/services/` | PostHog telemetry, Sentry error tracking |
| **Providers** | `backend/core/providers/` | Adapter implementations for OpenAI, Anthropic, Gemini |
| **Frontend** | `frontend/src/` | React SPA with pages, components, API client |

---

## 2. The Request Journey

### 2.1 API Call Flow

Here is the complete path of a chat completion request:

```
Client (Bearer clr-xxx)            Backend
       │                              │
       │ POST /v1/chat/completions    │
       │ Authorization: Bearer clr-xxx│
       │ { messages: [...], stream }  │
       │                              │
       ▼                              │
  ┌──────────────────┐               │
  │ get_virtual_key  │               │
  │ (auth/deps: line │               │
  │  43-68)          │               │
  │                  │               │
  │ hash key →       │               │
  │ lookup by hash   │               │
  │ in DB → check    │               │
  │ is_active        │               │
  └──────┬───────────┘               │
         │ VirtualKey                │
         ▼                           │
  ┌──────────────────┐               │
  │ rate_limit_chat  │               │
  │ (core/deps:      │               │
  │  line 17-28)     │               │
  │                  │               │
  │ SlidingWindow    │               │
  │ RateLimiter      │               │
  │ check user quota │               │
  └──────┬───────────┘               │
         │ allowed                   │
         ▼                           │
  ┌──────────────────────────┐       │
  │ Extract prompt from      │       │
  │ messages (last user msg) │       │
  └──────────┬───────────────┘       │
             │ prompt text           │
             ▼                       │
  ┌──────────────────────────┐       │
  │ route_prompt(prompt)     │       │
  │ (core/router.py:81)      │       │
  │                          │       │
  │ Feature Extraction ──►   │       │
  │ 22 numeric features +    │       │
  │ complexity_score         │       │
  │                          │       │
  │ ML Classifier? ──► Yes  │       │
  │   predict_proba → tier  │       │
  │   confidence check      │       │
  │   upgrade if low conf   │       │
  │                          │       │
  │ No classifier? ──►      │       │
  │   Heuristic fallback    │       │
  │   via complexity_score  │       │
  └──────────┬───────────────┘       │
             │ routing decision      │
             ▼                       │
  ┌──────────────────────────┐       │
  │ dispatch tier → provider │       │
  │ (core/dispatcher.py)     │       │
  │                          │       │
  │ Read tier model/api_key  │       │
  │ from VirtualKey attrs    │       │
  │                          │       │
  │ decrypt api_key (Fernet) │       │
  │                          │       │
  │ get_provider(type)       │       │
  │ from Registry → instance │       │
  │                          │       │
  │ Call provider.chat() or  │       │
  │ provider.chat_stream()   │       │
  └──────────┬───────────────┘       │
             │ response/chunks       │
             ▼                       │
  ┌──────────────────────────┐       │
  │ Fallback? (chat.py:60-   │       │
  │ 96, 125-151)             │       │
  │                          │       │
  │ Failed? Try next tier    │       │
  │ down: tier 2→[2,1,0]    │       │
  │ tier 1→[1,0]             │       │
  │ tier 0→[0]               │       │
  │                          │       │
  │ Inject x-llmrouter meta │       │
  │ in first chunk/response │       │
  └──────────┬───────────────┘       │
             │                       │
             ▼                       │
  ┌──────────────────────────┐       │
  │ Background log request   │       │
  │ (FastAPI BackgroundTasks)│       │
  │ ─► RequestLog in DB      │       │
  │ ─► PostHog telemetry     │       │
  │ ─► Sentry on error       │       │
  └──────────────────────────┘       │
             │                       │
             ▼                       │
        Response sent to client
```

### 2.2 Endpoint Details

**`POST /v1/chat/completions`** (`backend/api/v1/chat.py`)

- Accepts OpenAI-compatible request body: `{ messages, stream, ... }`
- Supports both streaming (`text/event-stream` via SSE) and synchronous responses
- Authentication via `get_virtual_key` (Bearier `clr-xxx` format)
- Rate limited via `rate_limit_chat` (60 req/min per user)

The endpoint has two parallel paths:

1. **Streaming** (lines 41-115): Returns a `StreamingResponse` with an async generator that yields SSE `data:` lines. The first chunk includes `x-llmrouter` metadata with the routing decision. Finalizes with a `[DONE]` signal. Background logging happens in a `finally` block.

2. **Synchronous** (lines 117-157): Awaits the dispatch response directly. Returns standard JSON with `x-llmrouter` injected into the response object.

### 2.3 Fallback Mechanism

Both paths implement cascading fallback. When a tier fails (exception during dispatch), the system tries the next lower tier:

```python
original_tier = routing["tier"]
attempts = list(range(original_tier, -1, -1))
for attempt in attempts:
    try:
        stream_obj, model_used = await dispatch_stream(messages, virtual_key, attempt)
        # success — break out
    except Exception:
        if attempt > 0:
            continue   # try next tier down
        raise          # all tiers failed
```

Fallback metadata is injected into the response: `rerouted=True`, `fallback_reason`, and the original tier info.

---

## 3. ML Pipeline

### 3.1 Feature Extraction

**File**: `backend/core/feature_extractor.py`

The `extract_features(text: str) -> dict` function computes 23 features from the prompt text:

#### Length and Readability (8 features)
| Feature | Description | Source |
|---------|-------------|--------|
| `char_count` | Total characters | `len(text)` |
| `word_count` | Word count | `textstat.lexicon_count` |
| `sentence_count` | Sentence count | `textstat.sentence_count` |
| `avg_word_length` | Chars / words | Derived |
| `unique_word_ratio` | Unique words / total | Derived via regex |
| `avg_sentence_len` | Words / sentences | Derived |
| `fk_grade` | Flesch-Kincaid grade level | `textstat.flesch_kincaid_grade` |
| `caps_ratio` | Uppercase chars / total | Regex |

#### Pattern Detection (8 boolean features)
Each is a regex match against the lowercased text:

| Feature | Matches |
|---------|---------|
| `is_coding` | code, implement, function, class, algorithm, api, def, return |
| `is_debugging` | debug, error, traceback, exception, fix, bug, crash, segfault |
| `is_reasoning` | explain, why, how does, analyze, compare, evaluate |
| `is_creative` | poem, story, creative, imagine, fiction, narrative |
| `is_multistep` | design, architecture, plan, scalable, system, steps to, roadmap |
| `is_math` | solve, calculate, equation, integral, derivative, probability |
| `is_summarize` | summarize, summary, tldr, brief, overview, condense |
| `is_simple_qa` | what is, who is, when did, where is, capital of, define |

#### Structural (5 boolean + 2 numeric features)
| Feature | Description |
|---------|-------------|
| `has_code_block` | Does text contain triple backticks |
| `has_numbers` | Regex match for any digit |
| `question_count` | Count of `?` characters |
| `comma_count` | Count of `,` characters |
| `has_bullet` | Lines starting with `-` or `*` |
| `has_constraints` | Keywords: must, require, limit, only, exactly |

#### Complexity Score (heuristic composite)
```python
complexity_score = 0.0
complexity_score += is_coding * 2.0
complexity_score += is_debugging * 2.0
complexity_score += is_multistep * 2.5
complexity_score += is_reasoning * 2.0
complexity_score += is_math * 1.5
complexity_score += has_code_block * 1.5
complexity_score += has_constraints * 1.0
if fk_grade > 12:
    complexity_score += 1.0
```

#### Feature Vector

`get_feature_vector(text: str) -> list[float]` extracts a 23-element list ordered by `FEATURE_ORDER` (same 22 features + `complexity_score` at the end). This is the input to both `CLASSIFIER.predict_proba` and `REGRESSOR.predict`.

### 3.2 Routing Decision

**File**: `backend/core/router.py`

The `route_prompt(prompt: str) -> dict` function implements a two-tier routing strategy:

```
                        ┌──────────────────┐
                        │  route_prompt()   │
                        └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
             CLASSIFIER is None        CLASSIFIER loaded
                    │                         │
                    ▼                         ▼
          ┌─────────────────┐      ┌─────────────────────┐
          │ _heuristic_route│      │ get_feature_vector() │
          │ (complexity     │      │         │            │
          │  score based)   │      │         ▼            │
          │                 │      │ predict_proba([vec]) │
          │ score<2 → weak  │      │         │            │
          │ score<4 → mid   │      │         ▼            │
          │ else → strong   │      │   argmax → tier     │
          │                 │      │         │            │
          │ confidence=0.5  │      │         ▼            │
          │                 │      │ confidence < 0.60   │
          └────────┬────────┘      │   AND tier < 2?     │
                   │               │         │            │
                   │               │    YES──┴──NO       │
                   │               │      │               │
                   │               │   upgrade tier      │
                   │               │   (tier += 1)       │
                   │               │      │               │
                   ▼               ▼      ▼               ▼
          ┌──────────────────────────────────────────────┐
          │  Return RoutingResult:                       │
          │  { tier, tier_name, confidence,              │
          │    difficulty_score, upgraded, rerouted }    │
          └──────────────────────────────────────────────┘
```

#### ML Path

1. Extract feature vector (23 floats)
2. `CLASSIFIER.predict_proba([features])[0]` returns probability distribution over 3 classes
3. `argmax` selects the tier
4. If `confidence < 0.60` (defined as `CONFIDENCE_THRESHOLD`) and tier is not already strong, **upgrade** one level. This biases toward more capable models when uncertain.
5. Optionally run `REGRESSOR.predict([features])` for a continuous difficulty score

#### Heuristic Fallback

When no classifier is loaded (models missing, corrupt, or running without ML):

1. Compute `complexity_score` from `extract_features`
2. Score < 2.0 -> weak (tier 0)
3. Score < 4.0 -> mid (tier 1)
4. Score >= 4.0 -> strong (tier 2)
5. Difficulty score derived from regressor if available, or `min(complexity / 10, 1.0)`
6. Fixed confidence of 0.5 (no uncertainty model)

### 3.3 Model Loading

**File**: `backend/core/router.py` (lines 14-42)

```python
def load_models():
    # Load XGBoost classifier from core/models/router_classifier.pkl
    # Load XGBoost regressor from core/models/router_regressor.pkl
    # Both are optional — gracefully handled when missing
```

Called during FastAPI lifespan startup (`backend/main.py`, line 41). Both models use `pickle.load()` and are stored as module-level globals (`CLASSIFIER`, `REGRESSOR`). Errors are logged but do not crash the application.

### 3.4 Routing Result

```python
{
    "tier":             0 | 1 | 2,
    "tier_name":        "weak" | "mid" | "strong",
    "confidence":       float (0-1),
    "difficulty_score": float (0-1),
    "upgraded":         bool,
    "rerouted":         bool,    # set by dispatch fallback, not router
}
```

---

## 4. Provider System

### 4.1 Architecture

The provider system uses a **Registry pattern** with an abstract base class. All providers normalize their output to OpenAI-compatible shapes.

```
         ┌─────────────────────────────────────┐
         │          BaseProvider (ABC)          │
         │  core/providers/base.py              │
         │                                     │
         │  + chat(messages, model, api_key,   │
         │      **kwargs) -> dict              │
         │  + chat_stream(messages, model,     │
         │      api_key, **kwargs) ->          │
         │      AsyncGenerator[dict, None]     │
         └──────────────────┬──────────────────┘
                            │ implements
         ┌──────────────────┼──────────────────┐
         │                  │                  │
┌────────▼────────┐ ┌──────▼──────┐ ┌─────────▼────────┐
│  OpenAIProvider │ │Anthropic    │ │  GeminiProvider  │
│                 │ │Provider     │ │                  │
│ AsyncOpenAI SDK │ │AsyncAnthropic│ │ google-genai SDK│
│ OpenAI-compat   │ │SDK          │ │                  │
│ (NIM, Together, │ │messages API │ │generate_content  │
│  Groq, etc.)    │ │system prop  │ │streaming support │
└────────┬────────┘ └──────┬──────┘ └─────────┬────────┘
         │                 │                  │
         └─────────────────┼──────────────────┘
                           │
                     ┌─────▼──────┐
                     │ Normalized │
                     │  Output    │
                     │            │
                     │ content    │
                     │ model      │
                     │ provider   │
                     │ usage {    │
                     │   prompt   │
                     │   complet  │
                     │   total    │
                     │ }          │
                     └────────────┘
```

### 4.2 BaseProvider

**File**: `backend/core/providers/base.py`

```python
class BaseProvider(ABC):
    async def chat(self, messages: list, model: str, api_key: str, **kwargs) -> dict:
        # Returns: { "content": str, "model": str, "provider": str, "usage": {...} }

    async def chat_stream(self, messages: list, model: str, api_key: str, **kwargs) -> AsyncGenerator[dict, None]:
        # Yields OpenAI-shaped chunks, final chunk includes usage
```

The interface is deliberately minimal. Each provider handles its own SDK initialization, message format conversion, and error normalization.

### 4.3 Registry

**File**: `backend/core/providers/registry.py`

```python
PROVIDER_MAP: dict[str, type[BaseProvider]] = {}

def register_provider(name: str, cls: type[BaseProvider]) -> None:
    PROVIDER_MAP[name] = cls

def get_provider(provider_type: str) -> BaseProvider:
    return PROVIDER_MAP[provider_type]()
```

Providers self-register at import time via a module-level call. Imports are triggered in `backend/main.py`:

```python
import core.providers.openai     # calls register_provider("openai", OpenAIProvider)
import core.providers.anthropic  # calls register_provider("anthropic", AnthropicProvider)
import core.providers.gemini     # calls register_provider("gemini", GeminiProvider)
```

### 4.4 Implemented Providers

| Provider | File | SDK | Notes |
|----------|------|-----|-------|
| **OpenAI** | `core/providers/openai.py` | `openai.AsyncOpenAI` | Compatible with any OpenAI-compatible endpoint (NVIDIA NIM, Together, Groq). Error normalization via `_normalize_error()`. |
| **Anthropic** | `core/providers/anthropic.py` | `anthropic.AsyncAnthropic` | Extracts system prompt from messages array (Anthropic requires it as a top-level field). Converts message format. Error wrapping via `httpx.HTTPStatusError`. |
| **Gemini** | `core/providers/gemini.py` | `google.genai.Client` | Uses `genai.Client.aio.models.generate_content`. Has message format conversion helper `_convert_messages()`. |

### 4.5 Dispatching

**File**: `backend/core/dispatcher.py`

```python
async def dispatch_stream(messages, virtual_key, tier: int):
    t = TIER_MAP[tier]  # {0: "weak", 1: "mid", 2: "strong"}
    model = getattr(virtual_key, f"{t}_model")
    api_key = decrypt(getattr(virtual_key, f"{t}_api_key"))
    provider_type = getattr(virtual_key, f"{t}_provider_type", "openai")
    base_url = getattr(virtual_key, f"{t}_base_url")

    provider = get_provider(provider_type)
    return provider.chat_stream(messages=messages, model=model, api_key=api_key, ...)
```

The dispatcher reads the VirtualKey model's tier-specific attributes using dynamic attribute access. Each tier can have a different provider type, allowing mixed-provider Virtual Keys. API keys are decrypted with Fernet symmetric encryption.

---

## 5. Data Model

### 5.1 Entity Relationship Diagram

```
┌──────────────────────┐       ┌──────────────────────────────┐
│        User          │       │        VirtualKey             │
├──────────────────────┤       ├──────────────────────────────┤
│ id (UUID, PK)        │──┐   │ id (UUID, PK)                │
│ email (unique, index)│  └───│ user_id (FK → users.id)       │
│ username             │      │ name                          │
│ password_hash        │      │ key_hash (unique, index)      │
│ is_admin             │      │                               │
│ created_at           │      │ weak_model                    │
└──────────────────────┘      │ weak_api_key (encrypted)      │
                              │ weak_base_url                 │
                              │ weak_provider_type            │
                              │                               │
                              │ mid_model                     │
                              │ mid_api_key (encrypted)       │
                              │ mid_base_url                  │
                              │ mid_provider_type             │
                              │                               │
                              │ strong_model                  │
                              │ strong_api_key (encrypted)    │
                              │ strong_base_url               │
                              │ strong_provider_type          │
                              │                               │
                              │ is_active                     │
                              │ created_at                    │
                              │ last_used_at                  │
                              └────────┬─────────────────────┘
                                       │ 1
                                       │ *
                              ┌────────▼─────────────────────┐
                              │        RequestLog             │
                              ├──────────────────────────────┤
                              │ id (UUID, PK)                │
                              │ virtual_key_id (FK)          │
                              │ user_id (FK → users.id)      │
                              │                               │
                              │ prompt_preview (200 chars)   │
                              │ prompt_length                 │
                              │ tier_assigned                 │
                              │ confidence                    │
                              │ model_used                    │
                              │                               │
                              │ input_tokens                  │
                              │ output_tokens                 │
                              │ latency_ms                    │
                              │ cost_estimate_usd             │
                              │                               │
                              │ status (success/error)        │
                              │ error_message                 │
                              │ created_at                    │
                              └──────────────────────────────┘
```

### 5.2 Models

**File**: `backend/db/models.py`

#### User

```python
class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())
```

Users own VirtualKeys and have an `is_admin` flag for admin-only endpoints. Passwords are hashed with bcrypt (via `auth/password.py`).

#### VirtualKey

```python
class VirtualKey(Base):
    __tablename__ = "virtual_keys"
    # Identity
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    key_hash = Column(String, unique=True, nullable=False, index=True)

    # Three tiers — each has model, api_key, base_url, provider_type
    weak_model / weak_api_key / weak_base_url / weak_provider_type
    mid_model  / mid_api_key  / mid_base_url  / mid_provider_type
    strong_model / strong_api_key / strong_base_url / strong_provider_type

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_used_at = Column(DateTime, nullable=True)
```

Each Virtual Key encodes a complete routing configuration: three tiers with independent model names, provider types, and encrypted API keys. The raw key (`clr-xxx`) is shown once at creation; only the SHA-256 hash is stored.

#### RequestLog

```python
class RequestLog(Base):
    __tablename__ = "request_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    virtual_key_id = Column(UUID, ForeignKey("virtual_keys.id"))
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"))

    prompt_preview = Column(String(length=200))
    prompt_length = Column(Integer, nullable=False)
    tier_assigned = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    model_used = Column(String, nullable=False)

    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=False)
    cost_estimate_usd = Column(Float, nullable=True)

    status = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
```

Every request is logged for analytics and cost tracking. The `cost_estimate_usd` field is computed from token counts and tier-based pricing rates.

### 5.3 CRUD Operations

**File**: `backend/db/crud.py`

Key operations:

| Function | Purpose |
|----------|---------|
| `create_user` / `get_user_by_email` / `get_user_by_id` | User lifecycle |
| `create_virtual_key` | Generates `clr-xxx` key, returns raw key + hashed record |
| `get_key_by_hash` | Key lookup for auth |
| `list_keys` / `revoke_key` / `delete_key` | Key management |
| `touch_key` | Updates `last_used_at` |
| `log_request` | Persists request log entry |
| `get_stats` | Aggregated analytics (requests, cost, latency, success rate) |
| `get_request_logs` | Paginated log retrieval |

### 5.4 Encryption

API keys at rest are encrypted using `cryptography.fernet.Fernet`:

```python
# backend/db/crud.py
def encrypt(val: str) -> str:
    return get_fernet().encrypt(val.encode()).decode()

def decrypt(val: str) -> str:
    return get_fernet().decrypt(val.encode()).decode()
```

The `ENCRYPTION_KEY` environment variable is required. Keys are decrypted on-the-fly during dispatch, never stored in plaintext in the database.

---

## 6. API Layer

### 6.1 Endpoint Organization

```
Prefix          Router File              Tags
────────────────────────────────────────────────
/auth/*         api/v1/auth.py           Auth
/keys/*         api/v1/keys.py           Keys
/v1/*           api/v1/keys_gemini.py    (Gemini model list)
/v1/*           api/v1/keys_anthropic.py (Anthropic model list)
/v1/*           api/v1/chat.py           Chat
/analytics/*    api/v1/analytics.py      Analytics
/users/*        api/v1/users.py          Users
/evaluate       api/v1/evaluate.py       Internal
/health         (in main.py)             (system health)
```

**File**: `backend/main.py` (lines 63-70)

### 6.2 Middleware Chain

Every request passes through this pipeline:

```
Request
  │
  ▼
┌─────────────────────────────────┐
│  CORS Middleware                │
│  (allow Vercel frontend origin) │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  Auth Dependency                │
│                                 │
│  /v1/chat/completions:           │
│    get_virtual_key              │
│    (Bearer clr-xxx → hash →     │
│     DB lookup)                  │
│                                 │
│  /keys/* /analytics/* /auth/me: │
│    get_current_user             │
│    (Bearer jwt → decode →       │
│     user lookup)                │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  Rate Limit Dependency          │
│                                 │
│  chat: 60 req/min per user      │
│  auth: 20 req/min per IP        │
│  api:  200 req/min per user     │
│  admin: 100 req/min per user    │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  Handler Logic                  │
│  (feature extraction →          │
│   routing → dispatch →          │
│   background logging)           │
└─────────────────────────────────┘
```

### 6.3 Rate Limiter

**File**: `backend/core/rate_limiter.py`

```python
class SlidingWindowRateLimiter:
    # _buckets: dict[key_string, list[float]]  — timestamps per key
    # Thread-safe via asyncio.Lock
```

The rate limiter uses a sliding window algorithm. Each key (user_id or IP) maintains a sorted list of request timestamps. On each check:

1. Clean expired timestamps (older than window)
2. If count >= max_requests, return 429 with `Retry-After` header
3. Otherwise append current timestamp, return remaining count

Four rate limit buckets are defined in `backend/core/dependencies.py`:

| Bucket | Window | Max | Key |
|--------|--------|-----|-----|
| `chat` | 60s | 60 | `chat:{user_id}` |
| `auth` | 60s | 20 | `auth:{ip}` |
| `api` | 60s | 200 | `api:{user_id}` |
| `admin` | 60s | 100 | `admin:{user_id}` |

Rate limit dependencies are injected via `Depends()` in route handlers.

### 6.4 Authentication

Two independent auth mechanisms:

#### JWT Auth (for frontend users)

**Files**: `backend/auth/jwt_handler.py`, `backend/auth/dependencies.py`

- Token creation: `create_token(user_id) -> JWT` with HS256, 30-day expiry
- Token validation: `decode_token(token) -> payload` (raises 401 on failure)
- FastAPI dependency: `get_current_user` extracts Bearer token, decodes JWT, fetches User from DB
- Used by: `/keys/*`, `/analytics/*`, `/auth/me`, `/users/*` routes

#### Virtual Key Auth (for API consumers)

**File**: `backend/auth/dependencies.py` (lines 43-68)

```python
async def get_virtual_key(authorization: str = Header(...)):
    # Expects "Bearer clr-xxx"
    # SHA-256 hash the token
    # Look up VirtualKey by hash in DB
    # Check is_active
```

The `clr-` prefix distinguishes Virtual Keys from JWT tokens. This auth method is used exclusively by `/v1/chat/completions`.

---

## 7. Frontend Architecture

### 7.1 Stack

| Technology | Role |
|------------|------|
| React 19 (JSX) | UI framework |
| Vite | Build tool + dev server |
| Tailwind CSS v4 | Styling |
| shadcn/ui + Radix UI | Component primitives |
| react-router-dom v7 | Client-side routing |
| Lucide React | Icons |
| Recharts | Analytics charts |
| Vitest + jsdom | Testing |
| TypeScript | Type safety |

### 7.2 Directory Structure

```
frontend/src/
├── api/           # API client modules (one per domain)
│   ├── client.ts      # Base fetch wrapper, error handling, auth token
│   ├── auth.ts        # Login, register, getMe
│   ├── keys.ts        # CRUD for Virtual Keys
│   ├── chat.ts        # Chat completions (SSE streaming)
│   ├── analytics.ts   # Summary, logs, daily stats
│   └── users.ts       # User management (admin)
├── components/
│   ├── ui/            # shadcn/ui primitives (Button, Input, etc.)
│   └── Layout.tsx     # App shell with sidebar nav
├── context/
│   └── AuthContext.tsx # Auth state, JWT persistence, login/logout
├── pages/
│   ├── Login.tsx      # Email/password login
│   ├── Register.tsx   # User registration
│   ├── Dashboard.tsx  # Overview with stats summary
│   ├── Chat.tsx       # Playground with streaming chat UI
│   ├── Keys.tsx       # Virtual Key management
│   ├── Analytics.tsx  # Usage analytics with charts
│   └── Profile.tsx    # User profile editing
├── lib/
│   └── utils.ts       # cn() classname utility
├── mocks/             # Test mocks
├── test/              # Test configuration
├── App.tsx            # Route definitions, lazy loading
├── main.tsx           # React entry point
└── index.css          # Tailwind imports, global styles
```

### 7.3 Component Tree

```
<App>
  <Suspense>                          # Lazy loading fallback
    <Routes>
      ├── /login → <Login />
      ├── /register → <Register />
      └── <Layout />                  # Authenticated shell
            ├── <Sidebar>            # Navigation with icons
            │   ├── Dashboard
            │   ├── Playground
            │   ├── Keys
            │   └── Analytics
            ├── <UserMenu>           # Profile + Logout dropdown
            └── <Outlet />           # Page content
                  ├── / → <Dashboard />
                  ├── /chat → <Chat />
                  ├── /keys → <Keys />
                  ├── /analytics → <Analytics />
                  └── /profile → <Profile />
    </Routes>
  </Suspense>
</App>
```

### 7.4 API Client Layer

**File**: `frontend/src/api/client.ts`

The API client is a thin fetch wrapper:

```typescript
export async function apiRequest<T>(path, options, requiresAuth = true): Promise<T>
```

- Reads JWT from `localStorage` (`auth` key)
- Attaches `Authorization: Bearer <token>` header when `requiresAuth` is true
- Parses errors into `ApiError` with status code and detail message
- Handles 204 No Content for delete operations
- In development, uses Vite proxy (no `VITE_API_URL`)
- In production, uses `VITE_API_URL` (Render backend URL)

#### SSE Streaming

**File**: `frontend/src/api/chat.ts`

```typescript
export async function* streamChatMessage(virtualKey, messages):
  AsyncGenerator<ChatChunk | FallbackNotice | StreamError>
```

The streaming endpoint returns an async generator that reads SSE `data:` lines from a `ReadableStream`. It yields typed objects:

- `ChatChunk`: A standard OpenAI-shaped delta with optional `x-llmrouter` metadata
- `FallbackNotice`: Emitted when the router downgrades tiers mid-stream
- `StreamError`: Error messages from the backend

### 7.5 Auth Context

**File**: `frontend/src/context/AuthContext.tsx`

```typescript
interface AuthContextType {
  token: string | null
  user: { id: string; email: string; username } | null
  loading: boolean
  login: (email, password) => Promise<void>
  register: (email, username, password) => Promise<void>
  logout: () => void
}
```

- Persists auth state in `localStorage`
- On mount: tries `getMe()` with stored token to validate session
- On 401: clears stored token and redirects to login
- Wraps the entire app via `<AuthProvider>`

### 7.6 Vite Dev Proxy

**File**: `frontend/vite.config.ts`

```typescript
server: {
  proxy: {
    '/v1': 'http://localhost:8000',
    '/auth': { target: 'http://localhost:8000', bypass: html guard },
    '/keys': { target: 'http://localhost:8000', bypass: html guard },
    '/analytics': { target: 'http://localhost:8000', bypass: html guard },
    '/users': 'http://localhost:8000',
    '/health': 'http://localhost:8000',
  }
}
```

In development, the Vite dev server proxies all API calls to the local FastAPI backend. The `bypass` logic for auth/keys/analytics prevents Vite from proxying HTML navigation requests (so react-router handles them).

---

## 8. Deployment Architecture

### 8.1 Infrastructure

```
                         Internet
                            │
              ┌─────────────┴──────────────┐
              │                            │
              ▼                            ▼
      ┌──────────────┐           ┌─────────────────────┐
      │   Vercel     │           │   Render (Web)      │
      │  (Frontend)  │           │  (Backend + ML)     │
      │              │           │                     │
      │  Vite-built  │  HTTP     │  FastAPI (uvicorn)  │
      │  static SPA  │◄─────────►│  on port 8000       │
      │              │           │                     │
      └──────────────┘           └──────────┬──────────┘
                                            │ asyncpg
                                            ▼
                                    ┌──────────────────┐
                                    │  Render Postgres │
                                    │  (or Docker)     │
                                    │  PostgreSQL 16   │
                                    └──────────────────┘
```

### 8.2 Docker Setup

**File**: `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes: pgdata:/var/lib/postgresql/data
    healthcheck: pg_isready
    ports: ["5432:5432"]

  app:
    build: ./backend
    depends_on: db (condition: service_healthy)
    ports: ["8000:8000"]
    volumes: modeldata:/app/models
    environment:
      DATABASE_URL, JWT_SECRET, ENCRYPTION_KEY, POSTHOG_*, SENTRY_DSN, APP_ENV
```

### 8.3 Backend Dockerfile

**File**: `backend/Dockerfile`

Multi-stage build with UV for dependency management:

1. **Builder stage** (`python:3.13-slim`): Installs build deps (gcc, g++), copies `uv`, runs `uv sync --frozen --no-dev`
2. **Runtime stage**: Copies `.venv` from builder, source code, sets up `HEALTHCHECK` on `/health`, runs `docker-entrypoint.sh` then `uvicorn main:app`

Key environment variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | HS256 signing key for JWT |
| `ENCRYPTION_KEY` | Yes | Fernet key for API key encryption |
| `POSTHOG_API_KEY` | No | Product analytics |
| `SENTRY_DSN` | No | Error tracking |
| `APP_ENV` | No | Environment label (development/production) |
| `DB_POOL_SIZE` | No | SQLAlchemy pool size (default: 10) |
| `DB_POOL_PRE_PING` | No | Connection validation (default: true) |

### 8.4 Frontend Deploy

**File**: `frontend/vercel.json`

Deployed on Vercel as a static SPA. The `VITE_API_URL` env var points to the Render backend URL. In development, Vite's proxy eliminates the need for CORS complexity.

### 8.5 Startup Sequence

```
1. Docker starts PostgreSQL (healthcheck: pg_isready)
2. Docker starts app service (depends on db healthy)
3. docker-entrypoint.sh runs:
   a. Alembic migrations: alembic upgrade head
   b. uvicorn starts main:app
4. FastAPI lifespan startup:
   a. Run Alembic upgrade (in executor, no asyncio)
   b. load_models() — loads XGBoost .pkl files
   c. init_sentry() — initialize Sentry SDK
5. Server ready on port 8000
6. Health endpoint: /health returns { status, db_connected, model_loaded }
```

### 8.6 Health Check

**File**: `backend/main.py` (lines 73-80)

```python
@app.get("/health")
async def health():
    return {
        "status": "ok" if db_ok else "degraded",
        "db_connected": db_ok,
        "model_loaded": CLASSIFIER is not None,
    }
```

Used by Docker's `HEALTHCHECK` and by Render for service monitoring. Reports database connectivity and ML model status.

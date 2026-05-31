# Quickstart — ClassiRoute

Get a working ClassiRoute gateway in under 10 minutes. By the end you will have the backend running, a Virtual Key created, and your first API call routed through the ML classifier.

---

## 0. Prerequisites

| Tool | Minimum version | Check |
|---|---|---|
| **Docker** | 24+ with Compose v2 | `docker --version && docker compose version` |
| **Node.js** | 18+ | `node --version` |
| **Python** 3.12+ (optional: for generating secrets locally) | | `python3 --version` |

You also need API keys for at least one LLM provider. The common ones are OpenAI, Anthropic, or Gemini. Have at least one pair of model name + API key ready before you start.

---

## 1. Clone and enter the project

```bash
git clone <repo-url> classiroute
cd classiroute
```

The project layout:

```
classiroute/
  backend/          # FastAPI app + ML models
  frontend/         # React 19 + Vite dashboard
  docker-compose.yml
  .env.example
  docs/
```

---

## 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` in your editor. The file you just created should look like this:

```ini
DATABASE_URL=postgresql://[username]:[password]@localhost:5432/[database_name]
DB_SCHEMA=public
JWT_SECRET=change-me-to-a-random-64-char-string
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=30
ENCRYPTION_KEY=
POSTHOG_API_KEY=
POSTHOG_HOST=https://app.posthog.com
SENTRY_DSN=
APP_ENV=development
```

### Set the required values

Two fields are mandatory: `JWT_SECRET` and `ENCRYPTION_KEY`. Generate them now.

```bash
# JWT_SECRET — 64 hex chars
python3 -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY — Fernet key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy each output into the corresponding field in `.env`.

**Note on DATABASE_URL:** In Docker Compose the connection string is handled automatically by the `docker-compose.yml` file. You only need to set `POSTGRES_PASSWORD` if you want a non-default password. The default is `classiroute`.

### Your `.env` should look roughly like this

```ini
JWT_SECRET=6a2f8c1e9b3d5f7a0c4e8b2d6f9a1c3e5b7d0f2a4c6e8b0d2f4a6c8e0b2d4f6
ENCRYPTION_KEY=NEfC5jPmZQq3xL8vW2rY6tA0bD9gH1sK4oU7iR3nM5=
APP_ENV=development
```

Everything else can stay at its default for local development.

---

## 3. Start the backend with Docker Compose

```bash
docker compose up
```

This starts two containers:

| Container | Role |
|---|---|
| `classiroute-db` | PostgreSQL 16 Alpine |
| `classiroute-app` | FastAPI + ML models (waits for DB to be healthy) |

Watch the logs. On first startup you will see something like:

```
classiroute-db-1   | PostgreSQL init process complete; ready for accept connections.
classiroute-app-1  | Waiting for database...
classiroute-app-1  | Database ready.
classiroute-app-1  | [alembic] Running upgrade -> abc123, initial migration
classiroute-app-1  | INFO:     Classifier loaded from core/models/router_classifier.pkl
classiroute-app-1  | INFO:     Regressor loaded from core/models/router_regressor.pkl
classiroute-app-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

The important milestones:

1. **DB ready** — the entrypoint script waited for PostgreSQL
2. **Alembic migration** — database tables were created automatically
3. **Models loaded** — the XGBoost classifier and regressor are active
4. **Uvicorn running** — the API is ready on port 8000

Verify with:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"healthy","database":"connected"}
```

If you see `database: "disconnected"`, wait a few seconds and try again. PostgreSQL can take a moment on first startup.

---

## 4. Register a user

You can register either through the API or (once the frontend is running) through the web UI.

### Via API (quickest)

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "username": "you",
    "password": "password123"
  }'
```

Expected response:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "you@example.com",
    "username": "you"
  }
}
```

Save the token. You will need it in the next step.

> Passwords must be at least 8 characters. The email must not already be registered. That is it — no email verification is needed in development mode.

---

## 5. Create a Virtual Key

A Virtual Key bundles three model tiers (weak, mid, strong) behind a single `clr-xxx` API key. When you send a request using this key, ClassiRoute picks the cheapest tier that can handle your prompt.

### Via API

Use the token from step 4 as your Bearer token:

```bash
curl -X POST http://localhost:8000/keys/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "name": "My First Key",
    "weak_model": "gpt-4o-mini",
    "weak_api_key": "sk-...",
    "weak_base_url": "https://api.openai.com/v1",
    "weak_provider_type": "openai",
    "mid_model": "gpt-4o",
    "mid_api_key": "sk-...",
    "mid_base_url": "https://api.openai.com/v1",
    "mid_provider_type": "openai",
    "strong_model": "gpt-4o",
    "strong_api_key": "sk-...",
    "strong_base_url": "https://api.openai.com/v1",
    "strong_provider_type": "openai"
  }'
```

Expected response:

```json
{
  "key": "clr-a1b2c3d4e5f6...<64 hex chars>",
  "key_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "My First Key"
}
```

The `key` value is your Virtual Key. It starts with `clr-` and is shown only once. **Save it** — you will use it to authenticate API calls.

> **Provider types:** You can mix providers across tiers. Use `"openai"` for any OpenAI-compatible endpoint (including NVIDIA, Together, Groq), `"anthropic"` for Anthropic, or `"gemini"` for Google Gemini. Each tier gets its own model, API key, and base URL.

> **Validation:** The API checks each provider before creating the key. If a model name is wrong or the API key is invalid, the endpoint returns an error with details.

### Via the frontend (alternative)

If you have the frontend running, log in at `http://localhost:5173/login`, go to the **Keys** page, and click **Create Key**. The form walks you through the same fields.

---

## 6. Make your first API call

ClassiRoute uses the OpenAI-compatible chat completions format. Send a request with your `clr-xxx` key:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer clr-a1b2c3d4e5f6...<your-full-virtual-key>" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```

Expected response:

```json
{
  "id": "chatcmpl-1717200000",
  "object": "chat.completion",
  "created": 1717200000,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 14,
    "completion_tokens": 7,
    "total_tokens": 21
  },
  "x-llmrouter": {
    "tier": 0,
    "tier_name": "weak",
    "confidence": 0.9876,
    "difficulty_score": 0.0234,
    "upgraded": false,
    "rerouted": false
  }
}
```

The routing information lives in the `x-llmrouter` field. Here is what it tells you:

| Field | Meaning |
|---|---|
| `tier` | Numeric tier: 0 (weak), 1 (mid), 2 (strong) |
| `tier_name` | Human-readable name |
| `confidence` | How sure the classifier is (0 to 1). Higher is better. |
| `difficulty_score` | Estimated difficulty of the prompt (0 to 1+) |
| `upgraded` | Was the prompt bumped up a tier due to low confidence |
| `rerouted` | Was the request automatically retried on a lower tier after failure |

### Try a harder prompt

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer clr-..." \
  -d '{
    "messages": [
      {"role": "user", "content": "Write a Python function that implements a Red-Black tree with insertion, deletion, and balancing operations. Include time complexity analysis."}
    ]
  }'
```

This time the `x-llmrouter` should show `"tier": 2, "tier_name": "strong"` because the prompt is much more complex.

---

## 7. Start the frontend (optional)

The backend works fine without the frontend (as shown above). But the dashboard is useful for analytics, key management, and a built-in chat UI.

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server starts on `http://localhost:5173`. It proxies API calls to the backend at `localhost:8000`, so you do not need to configure CORS or URLs.

**Login** with the email and password you registered in step 4. You should see the dashboard with key management, analytics, and a chat interface.

---

## 8. What is happening under the hood

Every request goes through this pipeline:

```
Your prompt
    │
    ▼
Feature Extractor  ──  23 measurements (length, readability,
    │                    keyword patterns, code detection...)
    ▼
ML Classifier      ──  XGBoost predicts difficulty tier
    │                    (if confidence < 60%, upgrade to next tier)
    ▼
Dispatched to      ──  Your chosen provider for that tier
    │                    (with automatic fallback if it fails)
    ▼
Response + routing metadata
```

The ML models are loaded from `backend/core/models/router_classifier.pkl` and `router_regressor.pkl` at startup. If the files are missing, the system falls back to a heuristic based on the complexity score.

---

## 9. Next steps

| Guide | What it covers |
|---|---|
| [Docker reference](docker.md) | Building images, running without Compose, deploying to a registry |
| [How routing works](how-routing-works.md) | Deep dive into the 23 features the classifier uses |
| [Implementation guide](implementation-guide.md) | Training your own models, custom providers, scaling |
| [Monitoring](monitoring.md) | PostHog analytics and Sentry error tracking setup |
| [Migrations](migrations.md) | Alembic workflow and schema changes |
| [Multi-provider adapters](multi-provider-adpaters.md) | Adding support for additional LLM providers |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `JWT_SECRET is required` | You did not set JWT_SECRET in `.env` |
| `ENCRYPTION_KEY is required` | You did not set ENCRYPTION_KEY in `.env` |
| `relation "users" does not exist` | Alembic migration did not run. Check `docker compose logs app` for migration errors |
| `Models not found` | `core/models/router_classifier.pkl` or `router_regressor.pkl` are missing. The system falls back to heuristic routing, which still works |
| `Invalid API key format` | Make sure your Authorization header starts with `Bearer clr-` (not `Bearer ` followed by a JWT) |
| Frontend shows blank page | Make sure the backend is running on port 8000. The Vite dev server proxies `/v1`, `/auth`, `/keys`, `/analytics` to it |

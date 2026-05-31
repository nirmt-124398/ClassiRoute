<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/ClassiRoute-Cost--Aware%20LLM%20Routing-6a9bcc?style=for-the-badge&logo=python&logoColor=white">
    <img alt="ClassiRoute" src="https://img.shields.io/badge/ClassiRoute-Cost--Aware%20LLM%20Routing-d97757?style=for-the-badge&logo=python&logoColor=white">
  </picture>
</p>

<p align="center">
  <strong>Route every prompt to the cheapest adequate model. Automatically.</strong>
</p>

<p align="center">
  <a href="#features"><img src="https://img.shields.io/badge/Features-6a9bcc?style=flat-square" alt="Features"></a>
  <a href="#how-it-works"><img src="https://img.shields.io/badge/Architecture-d97757?style=flat-square" alt="Architecture"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/Quick_Start-788c5d?style=flat-square" alt="Quick Start"></a>
  <a href="#configuration"><img src="https://img.shields.io/badge/Configuration-6a9bcc?style=flat-square" alt="Configuration"></a>
  <a href="#api-reference"><img src="https://img.shields.io/badge/API-d97757?style=flat-square" alt="API"></a>
  <a href="#contributing"><img src="https://img.shields.io/badge/Contributing-788c5d?style=flat-square" alt="Contributing"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/license/your-org/classiroute?style=flat-square&color=788c5d" alt="License">
  <img src="https://img.shields.io/badge/Python-3.13-6a9bcc?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React-19-d97757?style=flat-square&logo=react&logoColor=white" alt="React">
  <img src="https://img.shields.io/badge/XGBoost-92.3%25_accuracy-788c5d?style=flat-square" alt="XGBoost">
  <img src="https://img.shields.io/badge/Cost_Reduction-57.9%25-6a9bcc?style=flat-square" alt="Cost Reduction">
  <img src="https://img.shields.io/badge/Quality_Parity-96.8%25-d97757?style=flat-square" alt="Quality Parity">
  <img src="https://img.shields.io/badge/PostgreSQL-16-788c5d?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Ready-6a9bcc?style=flat-square&logo=docker&logoColor=white" alt="Docker">
</p>

---

## The Problem

Every LLM API call has a cost. Not just in dollars -- latency, rate limits, complexity. Teams that build on top of multiple LLM providers face a question with every prompt: _Which model is good enough for this?_

Send everything to GPT-4o or Claude Opus and you burn through budget on trivial requests. Default to a cheap model and you get garbage on anything complex. The manual middle ground -- hardcoding rules, maintaining routing tables, guessing per-request -- doesn't scale.

ClassiRoute solves this by learning what your prompts actually need.

## What It Does

ClassiRoute is a **routing engine** that sits between your application and LLM providers (OpenAI, Anthropic, Gemini). It analyzes every incoming prompt across 22 feature dimensions, classifies its complexity using an XGBoost model (92.31% accuracy), and dispatches it to the cheapest adequate model tier you've configured.

The result: **57.9% cost reduction** with **96.8% quality parity** against always-using-the-best-model. On a real-world workload of 15,000 prompts, that's the difference between paying for every request at the premium tier and paying the premium tier only when it actually matters.

## Features

- **ML-powered routing** -- XGBoost classifier (3-tier) with confidence scoring via a companion regression model. Low-confidence predictions auto-escalate to the next tier.
- **Heuristic fallback** -- When no ML model is loaded, a rule-based complexity scorer takes over. Score thresholds map cleanly to tiers.
- **Multi-provider dispatching** -- Plugin architecture via a Provider Registry. OpenAI-compatible, Anthropic, and Gemini are built in. Add your own in one file.
- **Cascading fallback chain** -- If a request fails on the predicted tier, ClassiRoute tries the next one down. A strong-tier failure drops to mid, then weak. No silent failures, no lost requests.
- **Virtual Keys** -- Each key bundles three model tiers (weak / mid / strong). Configure a different provider, model, API key, and base URL per tier. Keys authenticate incoming requests via the OpenAI-compatible endpoint.
- **Rate limiting** -- Sliding window per endpoint category (chat: 60/min, auth: 20/min, api: 200/min, admin: 100/min).
- **Streaming + sync** -- Full support for SSE streaming and synchronous completions, matching the OpenAI chat completions API shape.
- **Analytics** -- Track request volume, tier distribution, cost savings, latency, and success rates per key. Visualized on the frontend dashboard.
- **Telemetry** -- PostHog for product analytics, Sentry for error tracking. Both degrade gracefully when not configured.
- **Full management UI** -- React 19 dashboard with login, virtual key management (3-tier config per key), chat playground with routing info, analytics with Recharts, and user profile.

## How It Works

```
                           ┌──────────────────┐
                           │   Your App / UI   │
                           │ (OpenAI-compatible │
                           │   POST /v1/chat/   │
                           │   completions)     │
                           └────────┬─────────┘
                                    │
                                    ▼
                     ┌───────────────────────────┐
                     │      Rate Limiter          │
                     │  60/min per user (chat)    │
                     └───────────┬───────────────┘
                                │
                                ▼
                     ┌───────────────────────────┐
                     │     Virtual Key Auth       │
                     │    Bearer clr-xxx...       │
                     │   → resolves to 3 tiers    │
                     └───────────┬───────────────┘
                                │
                                ▼
                     ┌───────────────────────────┐
                     │    Feature Extractor       │
                     │  22 dimensions:            │
                     │  • Length & readability    │
                     │  • Pattern detection       │
                     │  • Heuristic complexity    │
                     └───────────┬───────────────┘
                                │
                                ▼
            ┌────────────────────────────────────┐
            │         Router (ML + Fallback)      │
            │                                      │
            │   ┌──────────┐     ┌──────────────┐  │
            │   │ XGBoost  │     │  XGBoost      │  │
            │   │Classifier│     │  Regressor    │  │
            │   │ 3-tier   │     │  Confidence   │  │
            │   │ predict  │     │  scoring      │  │
            │   └────┬─────┘     └──────┬───────┘  │
            │        │                  │          │
            │        ▼                  ▼          │
            │   ┌────────────────────────────┐    │
            │   │ Final Decision             │    │
            │   │ Tier 0 (weak)              │    │
            │   │ Tier 1 (mid)               │    │
            │   │ Tier 2 (strong)            │    │
            │   │ + auto-escalation on       │    │
            │   │   low confidence           │    │
            │   └───────────┬────────────────┘    │
            └───────────────┼────────────────────┘
                            │
                            ▼
            ┌────────────────────────────────────┐
            │         Dispatcher                  │
            │                                      │
            │   ┌──────────────────────────┐      │
            │   │  Provider Registry       │      │
            │   │  • OpenAI (and compat)   │      │
            │   │  • Anthropic             │      │
            │   │  • Gemini                │      │
            │   └──────────────────────────┘      │
            │                                      │
            │  Fallback: strong→mid→weak          │
            └───────────┬────────────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │  Model Response  │
              │  (stream / sync) │
              └──────────────────┘
```

### The 22 Feature Dimensions

The Feature Extractor measures every prompt across four categories:

**Length & Readability:** character count, word count, sentence count, average word length, unique word ratio, average sentence length, Flesch-Kincaid grade level.

**Pattern Detection:** code presence, debugging keywords, reasoning/analysis triggers, creative writing signals, multi-step/design intent, math formulas, summarization requests, simple Q&A, code blocks, numeric content, bullet lists, constraint language.

**Structural Signals:** question count, comma density, capitalization ratio.

**Heuristic Complexity:** weighted composite score that feeds the fallback router and augments the ML regressor.

### Routing Decision

The XGBoost classifier predicts one of three tiers:

| Tier | Name | When |
|------|------|------|
| 0 | Weak | Simple Q&A, definitions, summaries, basic lookups |
| 1 | Mid | Explanations, comparisons, creative writing, planning |
| 2 | Strong | Complex coding, debugging, math, system design, architecture |

A companion XGBoost regressor scores the predicted confidence. If confidence falls below 0.60 and the tier isn't already at maximum, the router escalates one level up. When no ML model is loaded, the heuristic complexity score maps directly: `<2.0 → weak`, `<4.0 → mid`, `else → strong`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.13, FastAPI, async SQLAlchemy + asyncpg, uvicorn |
| **ML** | XGBoost 3.2+, scikit-learn 1.6.1, pickle serialized models |
| **Frontend** | React 19, TypeScript 6, Vite 8, Tailwind CSS v4, Radix UI, Recharts |
| **Database** | PostgreSQL 16, Alembic migrations, async driver |
| **Providers** | OpenAI SDK, Anthropic SDK, Google GenAI SDK (plugin architecture) |
| **Auth** | JWT (python-jose), bcrypt (passlib), Fernet encryption for stored keys |
| **Infrastructure** | Docker (multi-stage with uv + slim), Docker Compose, Render (backend), Vercel (frontend), Neon (DB) |
| **Observability** | PostHog telemetry, Sentry error tracking (both optional) |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An API key from at least one LLM provider

### Run with Docker Compose

```bash
git clone https://github.com/your-org/classiroute.git
cd classiroute

# Set required secrets
echo "JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" >> .env
echo "ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env

# Start everything
docker compose up --build
```

The API starts on `http://localhost:8000`. Health check: `http://localhost:8000/health`.

### Run without Docker

**Backend:**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # fill in your values
alembic upgrade head
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server starts on `http://localhost:5173` and proxies API calls to the backend.

### Create Your First User

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","username":"demo","password":"securepass123"}'
```

### Create a Virtual Key

```bash
curl -X POST http://localhost:8000/keys \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-key",
    "weak_model": "gpt-4o-mini",
    "weak_api_key": "sk-...",
    "weak_base_url": "https://api.openai.com/v1",
    "mid_model": "gpt-4o",
    "mid_api_key": "sk-...",
    "mid_base_url": "https://api.openai.com/v1",
    "strong_model": "claude-3-5-sonnet-latest",
    "strong_api_key": "sk-ant-...",
    "strong_base_url": "https://api.anthropic.com",
    "strong_provider_type": "anthropic"
  }'
```

The response includes a virtual key starting with `clr-`. Use it to route prompts.

### Send a Chat Request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer clr-<your-virtual-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the capital of France?"}],
    "stream": false
  }'
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | -- | PostgreSQL connection string |
| `DB_SCHEMA` | No | `public` | Database schema |
| `JWT_SECRET` | Yes | -- | 64-char random string for token signing |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_DAYS` | No | `30` | Token expiration |
| `ENCRYPTION_KEY` | Yes | -- | Fernet key for API key encryption at rest |
| `POSTHOG_API_KEY` | No | -- | PostHog project key (telemetry) |
| `POSTHOG_HOST` | No | `https://app.posthog.com` | PostHog host |
| `SENTRY_DSN` | No | -- | Sentry DSN (error tracking) |
| `APP_ENV` | No | `development` | Environment label |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed origins |

Generate secrets:

```bash
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

## API Reference

### `POST /v1/chat/completions`

OpenAI-compatible chat endpoint. Authenticated via Bearer token with a virtual key.

**Request body:**

```json
{
  "messages": [
    {"role": "user", "content": "Explain quantum computing in one sentence."}
  ],
  "stream": false
}
```

**Streaming response** (when `stream: true`): Server-sent events matching the OpenAI chunk format. The routing decision (tier, confidence, model) is logged and visible in analytics.

### Auth Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Get JWT token |
| `POST` | `/auth/refresh` | Refresh JWT token |

### Virtual Keys

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/keys` | List user's virtual keys |
| `POST` | `/keys` | Create virtual key (3 tiers) |
| `GET` | `/keys/{id}` | Get key details |
| `PUT` | `/keys/{id}` | Update key configuration |
| `DELETE` | `/keys/{id}` | Delete key |

Each key stores three tiers with per-tier: model name, API key (encrypted at rest), base URL, and provider type.

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analytics/summary` | Aggregated stats (cost, volume, latency, success rate) |
| `GET` | `/analytics/requests` | Paginated request log |
| `GET` | `/analytics/daily` | Daily breakdown for charts |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (includes DB status) |

## Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/login` | Login | JWT authentication |
| `/register` | Register | Account creation |
| `/` | Dashboard | Stats summary, recent requests, cost savings |
| `/keys` | Keys | Manage virtual keys with 3-tier configuration |
| `/chat` | Chat | Playground with real-time routing tier display |
| `/analytics` | Analytics | Cost trends, tier distribution, latency charts |
| `/profile` | Profile | Account settings |

## Provider Architecture

Adding a new provider requires one file and one registration call:

```python
# core/providers/my_provider.py
from core.providers.base import BaseProvider
from core.providers.registry import register_provider

class MyProvider(BaseProvider):
    async def chat(self, messages, model, api_key, **kwargs) -> dict:
        # Normalize to { "content": ..., "model": ..., "provider": ..., "usage": ... }
        ...

    async def chat_stream(self, messages, model, api_key, **kwargs):
        # Yield OpenAI-compatible chunk dicts
        ...

register_provider("my_provider", MyProvider)
```

Import the module in `main.py` and it registers itself. The dispatcher picks it up via the registry.

## Project Structure

```
classiroute/
├── backend/
│   ├── api/v1/              # Route handlers
│   │   ├── chat.py          # POST /v1/chat/completions
│   │   ├── auth.py          # Login, register, refresh
│   │   ├── keys.py          # Virtual key CRUD
│   │   ├── analytics.py     # Usage analytics
│   │   ├── users.py         # User profile
│   │   └── evaluate.py      # Internal eval endpoints
│   ├── core/
│   │   ├── router.py        # ML + heuristic routing decision
│   │   ├── feature_extractor.py  # 22-dimension prompt analysis
│   │   ├── dispatcher.py    # Provider dispatch + fallback chain
│   │   ├── rate_limiter.py  # Sliding window rate limiter
│   │   ├── dependencies.py  # FastAPI deps (auth, ratelimit)
│   │   ├── models/          # Pickled XGBoost models
│   │   └── providers/       # Provider implementations
│   │       ├── base.py      # Abstract provider interface
│   │       ├── registry.py  # Provider registration & lookup
│   │       ├── openai.py    # OpenAI-compatible provider
│   │       ├── anthropic.py # Anthropic provider
│   │       └── gemini.py    # Google Gemini provider
│   ├── auth/                # JWT handling, password hashing
│   ├── db/                  # SQLAlchemy models, CRUD, migrations
│   ├── services/            # Telemetry (PostHog), error tracking (Sentry)
│   ├── tests/               # Test suite
│   ├── Dockerfile           # Multi-stage build with uv
│   └── main.py              # FastAPI app entry point
├── frontend/
│   ├── src/
│   │   ├── pages/           # Login, Register, Dashboard, Keys, Chat, Analytics, Profile
│   │   ├── components/      # Shared UI components
│   │   ├── api/             # HTTP client layer
│   │   ├── context/         # Auth context
│   │   └── lib/             # Utility functions
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml       # App + PostgreSQL
├── render.yaml              # Render deployment config
└── docs/                    # Additional documentation
    ├── how-routing-works.md
    ├── multi-provider-adapters.md
    ├── docker.md
    └── monitoring.md
```

## Deployment

### Deploy to Render (Backend)

The project includes a `render.yaml` blueprint. Connect your Render account, point it at this repo, and the API deploys automatically with a PostgreSQL database provisioned alongside it.

### Deploy to Vercel (Frontend)

```bash
cd frontend
npx vercel --prod
```

Set `VITE_API_URL` to your Render API URL in the Vercel project settings.

### Environment Checklist for Production

- Generate strong `JWT_SECRET` and `ENCRYPTION_KEY`
- Use a managed PostgreSQL (Neon, Railway, Render PostgreSQL)
- Set `APP_ENV=production`
- Configure `CORS_ORIGINS` to your frontend domain
- Optionally add PostHog and Sentry keys

## Performance

On a benchmark of 15,000 prompts across diverse categories:

- **92.31% tier classification accuracy** (XGBoost vs human-labeled ground truth)
- **57.9% total cost reduction** compared to always routing to the strongest tier
- **96.8% quality parity** -- responses from the routed tier rated as acceptable vs always-strong
- **<50ms routing latency** (feature extraction + prediction, excluding provider response time)
- **22-dimensional feature space** captures prompt nuance without overfitting

## Contributing

Contributions are welcome. The project is structured to make it easy to add providers, improve the feature extractor, train better models, and polish the frontend.

What would help most:

- **New provider adapters** -- Add support for AWS Bedrock, Azure OpenAI, Cohere, Mistral, or any OpenAI-compatible provider.
- **Feature extractor improvements** -- Additional feature dimensions, better pattern detection, multilingual support.
- **Model training pipeline** -- Scripts for retraining the classifier and regressor on new datasets.
- **More evaluators** -- Additional benchmarks and evaluation datasets.
- **Frontend polish** -- Dark mode, localization, accessibility improvements.

Before submitting, run the tests:

```bash
cd backend
pytest
```

### Development Setup

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## License

This project is licensed under the MIT License — see [LICENSE](./LICENSE) for details.

---

<p align="center">
  <small>
    Built for the engineers who know that not every prompt needs a sledgehammer.
  </small>
</p>

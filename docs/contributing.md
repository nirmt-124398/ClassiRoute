# Contributing to ClassiRoute

Thanks for your interest in ClassiRoute. Every contribution helps make cost-aware LLM routing more accessible.

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct. By participating, you agree to uphold its standards. Report unacceptable behavior to the project maintainers.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setting Up the Development Environment](#setting-up-the-development-environment)
  - [Backend](#backend)
  - [Frontend](#frontend)
  - [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
  - [Backend Tests](#backend-tests)
  - [Frontend Tests](#frontend-tests)
- [Code Style and Linting](#code-style-and-linting)
  - [Python](#python)
  - [Frontend (TypeScript/React)](#frontend-typescriptreact)
- [Pull Request Process](#pull-request-process)
- [Adding a New Provider Adapter](#adding-a-new-provider-adapter)
- [Reporting Issues and Feature Requests](#reporting-issues-and-feature-requests)

---

## Prerequisites

| Tool | Minimum Version | Why |
|------|----------------|-----|
| Python | 3.13 | Runtime requirement |
| uv | latest | Python package management |
| Node.js | 18+ | Frontend toolchain |
| npm or bun | latest | Frontend dependencies |
| Docker | latest | PostgreSQL database |
| Git | any | Version control |

You can check your versions with:

```bash
python --version
uv --version
node --version
npm --version
docker --version
```

---

## Setting Up the Development Environment

### Backend

1. **Clone the repository.**

   ```bash
   git clone https://github.com/your-org/classiroute.git
   cd classiroute
   ```

2. **Set up the Python environment with uv.**

   uv handles everything including creating the virtual environment:

   ```bash
   cd backend
   uv sync
   ```

   This reads dependencies from `pyproject.toml`, creates a `.venv` if one does not exist, and installs all packages.

3. **Activate the virtual environment.**

   ```bash
   source .venv/bin/activate
   ```

4. **Start PostgreSQL.**

   From the project root:

   ```bash
   docker compose up db
   ```

   This starts a PostgreSQL 16 container on port 5432. The database name, user, and password are set in `docker-compose.yml` (defaults: `classiroute`, `postgres`, `classiroute`). You can override the password with `POSTGRES_PASSWORD`.

5. **Configure environment variables.**

   Copy the example env file:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` with your local settings. At minimum, set:

   ```env
   DATABASE_URL=postgresql://postgres:classiroute@localhost:5432/classiroute
   JWT_SECRET=some-random-64-char-string
   ENCRYPTION_KEY=your-generated-fernet-key
   APP_ENV=development
   ```

   Generate a Fernet encryption key with:

   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

6. **Run migrations.**

   The app runs alembic automatically on startup, or you can run them manually:

   ```bash
   alembic upgrade head
   ```

7. **Start the backend server.**

   ```bash
   uvicorn main:app --reload
   ```

   The API will be available at `http://localhost:8000`. The `--reload` flag picks up code changes automatically.

### Frontend

1. **Navigate to the frontend directory.**

   ```bash
   cd frontend
   ```

2. **Install dependencies.**

   ```bash
   npm install
   ```

   Or if you use bun:

   ```bash
   bun install
   ```

3. **Configure the API proxy.**

   The Vite config (`vite.config.ts`) proxies `/v1`, `/auth`, `/keys`, and `/analytics` routes to `http://localhost:8000`. No extra configuration needed if the backend is running on port 8000.

4. **Start the development server.**

   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:5173`.

### Full Stack

With both servers running, you get:

- **Frontend**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000`
- **API docs**: `http://localhost:8000/docs`
- **Database**: `localhost:5432`

---

## Running Tests

### Backend Tests

The backend uses pytest with async support. Tests are split into two categories: **unit** tests (no external dependencies) and **integration** tests (require a running database and API).

**Run all unit tests:**

```bash
cd backend
pytest -m unit
```

**Run all tests (including integration):**

```bash
RUN_INTEGRATION=1 pytest
```

**Run a specific test file:**

```bash
pytest tests/auth/test_login.py
```

**Run with coverage:**

```bash
pytest -m unit --cov=. --cov-report=term-missing
```

The test suite lives in `backend/tests/` with this layout:

| Directory | What It Tests |
|-----------|--------------|
| `tests/auth/` | Authentication endpoints |
| `tests/chat/` | Chat and streaming endpoints |
| `tests/keys/` | Virtual key management |
| `tests/core/` | Router, feature extractor, dispatcher |
| `tests/analytics/` | Analytics endpoints |
| `tests/users/` | User management |
| `tests/providers/` | Provider adapters (OpenAI, Anthropic, Gemini) |
| `tests/edge_cases/` | Error handling, edge cases |

Key configuration files:

- `tests/config.py` — `TestConfig` dataclass loaded from environment variables
- `tests/conftest.py` — Pytest fixtures (test client, auth helpers, report directory)
- `tests/helpers.py` — Utility functions (`api_call`, `auth_header_jwt`, etc.)
- `tests/run_tests.py` — Convenience test runner

Integration tests are skipped by default. Set `RUN_INTEGRATION=1` to enable them.

### Frontend Tests

The frontend uses **vitest** with jsdom for component tests.

**Run all tests:**

```bash
cd frontend
npx vitest run
```

**Run in watch mode (useful during development):**

```bash
npx vitest
```

**Run a specific test file:**

```bash
npx vitest run -- src/components/Button.test.tsx
```

Test setup is configured in `vite.config.ts`:

```ts
test: {
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
}
```

The setup file (`src/test/setup.ts`) imports `@testing-library/jest-dom/vitest` for DOM matchers.

---

## Code Style and Linting

### Python

ClassiRoute uses **basedpyright** (a strict fork of pyright) for type checking.

**Check types:**

```bash
cd backend
basedpyright
```

Configuration lives in `basedpyrightconfig.json`:

- `typeCheckingMode`: basic
- `pythonVersion`: 3.13
- Strict mode for CI (type hints required on all public functions and classes)

Guidelines:

- **Type hints are required** on all public functions and class methods.
- Use `from __future__ import annotations` in new files for cleaner annotations.
- Use `| None` instead of `Optional[T]`.
- Prefer `dataclass` or `pydantic.BaseModel` over plain dicts for structured data.
- Use `async def` for I/O-bound operations.
- Avoid wildcard imports (`from module import *`).
- Write docstrings for all public functions and classes. Use triple-quoted descriptions, not a rigid format.

### Frontend (TypeScript/React)

The frontend uses **ESLint** with `typescript-eslint`, `eslint-plugin-react-hooks`, and `eslint-plugin-react-refresh`.

**Lint the frontend:**

```bash
cd frontend
npm run lint
```

**Build the frontend (includes TypeScript checking):**

```bash
npm run build
```

This runs `tsc -b` followed by `vite build`. TypeScript errors will fail the build.

Configuration files:

- `tsconfig.json` — strict mode enabled
- `tsconfig.app.json` — app-specific TypeScript config
- `eslint.config.js` — ESLint flat config with recommended rules
- `vite.config.ts` — Vite and vitest config

Guidelines:

- **Strict TypeScript mode** is on. Avoid `any`; prefer `unknown` when the type is not known.
- Use functional components with hooks. No class components.
- Prefer `@/` path alias (e.g., `@/components/Button` instead of relative imports).
- Format with the project's Prettier config if available. Otherwise, keep formatting consistent with the surrounding code.

---

## Pull Request Process

1. **Create a feature branch from `main`.**

   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/my-feature-name
   ```

   Naming convention: `feat/`, `fix/`, `docs/`, `refactor/`, or `chore/` followed by a short description.

2. **Make your changes.** Keep commits focused and atomic. Each commit should represent a single logical change.

3. **Run the tests.**

   ```bash
   cd backend && pytest -m unit
   cd frontend && npx vitest run
   ```

   Make sure all tests pass before opening a PR.

4. **Check for lint and type errors.**

   ```bash
   cd backend && basedpyright
   cd frontend && npm run lint && npm run build
   ```

5. **Write or update tests** if you are adding a feature. For bug fixes, add a test that reproduces the bug before applying the fix.

6. **Push your branch and open a pull request.**

   ```bash
   git push origin feat/my-feature-name
   ```

   Open the PR on GitHub. In the description, explain what the change does and why. Reference any related issues.

7. **Address review feedback.** The maintainers may ask for changes. Push additional commits to address them.

8. **Merge.** Once approved, squash and merge into `main`. The `main` branch should always remain stable.

---

## Adding a New Provider Adapter

ClassiRoute uses a registry pattern for LLM providers. Adding a new provider takes a few steps.

### Step 1: Create the provider class

Every provider must implement `BaseProvider` from `core/providers/base.py`:

```python
from typing import AsyncGenerator

from core.providers.base import BaseProvider
from core.providers.registry import register_provider


class MyNewProvider(BaseProvider):
    """Description of what this provider wraps."""

    async def chat(
        self, messages: list, model: str, api_key: str, **kwargs
    ) -> dict:
        # Return normalized dict:
        return {
            "content": "...",       # str — the response text
            "model": "...",         # str — model identifier
            "provider": "...",      # str — provider label
            "usage": {              # dict — token counts
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int,
            },
        }

    async def chat_stream(
        self, messages: list, model: str, api_key: str, **kwargs
    ) -> AsyncGenerator[dict, None]:
        # Yield normalized dicts matching OpenAI chunk shape.
        # Final chunk must include usage.
        ...


# Register it
register_provider("my_provider", MyNewProvider)
```

Save this file in `backend/core/providers/my_provider.py`.

### Step 2: Register the import in main.py

Add an import in `backend/main.py` so the module is loaded (which triggers `register_provider`):

```python
import core.providers.my_provider  # noqa: F401
```

The import is placed alongside the existing provider imports (around line 15-17 in `main.py`).

### Step 3: Write tests

Create a test file in `backend/tests/providers/test_my_provider.py`:

```python
import pytest

class TestMyProvider:
    async def test_chat_basic(self):
        ...

    async def test_chat_stream(self):
        ...
```

### How the registry works

The system is intentionally simple. `core/providers/registry.py` maintains a global `PROVIDER_MAP` dict. Importing a provider module calls `register_provider(name, class)` which adds the class to the map. The dispatcher (`core/dispatcher.py`) calls `get_provider(type)` to instantiate the right adapter at runtime.

See `docs/multi-provider-adapters.md` for the full architecture doc and existing adapters in `core/providers/openai.py`, `core/providers/anthropic.py`, and `core/providers/gemini.py` for reference implementations.

---

## Reporting Issues and Feature Requests

### Bugs

Open a [GitHub issue](https://github.com/your-org/classiroute/issues) and include:

- A clear title and description
- Steps to reproduce (a minimal test case is ideal)
- Expected behavior vs actual behavior
- Python version, OS, and relevant dependency versions
- Logs or error output if available

### Feature Requests

Before opening a feature request, check existing issues and discussions to see if the feature has already been proposed. Include:

- What the feature does and why it is useful
- How the feature fits into ClassiRoute's goal of cost-aware LLM routing
- A rough sketch of the API or behavior if you have one

### Questions

For questions, start a [GitHub Discussion](https://github.com/your-org/classiroute/discussions) rather than opening an issue.

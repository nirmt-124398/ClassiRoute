import asyncio
import os
import sys
import subprocess
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.v1 import auth, keys, chat, analytics, users, keys_gemini, evaluate
from api.v1.keys_anthropic import router as keys_anthropic_router
from core import router as router_mod

# Register all provider adapters — triggers register_provider() calls
import core.providers.openai  # noqa: F401
import core.providers.anthropic  # noqa: F401
import core.providers.gemini  # noqa: F401
from services.error_tracking import init_sentry
from db.database import dispose_engine, check_db_connected


def _run_alembic_upgrade() -> None:
    project_dir = os.path.dirname(os.path.abspath(__file__))
    python = getattr(sys, "_venv_python", None) or sys.executable or "python3"
    result = subprocess.run(
        [python, "-c", "from alembic.config import main; main()", "upgrade", "head"],
        capture_output=True, text=True,
        cwd=project_dir,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Alembic migration failed:\n{msg}")
    if result.stdout.strip():
        print(f"[alembic] {result.stdout.strip()}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_alembic_upgrade)
    router_mod.load_models()
    init_sentry()
    yield
    await dispose_engine()


app = FastAPI(
    title="ClassiRoute",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow frontend (Vercel) to call backend (Render)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(keys.router, prefix="/keys", tags=["Keys"])
app.include_router(keys_gemini.router, prefix="/v1")
app.include_router(chat.router, prefix="/v1", tags=["Chat"])
app.include_router(keys_anthropic_router, prefix="/v1")
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(evaluate.router, tags=["Internal"])


@app.get("/health")
async def health():
    db_ok = await check_db_connected()
    return {
        "status": "ok" if db_ok else "degraded",
        "db_connected": db_ok,
        "model_loaded": router_mod.CLASSIFIER is not None,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled 500s — send to Sentry + PostHog, return JSON."""
    if isinstance(exc, HTTPException):
        raise exc

    with suppress(Exception):
        import sentry_sdk
        sentry_sdk.capture_exception(exc)

    with suppress(Exception):
        from services.telemetry import capture_error
        capture_error("unknown", str(exc), {"path": str(request.url)})

    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred"},
    )

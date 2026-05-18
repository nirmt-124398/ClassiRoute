import asyncio
import os
import subprocess
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.v1 import auth, keys, chat, analytics, users
from core import router as router_mod
from services.error_tracking import init_sentry


def _run_alembic_upgrade() -> None:
    """Run alembic upgrade head in a subprocess to avoid event loop conflicts."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(project_dir, ".venv", "bin", "python3")
    result = subprocess.run(
        [venv_python, "-c", "from alembic.config import main; main()", "upgrade", "head"],
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


app = FastAPI(
    title="LLMRouter",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(keys.router, prefix="/keys", tags=["Keys"])
app.include_router(chat.router, prefix="/v1", tags=["Chat"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(users.router, prefix="/users", tags=["Users"])


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": router_mod.CLASSIFIER is not None}


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

import asyncio
import logging
import os
import re
from collections.abc import AsyncGenerator

from sqlalchemy import exc as sa_exc, text as sa_text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Connection URL ──────────────────────────────────────────────────────────

raw_database_url = os.getenv("DATABASE_URL")
if raw_database_url:
    if raw_database_url.startswith("postgres://"):
        raw_database_url = raw_database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw_database_url.startswith("postgresql://") and "+asyncpg" not in raw_database_url:
        raw_database_url = raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    raw_database_url = re.sub(r"(?i)[?&]sslmode=[^&]*", "", raw_database_url).replace("?&", "?").rstrip("?").rstrip("&")

DATABASE_URL = raw_database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
DB_SCHEMA = os.getenv("DB_SCHEMA")

# ── Connection pool sizing (from env or sensible defaults) ──────────────────

POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))       # 30 min — cloud PG kills idle conns after 5-15m
POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() in ("true", "1", "yes")

connect_args: dict = {}
if DB_SCHEMA:
    connect_args["server_settings"] = {"search_path": DB_SCHEMA}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ── Engine lifecycle for app shutdown ───────────────────────────────────────

_engine_disposed = False
_dispose_lock = asyncio.Lock()


async def dispose_engine() -> None:
    """Dispose the async engine, releasing all pooled connections.

    Call during app shutdown (lifespan shutdown hook).
    Safe to call multiple times.
    """
    global _engine_disposed
    if _engine_disposed:
        return
    async with _dispose_lock:
        if _engine_disposed:
            return
        _engine_disposed = True
        try:
            await engine.dispose()
            logger.info("Database engine disposed")
        except Exception as exc:
            logger.warning("Error disposing database engine: %s", exc)


# ── Retryable error types ───────────────────────────────────────────────────

DB_RETRYABLE = (
    sa_exc.InterfaceError,    # connection closed, broken pipe
    sa_exc.OperationalError,  # server gone away, can't connect
    sa_exc.TimeoutError,      # pool timeout
)


async def _create_session_with_retry() -> AsyncSession:
    """Create a new session, retrying once on transient connection errors."""
    try:
        return AsyncSessionLocal()
    except DB_RETRYABLE as exc:
        logger.warning("DB session creation failed (will retry once): %s", exc)
        await asyncio.sleep(0.5)
        return AsyncSessionLocal()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a ready-to-use AsyncSession.

    If an execution inside the request fails with a retryable connection error,
    the session is replaced transparently and the operation is **not** retried
    here (the request handler must decide). Most callers rely on
    ``pool_pre_ping``, which eliminates the vast majority of stale-connection
    problems at checkout time.
    """
    session = await _create_session_with_retry()
    try:
        yield session
    except DB_RETRYABLE as exc:
        logger.error("Request failed with DB connection error: %s", exc)
        raise
    finally:
        try:
            await session.close()
        except sa_exc.InterfaceError:
            logger.debug("Connection already closed during session cleanup")


async def get_db_standalone() -> AsyncSession:
    """Create a fresh session for fire-and-forget background tasks.

    The caller **must** close the session when done::

        db = await get_db_standalone()
        try:
            ...
        finally:
            await db.close()
    """
    return await _create_session_with_retry()


# ── Retry helper for critical DB operations ─────────────────────────────────

MAX_DB_RETRIES = int(os.getenv("DB_MAX_RETRIES", "1"))


async def run_with_retry(db_op, *args, session: AsyncSession | None = None, **kwargs):
    """Execute *db_op(session, *args, **kwargs)* with retry on connection errors.

    Parameters
    ----------
    db_op
        An async callable that accepts ``session`` as its first positional
        argument, e.g. ``crud.get_key_by_hash``.
    session : AsyncSession | None
        If provided, the operation is attempted on *session* first. On
        retryable failure a **new** session is created and the operation
        retried once.
    *args, **kwargs
        Forwarded to *db_op* after ``session``.

    Returns
    -------
    Whatever *db_op* returns.

    Examples
    --------
    ::

        vkey = await run_with_retry(crud.get_key_by_hash, key_hash=hashed, session=db)
    """
    current_session = session or await _create_session_with_retry()
    try:
        return await db_op(current_session, *args, **kwargs)
    except DB_RETRYABLE as exc:
        logger.warning("DB error on attempt 1/%d: %s", MAX_DB_RETRIES + 1, exc)
    except Exception:
        if session is None:
            await current_session.close()
        raise

    # ── retry with fresh session ───────────────────────────────────────
    if current_session is not session:
        await current_session.close()

    await asyncio.sleep(0.5)
    current_session = await _create_session_with_retry()
    try:
        logger.info("Retrying DB operation on fresh session")
        return await db_op(current_session, *args, **kwargs)
    except DB_RETRYABLE as exc:
        logger.error("DB operation failed after retry: %s", exc)
        raise
    finally:
        if session is None:
            await current_session.close()


# ── Connection check for health endpoint ────────────────────────────────────

async def check_db_connected(max_attempts: int = 2) -> bool:
    """Return ``True`` if the database is reachable.

    Runs ``SELECT 1``. Retries once on failure. Used by the ``/health``
    endpoint.
    """
    for attempt in range(1, max_attempts + 1):
        sess = AsyncSessionLocal()
        try:
            await sess.execute(sa_text("SELECT 1"))
            return True
        except DB_RETRYABLE as exc:
            logger.warning("DB health check attempt %d/%d failed: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                await asyncio.sleep(0.5)
        finally:
            await sess.close()
    return False

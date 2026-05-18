import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# Prefer an async driver for SQLAlchemy's async engine.
raw_database_url = os.getenv("DATABASE_URL")
if raw_database_url:
    if raw_database_url.startswith("postgres://"):
        raw_database_url = raw_database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw_database_url.startswith("postgresql://") and "+asyncpg" not in raw_database_url:
        raw_database_url = raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Default to a local dev DB if missing for safety during dev.
DATABASE_URL = raw_database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
DB_SCHEMA = os.getenv("DB_SCHEMA")

connect_args = {}
if DB_SCHEMA:
    connect_args["server_settings"] = {"search_path": DB_SCHEMA}

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

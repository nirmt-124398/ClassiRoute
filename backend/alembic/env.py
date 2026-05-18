import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema

from alembic import context

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from db.database import Base  # noqa: E402
from db import models  # noqa: E402, F401

target_metadata = Base.metadata


def get_url() -> str:
    raw_url = os.getenv("DATABASE_URL")
    if raw_url:
        if raw_url.startswith("postgres://"):
            return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgresql://") and "+asyncpg" not in raw_url:
            return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return raw_url
    return "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"


def run_migrations_offline() -> None:
    url = get_url().replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    db_schema = os.getenv("DB_SCHEMA")
    if db_schema:
        connection.execute(CreateSchema(db_schema, if_not_exists=True))
        connection.execute(text(f"SET search_path TO {db_schema}"))
    context.configure(connection=connection, target_metadata=target_metadata)
    context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

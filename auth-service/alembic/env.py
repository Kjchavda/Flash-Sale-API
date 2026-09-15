import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from dotenv import load_dotenv

# Ensure auth-service directory is in sys.path
auth_service_dir = Path(__file__).resolve().parent.parent
if str(auth_service_dir) not in sys.path:
    sys.path.insert(0, str(auth_service_dir))

# Load .env from auth-service folder
env_path = auth_service_dir / ".env"
load_dotenv(dotenv_path=env_path)

config = context.config
db_url = os.getenv("DIRECT_DATABASE_URL") or os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError("DIRECT_DATABASE_URL or DATABASE_URL is not set")

if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

try:
    from app.database import Base
    from app.models import User
except ImportError:
    from auth_service.app.database import Base
    from auth_service.app.models import User

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    # Only manage objects in the 'auth' schema for auth-service
    if type_ == "table":
        return object.schema == "auth"
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema="auth",
        version_table="alembic_version",
        include_object=include_object,
    )

    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="auth",
        version_table="alembic_version",
        include_object=include_object,
    )

    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
        connect_args={"ssl": True},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")


def engine_options() -> dict[str, Any]:
    """Shared by the app engine and Alembic so both connect the same way."""
    if _is_sqlite:
        return {"connect_args": {"check_same_thread": False}, "poolclass": NullPool}
    options: dict[str, Any] = {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
    if settings.DATABASE_SSL:
        options["connect_args"] = {"ssl": "require"}
    return options


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    **engine_options(),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """One session per request.

    Services commit explicitly *before* returning. Committing here, after the `yield`,
    would run after the response has already been sent (FastAPI >= 0.118), so a failed
    commit would reach the client as a success.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

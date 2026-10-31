# from collections.abc import AsyncGenerator
# from typing import Any

# from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
# from sqlalchemy.orm import DeclarativeBase
# from sqlalchemy.pool import NullPool

# from app.core.config import settings

# _is_sqlite = settings.DATABASE_URL.startswith("sqlite")


# def engine_options() -> dict[str, Any]:
#     """Shared by the app engine and Alembic so both connect the same way."""
#     if _is_sqlite:
#         return {"connect_args": {"check_same_thread": False}, "poolclass": NullPool}
#     options: dict[str, Any] = {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
#     if settings.DATABASE_SSL:
#         options["connect_args"] = {"ssl": "require"}
#     return options


# engine = create_async_engine(
#     settings.DATABASE_URL,
#     echo=settings.DATABASE_ECHO,
#     **engine_options(),
# )

# AsyncSessionLocal = async_sessionmaker(
#     bind=engine,
#     class_=AsyncSession,
#     expire_on_commit=False,
#     autocommit=False,
#     autoflush=False,
# )


# class Base(DeclarativeBase):
#     pass


# async def get_db() -> AsyncGenerator[AsyncSession, None]:
#     """One session per request.

#     Services commit explicitly *before* returning. Committing here, after the `yield`,
#     would run after the response has already been sent (FastAPI >= 0.118), so a failed
#     commit would reach the client as a success.
#     """
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise


from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

# ---------------------------------------------------------
# Database configuration
# ---------------------------------------------------------

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")


def engine_options() -> dict[str, Any]:
    """
    Return database engine options.

    SQLite:
        Uses NullPool and check_same_thread=False.

    PostgreSQL / Neon:
        Uses connection pooling, pre-ping, and optional SSL.
    """

    if _is_sqlite:
        return {
            "connect_args": {
                "check_same_thread": False,
            },
            "poolclass": NullPool,
        }

    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE,
    }

    if settings.DATABASE_SSL:
        options["connect_args"] = {
            "ssl": "require",
        }

    return options


# ---------------------------------------------------------
# Async database engine
# ---------------------------------------------------------

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    **engine_options(),
)


# ---------------------------------------------------------
# Async session factory
# ---------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------
# SQLAlchemy declarative base
# ---------------------------------------------------------


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    """

    pass


# ---------------------------------------------------------
# FastAPI database dependency
# ---------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide one AsyncSession per request.

    Services should commit explicitly.

    If an exception occurs during the request, the session
    transaction is rolled back before the exception propagates.
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session

        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------
# Database connection lifecycle
# ---------------------------------------------------------


async def dispose_db() -> None:
    """
    Dispose the database engine and release pooled connections.

    Call this during application shutdown.
    """

    await engine.dispose()

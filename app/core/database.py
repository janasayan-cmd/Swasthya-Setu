"""Database access boundary using SQLAlchemy 2.x Async Engine.

IMPORTANT ARCHITECTURAL BOUNDARY:
- The database schema, models, and migrations are owned by the Database Team.
- Do NOT create tables or clinical models in this module.
- This layer provides connection management, session pooling, and readiness probing.
"""

import asyncio
from collections.abc import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableException
from app.core.logging import get_logger

logger = get_logger("app.database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine | None:
    """Retrieve or initialize the SQLAlchemy 2.x AsyncEngine."""
    global _engine, _session_factory
    settings = get_settings()

    if _engine is not None:
        return _engine

    if not settings.DATABASE_URL:
        logger.info("DATABASE_URL is not set. Database integration is dormant.")
        return None

    try:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG and not settings.is_production,
            pool_pre_ping=settings.DB_POOL_PRE_PING,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            future=True,
        )
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        logger.info("Database async engine and session factory initialized.")
        return _engine
    except Exception as e:
        logger.warning(f"Could not initialize database engine: {e}")
        _engine = None
        _session_factory = None
        return None


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Retrieve the session factory if engine is initialized."""
    if _session_factory is None:
        get_engine()
    return _session_factory


async def close_database_engine() -> None:
    """Cleanly dispose of the async database engine during application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        logger.info("Disposing database connection pool...")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection pool disposed.")


async def check_database_health(timeout_seconds: float = 10.0) -> bool:
    """Probe database connectivity for the readiness endpoint.

    Returns True if a simple query (SELECT 1) succeeds within the timeout.
    Returns False if engine is not configured, unreachable, or times out.
    """
    engine = get_engine()
    if engine is None:
        return False

    try:
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.scalar()
                return row == 1
    except Exception as exc:
        logger.warning(f"Database readiness probe failed: {exc}")
        return False


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for FastAPI route handlers requiring database access."""
    session_factory = get_session_factory()
    if session_factory is None:
        raise ServiceUnavailableException(
            message="Database connectivity is not currently configured or available."
        )

    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

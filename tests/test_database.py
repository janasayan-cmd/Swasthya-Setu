
"""Tests for database boundary and connection handling."""

import pytest
from app.core.database import (
    check_database_health,
    close_database_engine,
    get_db_session,
    get_engine,
)
from app.core.exceptions import ServiceUnavailableException


@pytest.mark.asyncio
async def test_database_health_false_when_unconfigured():
    """When DATABASE_URL is not set, database health probe returns False cleanly."""
    is_ok = await check_database_health()
    assert is_ok is False


@pytest.mark.asyncio
async def test_session_dependency_raises_when_unavailable():
    """Requesting a database session when the engine is unavailable raises ServiceUnavailableException."""
    gen = get_db_session()
    with pytest.raises(ServiceUnavailableException) as exc_info:
        await gen.__anext__()
    assert "Database connectivity is not currently configured" in exc_info.value.message


@pytest.mark.asyncio
async def test_database_engine_lifecycle():
    """Engine disposal should complete gracefully without throwing errors."""
    await close_database_engine()

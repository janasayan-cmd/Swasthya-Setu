"""Tests for application readiness endpoint."""

from unittest.mock import patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_readiness_when_database_available(async_client: AsyncClient):
    """Test GET /api/v1/ready returns 200 OK when database is reachable."""
    with patch("app.services.health.check_database_health", return_value=True):
        response = await async_client.get("/api/v1/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] in ("available", "ok")


@pytest.mark.asyncio
async def test_readiness_when_database_unavailable(async_client: AsyncClient):
    """Test GET /api/v1/ready returns 503 Service Unavailable when database is unreachable."""
    with patch("app.services.health.check_database_health", return_value=False):
        response = await async_client.get("/api/v1/ready")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_includes_request_id(async_client: AsyncClient):
    """Test readiness response includes X-Request-ID header."""
    with patch("app.services.health.check_database_health", return_value=True):
        response = await async_client.get("/api/v1/ready")
        assert "X-Request-ID" in response.headers

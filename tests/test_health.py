"""Tests for application health/liveness endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    """Test GET /api/v1/health returns 200 with standard liveness response."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "healthsetu-backend"
    assert "version" in data
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_does_not_leak_secrets(async_client: AsyncClient):
    """Ensure /api/v1/health never exposes database credentials or internal secrets."""
    response = await async_client.get("/api/v1/health")
    content = response.text.lower()
    for sensitive_word in ("password", "secret", "postgresql", "token", "key"):
        assert sensitive_word not in content


@pytest.mark.asyncio
async def test_health_includes_request_id(async_client: AsyncClient):
    """Ensure health endpoint responses include the correlation ID header."""
    response = await async_client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0

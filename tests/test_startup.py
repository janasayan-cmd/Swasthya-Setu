"""Tests for application startup, lifespan, and OpenAPI schema configuration."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_openapi_schema_available(async_client: AsyncClient):
    """Test that the OpenAPI JSON specification is generated and matches metadata."""
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    assert schema["info"]["title"] == "HealthSetu API"
    assert schema["info"]["version"] == "1.0.0"
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/ready" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/refresh" in schema["paths"]
    assert "/api/v1/auth/logout" in schema["paths"]
    assert "/api/v1/auth/me" in schema["paths"]


@pytest.mark.asyncio
async def test_swagger_docs_available(async_client: AsyncClient):
    """Test Swagger UI docs endpoint responds successfully in test/dev environment."""
    response = await async_client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "html" in response.text.lower()


@pytest.mark.asyncio
async def test_redoc_available(async_client: AsyncClient):
    """Test ReDoc documentation endpoint responds successfully in test/dev environment."""
    response = await async_client.get("/redoc")
    assert response.status_code == 200
    assert "redoc" in response.text.lower() or "html" in response.text.lower()

"""Tests for application settings and configuration management."""

import pytest
from app.core.config import Settings, parse_cors_origins


def test_default_config():
    """Verify default configuration values."""
    settings = Settings()
    assert settings.APP_NAME == "HealthSetu"
    assert settings.APP_VERSION == "1.0.0"
    assert settings.PORT == 8000
    assert settings.REQUEST_ID_HEADER == "X-Request-ID"
    assert settings.API_PREFIX == "/api/v1"


def test_cors_origin_parser():
    """Test CORS origin parsing handles commas, trailing slashes, and spaces."""
    raw = "http://localhost:3000, https://app.healthsetu.org/ , http://127.0.0.1:8000"
    parsed = parse_cors_origins(raw)
    assert parsed == [
        "http://localhost:3000",
        "https://app.healthsetu.org",
        "http://127.0.0.1:8000",
    ]


def test_environment_helpers():
    """Test environment helper properties."""
    dev_settings = Settings(APP_ENV="development")
    assert dev_settings.is_development is True
    assert dev_settings.is_production is False
    assert dev_settings.docs_url == "/docs"

    prod_settings = Settings(APP_ENV="production")
    assert prod_settings.is_production is True
    assert prod_settings.is_development is False
    assert prod_settings.docs_url is None
    assert prod_settings.redoc_url is None
    assert prod_settings.openapi_url is None

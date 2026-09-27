"""Tests for Production Observability, Monitoring, and Metrics Instrumentation (Phase 18).

Validates:
- Bounded-cardinality route normalization (no patient_id or request_id in labels)
- HTTP request metrics and latency tracking
- Security, authentication, and authorization metrics
- Database connectivity error metrics
- External healthcare provider telemetry (OCR, AI, Medication Safety)
- Background job lifecycle metrics
- Slow request threshold detection and warning emission
- GET /api/v1/metrics (both Prometheus text and JSON summary formats)
- GET /metrics alias
"""

import logging
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.metrics import metrics, normalize_route_path


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before each test for clean isolation."""
    metrics.reset()
    yield
    metrics.reset()


class TestMetricsInstrumentation:
    """Unit tests for the MetricsCollector engine."""

    def test_route_normalization_bounds_cardinality(self):
        """Route normalization must eliminate specific patient/user IDs from metric labels."""
        raw_paths = [
            "/api/v1/patients/pat-001/medications",
            "/api/v1/patients/HS-PAT-8921/care-plans",
            "/api/v1/documents/doc-550e8400-e29b-41d4-a716-446655440000",
            "/api/v1/facilities/hosp-apollo-01/departments",
            "/api/v1/users/usr-doctor-001",
        ]
        expected_templates = [
            "/api/v1/patients/{patient_id}/medications",
            "/api/v1/patients/{patient_id}/care-plans",
            "/api/v1/documents/{document_id}",
            "/api/v1/facilities/{facility_id}/departments",
            "/api/v1/users/{user_id}",
        ]
        for raw, expected in zip(raw_paths, expected_templates):
            normalized = normalize_route_path(raw)
            assert normalized == expected
            # Ensure no specific UUID or sensitive ID token remains
            assert "pat-001" not in normalized
            assert "HS-PAT-8921" not in normalized
            assert "550e8400" not in normalized

    def test_record_http_request_and_summary(self):
        """HTTP metrics collector accurately counts requests, status codes, and latency percentiles."""
        metrics.record_http_request("GET", "/api/v1/health", 200, 15.0)
        metrics.record_http_request("GET", "/api/v1/health", 200, 25.0)
        metrics.record_http_request("POST", "/api/v1/auth/login", 401, 100.0)
        metrics.record_http_request("GET", "/api/v1/ready", 503, 50.0)

        summary = metrics.get_summary()
        assert summary["http"]["total_requests"] == 4
        assert summary["http"]["status_4xx"] == 1
        assert summary["http"]["status_5xx"] == 1
        assert summary["http"]["latency_ms"]["p50"] > 0
        assert summary["http"]["latency_ms"]["p99"] >= summary["http"]["latency_ms"]["p50"]

    def test_security_and_database_metrics(self):
        """Security failures and database errors are tracked accurately."""
        metrics.record_auth_failure()
        metrics.record_auth_failure()
        metrics.record_authz_denial()
        metrics.record_database_error()

        summary = metrics.get_summary()
        assert summary["security"]["authentication_failures"] == 2
        assert summary["security"]["authorization_denials"] == 1
        assert summary["database"]["errors_total"] == 1

    def test_external_provider_telemetry(self):
        """External provider latency, errors, and timeouts are tracked per provider."""
        metrics.record_provider_request("ocr", success=True, duration_ms=120.0)
        metrics.record_provider_request("ocr", success=False, duration_ms=45.0)
        metrics.record_provider_request("ai", success=True, duration_ms=300.0)
        metrics.record_provider_request("medication_safety", success=False, is_timeout=True)

        summary = metrics.get_summary()
        providers = summary["external_providers"]
        assert "ocr" in providers
        assert providers["ocr"]["total"] == 2
        assert providers["ocr"]["errors"] == 1

        assert "medication_safety" in providers
        assert providers["medication_safety"]["timeouts"] == 1

    def test_background_job_telemetry(self):
        """Background job lifecycle transitions and failures are tracked."""
        metrics.record_background_job("document_processing", "started")
        metrics.record_background_job("document_processing", "completed")
        metrics.record_background_job("fhir_import", "failed")

        summary = metrics.get_summary()
        jobs = summary["background_jobs"]
        assert jobs["failures_total"] == 1
        assert jobs["by_type"].get("fhir_import") == 1

    def test_prometheus_exposition_format(self):
        """Prometheus text format contains expected metric definitions and values."""
        metrics.record_http_request("GET", "/api/v1/health", 200, 20.0)
        metrics.record_auth_failure()
        metrics.record_database_error()

        prom_text = metrics.to_prometheus_text()
        assert "# HELP http_requests_total" in prom_text
        assert 'http_requests_total{method="GET",route="/api/v1/health",status_code="200"} 1' in prom_text
        assert "authentication_failures_total 1" in prom_text
        assert "database_errors_total 1" in prom_text


class TestObservabilityEndpoints:
    """Integration tests for the metrics API routes."""

    @pytest.mark.asyncio
    async def test_get_metrics_prometheus_format(self, async_client: AsyncClient):
        """GET /api/v1/metrics returns Prometheus text by default."""
        response = await async_client.get("/api/v1/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        text = response.text
        assert "http_requests_total" in text
        assert "http_requests_in_progress" in text

    @pytest.mark.asyncio
    async def test_get_metrics_json_format(self, async_client: AsyncClient):
        """GET /api/v1/metrics?format=json returns structured telemetry dictionary."""
        response = await async_client.get("/api/v1/metrics?format=json")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        data = response.json()
        assert "http" in data
        assert "security" in data
        assert "database" in data
        assert "version" in data
        assert "environment" in data

    @pytest.mark.asyncio
    async def test_root_metrics_alias(self, async_client: AsyncClient):
        """GET /metrics root alias serves standard Prometheus scraper format."""
        response = await async_client.get("/metrics")
        assert response.status_code == 200
        assert "http_requests_total" in response.text

    @pytest.mark.asyncio
    async def test_slow_request_detection(self, async_client: AsyncClient, caplog):
        """Requests exceeding SLOW_REQUEST_THRESHOLD_MS emit a WARNING log."""
        settings = get_settings()
        original_threshold = settings.SLOW_REQUEST_THRESHOLD_MS
        # Set threshold to 0ms so any request triggers slow detection
        settings.SLOW_REQUEST_THRESHOLD_MS = 0

        with caplog.at_level(logging.WARNING):
            res = await async_client.get("/api/v1/health")
            assert res.status_code == 200

        # Reset threshold
        settings.SLOW_REQUEST_THRESHOLD_MS = original_threshold

        slow_logs = [r for r in caplog.records if "SLOW REQUEST" in r.message]
        assert len(slow_logs) >= 1
        assert slow_logs[0].levelno == logging.WARNING
        assert "/api/v1/health" in slow_logs[0].message

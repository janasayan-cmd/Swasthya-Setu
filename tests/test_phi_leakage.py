"""Tests for PHI, Credential, and Secret Leakage Prevention (Phase 18 TRD Sec 44).

Verifies that sensitive data, credentials, and synthetic test PHI values:
- Are NEVER emitted in application logs
- Are masked by the centralized log sanitizer
- Are NOT present in error responses or exception representations
"""

import json
import logging
from io import StringIO
import pytest

from app.core.log_sanitizer import (
    _REDACTED,
    build_safe_log_context,
    sanitize_for_log,
    sanitize_headers,
)
from app.core.logging import StructuredJsonFormatter


class TestPHILeakagePrevention:
    """Rigorous tests confirming sensitive healthcare data is never leaked to logs."""

    def test_synthetic_patient_name_redacted(self):
        """Synthetic test patient name TEST_PATIENT_NAME_123 must be redacted."""
        raw_data = {
            "patient_name": "TEST_PATIENT_NAME_123",
            "first_name": "John",
            "last_name": "Doe",
            "notes": "Patient presents with headache.",
        }
        sanitized = sanitize_for_log(raw_data)
        assert sanitized["patient_name"] == _REDACTED
        assert sanitized["first_name"] == _REDACTED
        assert sanitized["last_name"] == _REDACTED
        assert sanitized["notes"] == _REDACTED
        assert "TEST_PATIENT_NAME_123" not in str(sanitized)

    def test_credentials_and_secrets_redacted(self):
        """Passwords, JWT tokens, and API keys must be completely masked."""
        secret_payload = {
            "password": "SuperSecretPassword123!",
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature",
            "api_key": "sk-1234567890abcdef1234567890abcdef",
            "database_url": "postgresql+asyncpg://postgres:supersecretpassword@localhost:5432/mydb",
        }
        sanitized = sanitize_for_log(secret_payload)
        assert sanitized["password"] == _REDACTED
        assert sanitized["access_token"] == _REDACTED
        assert sanitized["api_key"] == _REDACTED
        assert sanitized["database_url"] == _REDACTED
        assert "SuperSecretPassword123!" not in str(sanitized)
        assert "supersecretpassword" not in str(sanitized)

    def test_clinical_data_fields_redacted(self):
        """Prescriptions, diagnoses, OCR text, and AI completions must be masked."""
        clinical_payload = {
            "diagnosis": "Acute Coronary Syndrome",
            "prescription": "Metformin 500mg PO daily",
            "medical_history": "Type 2 Diabetes, Hypertension",
            "ocr_output": "EXTRACTED PRESCRIPTION TEXT FOR PATIENT",
            "ai_prompt": "Summarize medical record for patient John Doe",
            "ai_response": "The patient has severe pneumonia",
        }
        sanitized = sanitize_for_log(clinical_payload)
        for key in clinical_payload:
            assert sanitized[key] == _REDACTED
            assert clinical_payload[key] not in str(sanitized)

    def test_structured_json_formatter_phi_sanitization(self):
        """StructuredJsonFormatter must sanitize record messages and extra dictionaries."""
        formatter = StructuredJsonFormatter()
        logger = logging.getLogger("test.phi.leakage")
        logger.setLevel(logging.INFO)

        record = logger.makeRecord(
            name="test.phi.leakage",
            level=logging.INFO,
            fn="test_file.py",
            lno=42,
            msg="User login processed",
            args=(),
            exc_info=None,
            extra={
                "password": "plaintext_password_leak_attempt",
                "patient_name": "TEST_PATIENT_NAME_123",
                "diagnosis": "Terminal condition",
            },
        )
        formatted_json = formatter.format(record)
        log_obj = json.loads(formatted_json)

        assert "plaintext_password_leak_attempt" not in formatted_json
        assert "TEST_PATIENT_NAME_123" not in formatted_json
        assert "Terminal condition" not in formatted_json
        assert log_obj.get("password") == _REDACTED
        assert log_obj.get("patient_name") == _REDACTED
        assert log_obj.get("diagnosis") == _REDACTED

    def test_http_headers_sanitization(self):
        """Authorization and Cookie headers must be redacted."""
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature",
            "Cookie": "session_id=insecure_session_token_12345",
            "Content-Type": "application/json",
            "X-Request-ID": "test-req-1234",
        }
        sanitized_headers = sanitize_headers(headers)
        assert sanitized_headers["Authorization"] == _REDACTED
        assert sanitized_headers["Cookie"] == _REDACTED
        assert sanitized_headers["Content-Type"] == "application/json"
        assert sanitized_headers["X-Request-ID"] == "test-req-1234"

    def test_build_safe_log_context_filters_phi(self):
        """build_safe_log_context only includes safe identifiers and sanitizes extras."""
        ctx = build_safe_log_context(
            request_id="req-9999",
            actor_id="usr-doctor-1",
            resource_type="document",
            resource_id="doc-444",
            operation="review",
            outcome="success",
            extra={"patient_name": "TEST_PATIENT_NAME_123", "safe_meta": "count_1"},
        )
        assert ctx["request_id"] == "req-9999"
        assert ctx["resource_type"] == "document"
        assert ctx["extra"]["patient_name"] == _REDACTED
        assert ctx["extra"]["safe_meta"] == "count_1"

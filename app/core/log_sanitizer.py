"""Centralized PHI-safe log sanitization for HealthSetu.

SECURITY POLICY
================
This module is the SINGLE sanitization point for all log output.
Individual endpoints, services, and repositories must NOT perform
their own ad-hoc log sanitization.

PHI EXCLUSION GUARANTEES
=========================
- Passwords, tokens, API keys, secrets are ALWAYS redacted.
- Complete patient records, documents, prescriptions are ALWAYS redacted.
- AI prompts and AI raw outputs containing PHI are ALWAYS redacted.
- Clinical note bodies, document content, medication details are ALWAYS redacted.

WHAT IS SAFE TO LOG
====================
- request_id
- actor_id (user/clinician UUID)
- resource_type (e.g. "patient", "document")
- resource_id (UUID/identifier only)
- operation name
- result/outcome
- error code (NOT error details containing PHI)
- timestamp
- provider name
- latency
- security event type
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Exact field name redaction (case-insensitive key match)
# ---------------------------------------------------------------------------

_EXACT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        # Credentials & secrets
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "jwt",
        "api_key",
        "apikey",
        "api_secret",
        "client_secret",
        "private_key",
        "signing_key",
        "auth_token",
        "bearer",
        # HTTP headers
        "authorization",
        "x-api-key",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        # PHI — identity
        "ssn",
        "national_id",
        "passport_number",
        "date_of_birth",
        "dob",
        "birth_date",
        "patient_name",
        "full_name",
        "first_name",
        "last_name",
        "address",
        "phone",
        "phone_number",
        "mobile",
        "email",
        "database_url",
        "db_url",
        "connection_string",
        # PHI — clinical content
        "diagnosis",
        "diagnoses",
        "prescription",
        "prescriptions",
        "prescription_text",
        "medication",
        "medications",
        "medication_details",
        "allergy",
        "allergies",
        "allergy_details",
        "symptoms",
        "symptom_details",
        "medical_history",
        "history",
        "clinical_notes",
        "clinical_note",
        "notes",
        "note",
        "clinical_note_body",
        "clinical_note_content",
        "clinical_note_text",
        "document_content",
        "document_text",
        "document_body",
        "patient_data",
        "patient_record",
        "raw_document",
        "extracted_text",
        "ocr_result",
        "ocr_text",
        "ocr_output",
        # PHI — AI
        "prompt",
        "prompt_text",
        "ai_prompt",
        "ai_input",
        "raw_prompt",
        "full_prompt",
        "system_prompt",
        "ai_output",
        "ai_response",
        "raw_output",
        "raw_content",
        "raw_text",
        "generated_text",
        "completion",
        "ai_completion",
        # PHI — transfers / interoperability
        "clinical_context",
        "transfer_context",
        "clinical_summary",
        "discharge_summary",
        "discharge_instructions",
        "interoperability_data",
        "fhir_resource",
        "hl7_message",
        # PHI — care
        "care_plan_content",
        "sbar_content",
        "sbar_text",
        "vitals",
        "vital_signs",
        # Storage
        "storage_key",
        "signed_url",
        "presigned_url",
        "download_url",
    }
)

# ---------------------------------------------------------------------------
# Substring-based key redaction (if key contains any of these substrings)
# ---------------------------------------------------------------------------

_SENSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "signing_key",
    "credential",
    "auth_header",
    "authorization",
    "clinical_note",
    "document_content",
    "prescription_text",
    "patient_data",
    "patient_name",
    "database_url",
    "ai_prompt",
    "ai_output",
    "ai_response",
    "ocr_output",
    "diagnosis",
    "medication",
    "medical_history",
)

# ---------------------------------------------------------------------------
# Value-pattern redaction (regex matches on values regardless of key)
# ---------------------------------------------------------------------------

_VALUE_PATTERNS: list[re.Pattern[str]] = [
    # JWT tokens (3 base64url segments)
    re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
    # Bearer tokens in Authorization header values
    re.compile(r"Bearer\s+[A-Za-z0-9\-_.~+/]+=*", re.IGNORECASE),
    # Generic API keys (long alphanumeric strings starting with common prefixes)
    re.compile(r"\b(?:sk|pk|rk|ak)-[A-Za-z0-9]{20,}\b"),
    # Synthetic test patient tokens
    re.compile(r"TEST_PATIENT_[A-Za-z0-9_]+", re.IGNORECASE),
    # Database connection URLs with credentials
    re.compile(r"postgres(?:ql)?(?:\+[a-z0-9]+)?://[^@\s]+@[^\s/]+/[^\s]+", re.IGNORECASE),
]

_REDACTED = "[REDACTED]"
_MAX_SAFE_DEPTH = 10  # Prevent infinite recursion on deep nested structures


def _is_sensitive_key(key: str) -> bool:
    """Return True if this dictionary key should be redacted."""
    lower = str(key).lower().replace("-", "_")
    if lower in _EXACT_SENSITIVE_KEYS:
        return True
    return any(sub in lower for sub in _SENSITIVE_SUBSTRINGS)


def _sanitize_str_value(value: str) -> str:
    """Redact known secret/PHI patterns embedded in string values."""
    for pattern in _VALUE_PATTERNS:
        if pattern.search(value):
            return _REDACTED
    return value


def sanitize_for_log(data: Any, _depth: int = 0) -> Any:
    """Recursively sanitize a value for safe logging.

    Handles:
    - dict: redacts sensitive keys, recurses into values
    - list / tuple / set: recurses into items
    - str: redacts embedded secrets/tokens
    - All other types: returned as-is

    Args:
        data: The value to sanitize.
        _depth: Internal recursion depth guard (not for external use).

    Returns:
        Sanitized copy of ``data``.
    """
    if _depth > _MAX_SAFE_DEPTH:
        return _REDACTED

    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for k, v in data.items():
            if _is_sensitive_key(k):
                result[k] = _REDACTED
            else:
                result[k] = sanitize_for_log(v, _depth + 1)
        return result

    if isinstance(data, (list, tuple)):
        sanitized = [sanitize_for_log(item, _depth + 1) for item in data]
        return type(data)(sanitized)

    if isinstance(data, set):
        return {sanitize_for_log(item, _depth + 1) for item in data}

    if isinstance(data, str):
        return _sanitize_str_value(data)

    return data


def sanitize_headers(headers: dict[str, str] | Any) -> dict[str, str]:
    """Sanitize HTTP headers for safe logging.

    Always redacts Authorization, Cookie, and any header whose name
    contains a sensitive substring.
    """
    if not isinstance(headers, dict):
        try:
            headers = dict(headers)
        except Exception:
            return {}

    result: dict[str, str] = {}
    for k, v in headers.items():
        norm_k = str(k).lower().replace("-", "_")
        if norm_k in {"authorization", "cookie", "set_cookie", "proxy_authorization"} or any(
            sub in norm_k for sub in ("token", "secret", "api_key", "apikey", "credential", "auth")
        ):
            result[k] = _REDACTED
        else:
            result[k] = str(v)
    return result


def build_safe_log_context(
    *,
    request_id: str | None = None,
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    operation: str | None = None,
    outcome: str | None = None,
    error_code: str | None = None,
    provider: str | None = None,
    latency_ms: float | None = None,
    event_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a PHI-safe structured log context dictionary.

    Only fields explicitly listed here are allowed.
    The ``extra`` dict is sanitized before inclusion.
    """
    ctx: dict[str, Any] = {}
    if request_id is not None:
        ctx["request_id"] = request_id
    if actor_id is not None:
        ctx["actor_id"] = actor_id
    if resource_type is not None:
        ctx["resource_type"] = resource_type
    if resource_id is not None:
        ctx["resource_id"] = resource_id
    if operation is not None:
        ctx["operation"] = operation
    if outcome is not None:
        ctx["outcome"] = outcome
    if error_code is not None:
        ctx["error_code"] = error_code
    if provider is not None:
        ctx["provider"] = provider
    if latency_ms is not None:
        ctx["latency_ms"] = latency_ms
    if event_type is not None:
        ctx["event_type"] = event_type
    if extra:
        ctx["extra"] = sanitize_for_log(extra)
    return ctx

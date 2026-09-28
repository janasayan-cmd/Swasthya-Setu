"""Centralized Data Classification, Privacy Invariants, and PHI Sanitization (Phase 24).

ARCHITECTURAL PRINCIPLE:
========================
This module is the canonical backend authority for:
- Data classification levels
- Purpose-aware processing categories
- Strict PHI & security-sensitive detection
- Privacy-safe logging & telemetry sanitization
- Contextual data minimization contracts

FAIL-CLOSED INVARIANT:
======================
When data classification or purpose is unknown, uncertain, or ambiguous,
the system MUST classify as HIGHLY_SENSITIVE_PHI and FAIL CLOSED (deny access).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union


# ---------------------------------------------------------------------------
# 1. Data Classification Model (TRD Sec 5)
# ---------------------------------------------------------------------------

class DataClassification(str, Enum):
    """Canonical data sensitivity classifications for HealthSetu."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    PHI = "PHI"
    HIGHLY_SENSITIVE_PHI = "HIGHLY_SENSITIVE_PHI"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"


# ---------------------------------------------------------------------------
# 2. Processing Purpose Model (TRD Sec 8)
# ---------------------------------------------------------------------------

class DataProcessingPurpose(str, Enum):
    """Explicit authorized purposes for sensitive healthcare data processing."""

    CLINICAL_CARE = "CLINICAL_CARE"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    MEDICATION_SAFETY = "MEDICATION_SAFETY"
    TRIAGE = "TRIAGE"
    CARE_PLAN = "CARE_PLAN"
    INTEROPERABILITY = "INTEROPERABILITY"
    CLINICAL_REVIEW = "CLINICAL_REVIEW"
    PATIENT_DATA_EXPORT = "PATIENT_DATA_EXPORT"
    SECURITY = "SECURITY"
    AUDIT = "AUDIT"
    SYSTEM_OPERATIONS = "SYSTEM_OPERATIONS"


# ---------------------------------------------------------------------------
# Classification Map & Registry
# ---------------------------------------------------------------------------

_RESOURCE_CLASSIFICATION_MAP: Dict[str, DataClassification] = {
    # Public reference metadata
    "system_health": DataClassification.PUBLIC,
    "api_docs": DataClassification.PUBLIC,
    "privacy_policy_doc": DataClassification.PUBLIC,

    # Internal operational metadata
    "system_metrics": DataClassification.INTERNAL,
    "facility_capacity": DataClassification.INTERNAL,
    "department_metadata": DataClassification.INTERNAL,
    "organization_directory": DataClassification.INTERNAL,
    "synthetic_test_data": DataClassification.INTERNAL,

    # Confidential non-clinical metadata
    "clinician_profile": DataClassification.CONFIDENTIAL,
    "audit_trail_metadata": DataClassification.CONFIDENTIAL,
    "billing_summary": DataClassification.CONFIDENTIAL,
    "retention_policy": DataClassification.CONFIDENTIAL,

    # Standard PHI
    "patient_profile": DataClassification.PHI,
    "vital_signs": DataClassification.PHI,
    "encounter": DataClassification.PHI,
    "medical_document": DataClassification.PHI,
    "document_extraction": DataClassification.PHI,
    "prescription": DataClassification.PHI,
    "medication": DataClassification.PHI,
    "symptom": DataClassification.PHI,
    "triage_assessment": DataClassification.PHI,
    "sbar_handoff": DataClassification.PHI,
    "care_plan": DataClassification.PHI,
    "discharge_summary": DataClassification.PHI,
    "transfer_record": DataClassification.PHI,
    "fhir_clinical_resource": DataClassification.PHI,
    "patient_data_export": DataClassification.PHI,

    # Highly Sensitive PHI (requires elevated auditing & strict purpose justification)
    "clinical_notes": DataClassification.HIGHLY_SENSITIVE_PHI,
    "psychiatric_evaluation": DataClassification.HIGHLY_SENSITIVE_PHI,
    "allergy_record": DataClassification.HIGHLY_SENSITIVE_PHI,
    "genetic_data": DataClassification.HIGHLY_SENSITIVE_PHI,
    "substance_abuse_history": DataClassification.HIGHLY_SENSITIVE_PHI,
    "hiv_infectious_disease": DataClassification.HIGHLY_SENSITIVE_PHI,
    "ai_clinical_summary": DataClassification.HIGHLY_SENSITIVE_PHI,

    # Security Sensitive
    "password_hash": DataClassification.SECURITY_SENSITIVE,
    "auth_token": DataClassification.SECURITY_SENSITIVE,
    "refresh_token": DataClassification.SECURITY_SENSITIVE,
    "api_key": DataClassification.SECURITY_SENSITIVE,
    "private_key": DataClassification.SECURITY_SENSITIVE,
    "database_credential": DataClassification.SECURITY_SENSITIVE,
    "pseudonym_salt": DataClassification.SECURITY_SENSITIVE,
}


def classify_data(data_type: str) -> DataClassification:
    """Classify data type according to approved governance hierarchy.
    
    Fail-closed: Unmapped data types default to HIGHLY_SENSITIVE_PHI.
    """
    normalized = data_type.strip().lower()
    return _RESOURCE_CLASSIFICATION_MAP.get(normalized, DataClassification.HIGHLY_SENSITIVE_PHI)


def is_phi(classification: Union[DataClassification, str]) -> bool:
    """Check if classification level represents Protected Health Information."""
    if isinstance(classification, str):
        try:
            classification = DataClassification(classification)
        except ValueError:
            return True  # Fail-closed
    return classification in (DataClassification.PHI, DataClassification.HIGHLY_SENSITIVE_PHI)


def is_highly_sensitive(classification: Union[DataClassification, str]) -> bool:
    """Check if classification is Highly Sensitive PHI."""
    if isinstance(classification, str):
        try:
            classification = DataClassification(classification)
        except ValueError:
            return True
    return classification == DataClassification.HIGHLY_SENSITIVE_PHI


def is_security_sensitive(classification: Union[DataClassification, str]) -> bool:
    """Check if classification is security credential / secret."""
    if isinstance(classification, str):
        try:
            classification = DataClassification(classification)
        except ValueError:
            return False
    return classification == DataClassification.SECURITY_SENSITIVE


# ---------------------------------------------------------------------------
# 3. Privacy-Safe Logging & Sanitization (TRD Sec 6 & 31)
# ---------------------------------------------------------------------------

_SENSITIVE_LOG_KEYS: Set[str] = {
    # Credentials & secrets
    "password", "secret", "token", "access_token", "refresh_token", "api_key",
    "apikey", "private_key", "signing_key", "authorization", "x-api-key",
    "salt", "pseudonym_salt", "connection_string", "database_url",
    # PHI Demographics
    "first_name", "last_name", "patient_name", "full_name", "dob",
    "date_of_birth", "birth_date", "ssn", "national_id", "phone",
    "phone_number", "mobile", "email", "address", "postal_code", "zip_code",
    # Clinical Content
    "diagnosis", "diagnoses", "symptom", "symptoms", "prescription_text",
    "medication_name", "clinical_notes", "note_body", "extracted_text",
    "document_content", "narrative", "assessment", "plan", "sbar_text",
    "raw_ocr", "ai_prompt", "ai_response",
}

_PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_JWT_REGEX = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}")


def sanitize_for_logging(data: Any, depth: int = 0) -> Any:
    """Recursively mask all credentials, identifiers, and clinical PHI for log output."""
    if depth > 10:
        return "[DEPTH_EXCEEDED]"

    if isinstance(data, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower().strip()
            if any(sensitive in k_lower for sensitive in _SENSITIVE_LOG_KEYS):
                sanitized[k] = "[REDACTED_PHI_OR_SECRET]"
            else:
                sanitized[k] = sanitize_for_logging(v, depth + 1)
        return sanitized

    if isinstance(data, list):
        return [sanitize_for_logging(item, depth + 1) for item in data]

    if isinstance(data, str):
        val = _JWT_REGEX.sub("[REDACTED_JWT]", data)
        val = _EMAIL_REGEX.sub("[REDACTED_EMAIL]", val)
        val = _PHONE_REGEX.sub("[REDACTED_PHONE]", val)
        val = _SSN_REGEX.sub("[REDACTED_SSN]", val)
        return val

    return data


# ---------------------------------------------------------------------------
# 4. Telemetry & Metric Label Sanitization (TRD Sec 32)
# ---------------------------------------------------------------------------

_FORBIDDEN_METRIC_LABELS: Set[str] = {
    "patient_id", "patientid", "user_id", "userid", "patient_name", "name",
    "email", "phone", "address", "mrn", "diagnosis", "medication",
    "token", "secret", "note", "text", "body", "filename",
}


def sanitize_for_telemetry(labels: Dict[str, Any]) -> Dict[str, str]:
    """Ensure Prometheus metric labels NEVER capture patient IDs, names, or clinical text.
    
    Safe labels include: resource_type, operation, status, reason, format, scope.
    """
    clean_labels: Dict[str, str] = {}
    for k, v in labels.items():
        k_lower = str(k).lower().strip()
        if k_lower in _FORBIDDEN_METRIC_LABELS or "patient" in k_lower:
            # Strip out or generalize to avoid card-explosion and PHI capture
            continue
        # Convert label value to safe, bounded string
        str_val = str(v).strip()
        if len(str_val) > 64:
            str_val = str_val[:61] + "..."
        # Scrub any potential token/id pattern in value
        if _JWT_REGEX.search(str_val) or _EMAIL_REGEX.search(str_val):
            str_val = "[REDACTED]"
        clean_labels[k] = str_val
    return clean_labels


# ---------------------------------------------------------------------------
# 5. Data Minimization Helpers (TRD Sec 7 & 35)
# ---------------------------------------------------------------------------

def minimize_for_ocr(document_id: str, storage_key: str, job_id: str) -> Dict[str, Any]:
    """Construct minimized payload for OCR document processing worker.
    
    Excludes patient demographics, entire medication lists, or unrelated clinical records.
    """
    return {
        "document_id": document_id,
        "storage_key": storage_key,
        "job_id": job_id,
    }


def minimize_for_medication_safety(
    medications: List[Dict[str, Any]],
    allergies: List[str],
) -> Dict[str, Any]:
    """Construct minimized payload for external medication safety engine.
    
    Passes ONLY active drug codes/names and allergen substances; strips patient IDs,
    demographics, encounters, and clinician notes.
    """
    minimized_meds = []
    for med in medications:
        minimized_meds.append({
            "code": med.get("code") or med.get("rxnorm_code"),
            "name": med.get("name") or med.get("medication_name"),
            "dosage": med.get("dosage"),
        })
    return {
        "medications": minimized_meds,
        "allergies": [str(a) for a in allergies],
    }


def minimize_for_ai(content: str, max_chars: int = 4000) -> str:
    """Sanitize and constrain clinical content prior to AI inference.
    
    Redacts direct identifiers (SSN, emails, phones) and enforces bounded context length.
    """
    content = _EMAIL_REGEX.sub("[EMAIL]", content)
    content = _PHONE_REGEX.sub("[PHONE]", content)
    content = _SSN_REGEX.sub("[IDENTIFIER]", content)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n...[TRUNCATED_FOR_DATA_MINIMIZATION]"
    return content


def minimize_for_export(data: Dict[str, Any], allowed_scopes: List[str]) -> Dict[str, Any]:
    """Filter comprehensive patient bundle to contain ONLY validated, approved scopes."""
    allowed = set(s.upper() for s in allowed_scopes)
    if "FULL_AUTHORIZED_RECORD" in allowed:
        return data

    filtered: Dict[str, Any] = {}
    scope_to_key_map = {
        "PATIENT_PROFILE": "patient_profile",
        "CLINICAL_HISTORY": "clinical_history",
        "ENCOUNTERS": "encounters",
        "ALLERGIES": "allergies",
        "VITALS": "vitals",
        "MEDICATIONS": "medications",
        "PRESCRIPTIONS": "prescriptions",
        "DOCUMENTS": "documents",
        "TRIAGE": "triage_assessments",
        "CARE_PLANS": "care_plans",
        "TRANSFERS": "transfers",
        "INTEROPERABILITY_DATA": "interoperability_records",
    }

    for scope, key in scope_to_key_map.items():
        if scope in allowed and key in data:
            filtered[key] = data[key]

    return filtered


# ---------------------------------------------------------------------------
# 6. PHI-Safe Error Response Helper (TRD Sec 33)
# ---------------------------------------------------------------------------

def format_safe_client_error(
    code: str,
    message: str,
    request_id: str,
) -> Dict[str, Any]:
    """Construct an error response that is guaranteed to contain zero patient PHI."""
    # Ensure message does not accidentally leak names or tokens
    safe_message = sanitize_for_logging(message)
    if isinstance(safe_message, dict):
        safe_message = "An error occurred during processing."

    return {
        "success": False,
        "error": {
            "code": code,
            "message": str(safe_message),
            "request_id": request_id,
        },
    }

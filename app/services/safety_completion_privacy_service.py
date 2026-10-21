"""Phase 65: Safety Completion Privacy & Authorization Service.

Enforces tenant scoping, facility scoping, role authorization, and PHI sanitization.
"""

import re
from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

_PHI_SENSITIVE_KEYS = {
    "patient_name", "first_name", "last_name", "phone", "email",
    "address", "aadhaar", "ssn", "mrn", "dob", "birth_date",
    "clinical_notes", "narrative", "diagnosis", "transcription",
}


class SafetyCompletionPrivacyService:
    """Enforces multi-tenant isolation, role checks, and PHI data hygiene."""

    @staticmethod
    def validate_caller_access(
        user: AuthenticatedUserContext,
        target_organization_id: str,
        target_facility_id: Optional[str] = None,
    ) -> None:
        """Validate multi-tenant boundaries."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Patient role is not permitted to access clinical safety completion governance workflows.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if user.organization_id != target_organization_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Cross-tenant access forbidden. Tenant mismatch.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if target_facility_id and user.facility_id and user.facility_id != target_facility_id:
            # If user has a specific facility assigned, enforce match
            if user.role != UserRole.ADMIN:
                raise AppException(
                    code=ErrorCode.ACCESS_DENIED,
                    message="Cross-facility access forbidden. Facility mismatch.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

    @staticmethod
    def sanitize_phi(data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip or mask direct identifiers and sensitive clinical narrative free-text."""
        sanitized: Dict[str, Any] = {}
        for key, val in data.items():
            lower_k = key.lower()
            if any(phi_k in lower_k for phi_k in _PHI_SENSITIVE_KEYS):
                sanitized[key] = "[REDACTED_PHI]"
            elif isinstance(val, dict):
                sanitized[key] = SafetyCompletionPrivacyService.sanitize_phi(val)
            elif isinstance(val, list):
                sanitized[key] = [
                    SafetyCompletionPrivacyService.sanitize_phi(item) if isinstance(item, dict) else item
                    for item in val
                ]
            else:
                sanitized[key] = val
        return sanitized

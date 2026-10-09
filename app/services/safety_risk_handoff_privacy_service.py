"""Phase 64: Clinical Safety Risk Handoff Privacy Service.

Enforces multi-tenant isolation, data minimization, PHI protection,
and authorized clinical access purpose validation for handoffs.
"""

from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.user import AuthenticatedUserContext


class SafetyRiskHandoffPrivacyService:
    """Enforces tenant boundaries, data minimization, and privacy rules."""

    SENSITIVE_KEYS = {
        "ssn", "patient_name", "phone", "email", "address", "mrn_raw",
        "dob", "patient_identifier", "raw_phi", "biometric_id",
    }

    VALID_PURPOSES = {
        "GOVERNED_ACTION_HANDOFF",
        "SAFETY_SURVEILLANCE_HANDOFF",
        "INCIDENT_ESCALATION",
        "DISPOSITION_EXECUTION",
        "CLINICAL_SAFETY_AUDIT",
        "RECONCILIATION_VERIFICATION",
    }

    @classmethod
    def validate_tenant_access(
        cls,
        user: AuthenticatedUserContext,
        organization_id: str,
        facility_id: Optional[str] = None,
    ) -> None:
        """Enforce strict organization and facility multi-tenant isolation."""
        if not user or not user.organization_id:
            raise AppException(
                code=ErrorCode.UNAUTHORIZED,
                message="User lacks valid organization identity context.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        if user.organization_id != organization_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Access denied across organization boundary: requested '{organization_id}', user belongs to '{user.organization_id}'.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if facility_id and user.facility_id and user.facility_id != facility_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Access denied across facility boundary: requested '{facility_id}', user assigned to '{user.facility_id}'.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    @classmethod
    def validate_purpose(cls, purpose: Optional[str]) -> None:
        """Verify legitimate clinical safety or governance handoff purpose."""
        if not purpose or purpose.upper() not in cls.VALID_PURPOSES:
            raise AppException(
                code=ErrorCode.PRIVACY_RESTRICTED,
                message=f"Invalid or unauthorized handoff purpose: '{purpose}'.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    @classmethod
    def sanitize_payload(cls, data: Any) -> Any:
        """Recursively redact direct patient identifiers and raw PHI from metadata."""
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if any(sens in k.lower() for sens in cls.SENSITIVE_KEYS):
                    cleaned[k] = "[REDACTED_PHI]"
                else:
                    cleaned[k] = cls.sanitize_payload(v)
            return cleaned
        elif isinstance(data, list):
            return [cls.sanitize_payload(item) for item in data]
        return data

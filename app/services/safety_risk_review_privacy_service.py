"""Phase 63: Clinical Safety Risk Review Privacy Service.

Enforces tenant scoping, minimum-necessary data filtering, PHI sanitization,
and purpose validation. Fails closed on any privacy boundary violation.
"""

from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.user import AuthenticatedUserContext


class SafetyRiskReviewPrivacyService:
    """Enforces tenant isolation, data minimization, and PHI protection for Phase 63."""

    SENSITIVE_KEYS = {
        "ssn", "patient_name", "phone", "email", "address", "mrn_raw", "dob",
        "patient_identifier", "raw_phi", "biometric_id"
    }

    @classmethod
    def validate_tenant_access(
        cls,
        user: AuthenticatedUserContext,
        organization_id: str,
        facility_id: Optional[str] = None,
    ) -> None:
        """Validate organization and facility multi-tenant boundaries."""
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
        """Validate legitimate clinical safety surveillance or risk governance purpose."""
        valid_purposes = {
            "GOVERNED_RISK_REVIEW",
            "CROSS_DOMAIN_RISK_CONSOLIDATION",
            "SAFETY_SURVEILLANCE",
            "RISK_GOVERNANCE",
            "INCIDENT_PREVENTION",
            "CLINICAL_SAFETY_AUDIT",
            "CLINICAL_SAFETY_GOVERNANCE",
        }
        if not purpose or purpose.upper() not in valid_purposes:
            raise AppException(
                code=ErrorCode.PRIVACY_RESTRICTED,
                message=f"Invalid or unauthorized clinical access purpose: '{purpose}'.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    @classmethod
    def sanitize_payload(cls, data: Any) -> Any:
        """Recursively redact sensitive patient identifiers and direct PHI."""
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

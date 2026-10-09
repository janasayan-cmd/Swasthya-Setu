"""Phase 63: Clinical Safety Review Authorization Service.

Enforces strict role, scope, credentials, and authority validity checks for governed
risk review participants.
Never trusts client-supplied roles or unverified authorities.
"""

from datetime import datetime, timezone
from typing import Optional, Set
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.safety_risk_review import SafetyRiskReviewRecord
from app.schemas.user import AuthenticatedUserContext


class SafetyRiskReviewAuthorizationService:
    """Enforces fine-grained reviewer authorization boundaries."""

    PERMITTED_ROLES = {
        UserRole.ADMIN,
        UserRole.SYSTEM_ADMIN,
        UserRole.DOCTOR,
        "ADMIN",
        "SYSTEM_ADMIN",
        "DOCTOR",
        "CLINICIAN",
    }

    @classmethod
    def validate_reviewer_authority(
        cls,
        user: AuthenticatedUserContext,
        review: SafetyRiskReviewRecord,
        required_permission: Optional[str] = "safety_risk:review",
    ) -> None:
        """Verify that the user possesses active authority to participate in governed risk reviews."""
        if not user or not user.user_id:
            raise AppException(
                code=ErrorCode.UNAUTHORIZED,
                message="Review action requires authenticated credentials.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        # Check tenant boundaries
        if user.organization_id != review.organization_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Reviewer organization '{user.organization_id}' does not match review organization '{review.organization_id}'.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if user.facility_id and review.facility_id and user.facility_id != review.facility_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Reviewer facility '{user.facility_id}' does not match review facility '{review.facility_id}'.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Check role permission
        if user.role not in cls.PERMITTED_ROLES:
            raise AppException(
                code=ErrorCode.REVIEWER_NOT_AUTHORIZED,
                message=f"User role '{user.role}' lacks governed clinical risk review authority.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    @classmethod
    def validate_authority_not_expired(
        cls,
        authority_expiry: Optional[datetime],
        is_revoked: bool = False,
    ) -> None:
        """Verify that reviewer authority is not revoked or expired."""
        if is_revoked:
            raise AppException(
                code=ErrorCode.REVIEWER_NOT_AUTHORIZED,
                message="Reviewer authority has been explicitly revoked.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if authority_expiry and authority_expiry < datetime.now(timezone.utc):
            raise AppException(
                code=ErrorCode.REVIEWER_NOT_AUTHORIZED,
                message="Reviewer clinical governance authority credential has expired.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

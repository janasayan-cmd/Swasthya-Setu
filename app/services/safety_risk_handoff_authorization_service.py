"""Phase 64: Clinical Safety Risk Handoff Authorization Service.

Enforces role, permission, and authority validity checks for governed handoff operations.
"""

from datetime import datetime, timezone
from typing import Optional, Set
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext


class SafetyRiskHandoffAuthorizationService:
    """Enforces fine-grained reviewer and operational authority boundaries."""

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
    def validate_actor_authority(
        cls,
        user: AuthenticatedUserContext,
        required_permission: Optional[str] = "safety_risk:handoff",
    ) -> None:
        """Verify that the actor possesses active clinical/governance authority."""
        if not user or not user.user_id:
            raise AppException(
                code=ErrorCode.UNAUTHORIZED,
                message="Handoff action requires authenticated credentials.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        if user.role not in cls.PERMITTED_ROLES:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"User role '{user.role}' lacks governed clinical risk handoff authority.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

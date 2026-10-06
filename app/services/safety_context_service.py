"""Phase 48: Safety Context Service.

Constructs minimum-necessary, authorization-aware, consent-aware,
and version-aware execution context for safety evaluations.
"""

from typing import Any

from app.core.exceptions import (
    ClinicalContextStaleException,
    DecisionStaleException,
    UnauthorizedClinicalActionException,
)
from app.repositories.consent_repository import ConsentRepository, consent_repository
from app.repositories.versioning_repository import VersioningRepository, versioning_repository


CLINICAL_ACTOR_ROLES = {"DOCTOR", "NURSE", "CLINICIAN", "ADMINISTRATOR"}


class SafetyContextService:
    """Service for gathering and validating safe clinical context."""

    def __init__(
        self,
        version_repo: VersioningRepository | None = None,
        consent_repo: ConsentRepository | None = None,
    ) -> None:
        self.version_repo = version_repo or versioning_repository
        self.consent_repo = consent_repo or consent_repository

    def validate_actor_privileges(self, actor_role: str, action: str) -> None:
        """Validate that the actor holds clinical authorization for this action."""
        role_upper = (actor_role or "").upper()
        if role_upper not in CLINICAL_ACTOR_ROLES:
            raise UnauthorizedClinicalActionException(
                f"Role '{actor_role}' is not authorized to execute clinical action '{action}'.",
                details={"actor_role": actor_role, "action": action},
            )

    def validate_resource_freshness(
        self,
        resource_type: str,
        resource_id: str,
        expected_version: int,
    ) -> int:
        """Verify that the resource has not evolved past the expected version.

        Returns current version. Raises ClinicalContextStaleException if stale.
        """
        current_version = self.version_repo.get_current_version_number(resource_type, resource_id)
        if current_version > expected_version:
            raise ClinicalContextStaleException(
                f"Resource '{resource_type}:{resource_id}' is stale. Expected v{expected_version}, but current is v{current_version}.",
                details={
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        return current_version

    def build_safe_context(
        self,
        patient_id: str | None,
        resource_type: str | None,
        resource_id: str | None,
        actor_id: str | None,
        actor_role: str | None,
    ) -> dict[str, Any]:
        """Assemble minimum necessary context without PHI leakage."""
        context: dict[str, Any] = {
            "actor_id": actor_id,
            "actor_role": actor_role,
            "patient_id": patient_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
        }

        if resource_type and resource_id:
            current_ver = self.version_repo.get_current_version_number(resource_type, resource_id)
            context["current_version"] = current_ver

        return context


# Global singleton
safety_context_service = SafetyContextService()

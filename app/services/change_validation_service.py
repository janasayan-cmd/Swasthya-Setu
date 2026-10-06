"""Change Validation Service (Phase 46).

Enforces:
- Clinical justification requirements
- AI safety boundaries (AI cannot create authoritative versions or modify records autonomously)
- Autonomous clinical practice prohibitions (versioning cannot diagnose, prescribe, or triage)
- Permissible state transitions and historical immutability
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.exceptions import (
    AIVersioningAuthorityProhibitedException,
    ChangeReasonRequiredException,
    HistoricalResourceReadOnlyException,
    InvalidStateTransitionException,
    VersioningAutonomousClinicalProhibitedException,
)
from app.schemas.versioning import ClinicalVersionRecord, VersionType

logger = logging.getLogger(__name__)


class ChangeValidationService:
    """Validates clinical record mutation intent, actor authority, and safety boundaries."""

    @staticmethod
    def validate_change_reason(reason: Optional[str]) -> None:
        """Validate that a valid clinical change reason is provided if required."""
        if getattr(settings, "VERSIONING_REQUIRE_CHANGE_REASON", True):
            if not reason or not reason.strip() or len(reason.strip()) < 3:
                raise ChangeReasonRequiredException(
                    "A valid clinical change reason (minimum 3 characters) is required for this modification."
                )

    @staticmethod
    def validate_actor_ai_boundary(actor_role: str, actor_type: str, action: str = "MODIFY") -> None:
        """Enforce strict AI boundary: AI agents cannot autonomously author or modify clinical records."""
        normalized_role = (actor_role or "").upper()
        normalized_type = (actor_type or "").upper()

        ai_identifiers = {"AI", "AI_AGENT", "BOT", "SYSTEM_AI", "AUTOMATION_AI", "LLM"}

        if normalized_role in ai_identifiers or normalized_type in ai_identifiers:
            logger.warning(
                "Blocked autonomous AI attempt to perform '%s' on clinical version record. Role: %s, Type: %s",
                action,
                actor_role,
                actor_type,
            )
            raise AIVersioningAuthorityProhibitedException(
                f"Autonomous AI agent ({actor_role}) is prohibited from executing authoritative clinical record '{action}'. "
                "AI outputs must be reviewed and submitted by an authorized human clinician."
            )

    @staticmethod
    def validate_clinical_safety_actions(
        resource_type: str,
        changes: Dict[str, Any],
        actor_role: str,
    ) -> None:
        """Ensure versioning engine is not used to autonomously diagnose, prescribe, or alter medication."""
        normalized_type = (resource_type or "").lower()
        normalized_role = (actor_role or "").upper()

        # If resource is prescription or medication or diagnosis, verify clinician presence
        clinical_restricted_types = {"prescription", "medication", "condition", "diagnosis"}
        non_clinician_roles = {"SYSTEM", "GUEST", "PATIENT", "EXTERNAL_API", "UNVERIFIED_SOURCE"}

        if normalized_type in clinical_restricted_types and normalized_role in non_clinician_roles:
            if normalized_type in {"prescription", "medication", "diagnosis", "condition"}:
                raise VersioningAutonomousClinicalProhibitedException(
                    f"Non-clinicians ({actor_role}) cannot autonomously prescribe, diagnose, or alter clinical records on {resource_type}."
                )

    @staticmethod
    def validate_state_transition(
        current_record: ClinicalVersionRecord,
        target_version_type: VersionType,
    ) -> None:
        """Validate that current record allows transition to target version type."""
        # Invariant: If record is soft-deleted, it can only transition via RESTORED
        if current_record.is_deleted and target_version_type != VersionType.RESTORED:
            raise InvalidStateTransitionException(
                f"Cannot perform {target_version_type.value} on deleted resource {current_record.resource_id}. "
                "Only RESTORED is permissible on soft-deleted clinical records."
            )

        # Invariant: Historical records cannot be directly edited
        if not current_record.is_current:
            raise HistoricalResourceReadOnlyException(
                f"Version {current_record.version_number} of {current_record.resource_id} is historical and read-only. "
                "Mutations must target the current active version."
            )


change_validation_service = ChangeValidationService()

"""Phase 51: Safety Change Validation Service.

Enforces post-implementation validation gating and the foundational principle:
TECHNICAL SUCCESS != CLINICAL SAFETY PROOF.
Validates automated and human safety evidence before permitting rollout.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import (
    SafetyChangeInvalidStateException,
    SafetyChangeNotFoundException,
    SafetyChangeValidationFailedException,
    SafetyChangeValidationRequiredException,
    SafetyChangeVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.safety_change import SafetyChangeRecord
from app.schemas.safety_governance import ChangeRequestState
from app.schemas.safety_validation import (
    SafetyChangeValidationRecord,
    SafetyChangeValidationRequest,
    ValidationOutcome,
)
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.safety_change_validation_service")


class SafetyChangeValidationService:
    """Service governing empirical clinical safety validation after change implementation."""

    def __init__(
        self,
        repository: Optional[SafetyGovernanceRepository] = None,
        policy_service: Optional[SafetyGovernancePolicyService] = None,
        audit_svc: Optional[AuditService] = None,
        metrics_svc: Optional[SafetyGovernanceMetricsService] = None,
    ) -> None:
        self.repository = repository or safety_governance_repository
        self.policy_service = policy_service or safety_governance_policy_service
        self.audit_service = audit_svc or audit_service
        self.metrics_service = metrics_svc or safety_governance_metrics_service

    async def validate_change(
        self,
        change_id: str,
        request: SafetyChangeValidationRequest,
        validator_id: str,
        validator_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SafetyChangeValidationRecord:
        """Record validation evidence and verify clinical safety efficacy."""
        # 1. Human Authority validation (AI cannot approve safety validation)
        self.policy_service.assert_human_safety_authority(validator_id, validator_role, "validate_change")

        # 2. Retrieve change & validate
        change = self.repository.get_change(change_id)
        if not change:
            raise SafetyChangeNotFoundException(f"Safety change request '{change_id}' not found.")
        self.policy_service.validate_org_boundary(change.organization_id, organization_id, "safety_change")

        if change.state not in (ChangeRequestState.VALIDATION_REQUIRED, ChangeRequestState.IMPLEMENTING):
            raise SafetyChangeInvalidStateException(
                f"Safety change '{change_id}' is in state '{change.state.value}'. "
                "Validation is only permitted for implemented changes."
            )

        # 3. Concurrency check
        if request.expected_change_version is not None and change.version != request.expected_change_version:
            raise SafetyChangeVersionConflictException(
                f"Version mismatch during validation: expected {request.expected_change_version}, current {change.version}."
            )

        now = datetime.now(timezone.utc)
        validation_record = SafetyChangeValidationRecord(
            change_id=change.id,
            outcome=request.outcome,
            validator_id=validator_id,
            validator_role=validator_role,
            validation_evidence=request.validation_evidence,
            findings_summary=request.findings_summary,
            notes=request.notes,
            validated_at=now,
        )

        persisted_val = self.repository.save_validation(validation_record)
        change.latest_validation_id = persisted_val.id

        if request.outcome == ValidationOutcome.VALIDATED:
            change.validated_version = change.implemented_version
            change.state = ChangeRequestState.VALIDATED
            change.version += 1
            change.updated_at = now
            self.repository.save_change(change)

            if self.audit_service:
                try:
                    await self.audit_service.record(
                        event_type=AuditEventType.SAFETY_CHANGE_VALIDATED,
                        outcome="ALLOW",
                        actor_id=validator_id,
                        action="safety_governance:change:validate",
                        resource_type="safety_change",
                        resource_id=change.id,
                        metadata={"validated_version": change.validated_version},
                        request_id=request_id,
                    )
                except Exception as ex:
                    logger.warning("Audit record failed for validation: %s", ex)

            return persisted_val

        else:
            # Failure handling (Section 59)
            change.state = ChangeRequestState.FAILED
            change.version += 1
            change.updated_at = now
            self.repository.save_change(change)
            self.metrics_service.increment("validation_failure_count")

            if self.audit_service:
                try:
                    await self.audit_service.record(
                        event_type=AuditEventType.SAFETY_CHANGE_FAILED,
                        outcome="DENY",
                        actor_id=validator_id,
                        action="safety_governance:change:validate_failed",
                        resource_type="safety_change",
                        resource_id=change.id,
                        metadata={"failure_reason": request.findings_summary},
                        request_id=request_id,
                    )
                except Exception as ex:
                    logger.warning("Audit record failed for validation failure: %s", ex)

            raise SafetyChangeValidationFailedException(
                f"Safety change '{change_id}' failed clinical validation: {request.findings_summary}. "
                "Rollback or remediation required."
            )

    def list_validations(self, change_id: str) -> List[SafetyChangeValidationRecord]:
        """List all validation records for a change."""
        return self.repository.list_validations(change_id)


# Global singleton safety change validation service
safety_change_validation_service = SafetyChangeValidationService()

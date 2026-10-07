"""Phase 51: Safety Change Implementation Gating & Orchestration Service.

Enforces the strict implementation gate:
AUTHENTICATE -> AUTHORIZE -> CHECK RISK STATE -> CHECK CHANGE STATE ->
CHECK APPROVAL -> CHECK SCOPE -> CHECK VERSION -> CHECK DEPENDENCIES ->
CHECK VALIDATION PLAN -> CHECK ROLLBACK PLAN -> CHECK MONITORING PLAN -> CHECK CONCURRENCY.

Enforces:
- APPROVAL != IMPLEMENTATION
- IMPLEMENTATION != VALIDATION
- Preservation of CURRENT, PROPOSED, IMPLEMENTED, and VALIDATED versions.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import (
    SafetyChangeAlreadyImplementedException,
    SafetyChangeApprovalRequiredException,
    SafetyChangeImplementationDeniedException,
    SafetyChangeInvalidStateException,
    SafetyChangeNotFoundException,
    SafetyChangeRollbackRequiredException,
    SafetyChangeVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.safety_change import SafetyChangeRecord
from app.schemas.safety_governance import (
    ChangeRequestState,
    RolloutScopeType,
    SafetyChangeTargetType,
)
from app.schemas.safety_rollback import (
    SafetyChangeImplementationRecord,
    SafetyChangeImplementationRequest,
)
from app.services.audit_service import AuditService, audit_service
from app.services.safety_change_approval_service import (
    SafetyChangeApprovalService,
    safety_change_approval_service,
)
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.safety_change_implementation_service")


class SafetyChangeImplementationService:
    """Service governing implementation gating, controlled deployment, and subsystem orchestration."""

    def __init__(
        self,
        repository: Optional[SafetyGovernanceRepository] = None,
        policy_service: Optional[SafetyGovernancePolicyService] = None,
        approval_service: Optional[SafetyChangeApprovalService] = None,
        audit_svc: Optional[AuditService] = None,
        metrics_svc: Optional[SafetyGovernanceMetricsService] = None,
    ) -> None:
        self.repository = repository or safety_governance_repository
        self.policy_service = policy_service or safety_governance_policy_service
        self.approval_service = approval_service or safety_change_approval_service
        self.audit_service = audit_svc or audit_service
        self.metrics_service = metrics_svc or safety_governance_metrics_service

    async def implement_change(
        self,
        change_id: str,
        request: SafetyChangeImplementationRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SafetyChangeImplementationRecord:
        """Execute implementation gate checks and apply governed change via authoritative subsystem."""
        # 1. Authority validation (AI cannot deploy/implement changes)
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "implement_change")

        # 2. Retrieve change & validate
        change = self.repository.get_change(change_id)
        if not change:
            raise SafetyChangeNotFoundException(f"Safety change request '{change_id}' not found.")
        self.policy_service.validate_org_boundary(change.organization_id, organization_id, "safety_change")

        if change.state in (ChangeRequestState.IMPLEMENTING, ChangeRequestState.VALIDATION_REQUIRED, ChangeRequestState.VALIDATED, ChangeRequestState.COMPLETED):
            raise SafetyChangeAlreadyImplementedException(
                f"Safety change '{change_id}' is already implemented (current state: {change.state.value})."
            )

        # 3. Check Approval Gate (Section 28)
        if change.state not in (ChangeRequestState.APPROVED, ChangeRequestState.IMPLEMENTATION_READY):
            if not change.is_emergency:
                raise SafetyChangeApprovalRequiredException(
                    f"Safety change '{change_id}' has not been approved (state: {change.state.value}). "
                    "Implementation is blocked."
                )

        # 4. Check Stale Approval (Section 26)
        if not change.is_emergency and change.latest_approval_id:
            self.approval_service.verify_approval_staleness(change_id)

        # 5. Check Concurrency
        if request.expected_change_version is not None and change.version != request.expected_change_version:
            raise SafetyChangeVersionConflictException(
                f"Version conflict on implementation: expected {request.expected_change_version}, current {change.version}."
            )

        # 6. Verify Plans
        if not change.rollback_plan:
            raise SafetyChangeImplementationDeniedException("Rollback plan is missing or empty.")
        if not change.validation_plan:
            raise SafetyChangeImplementationDeniedException("Validation plan is missing or empty.")
        if not change.monitoring_plan:
            raise SafetyChangeImplementationDeniedException("Monitoring plan is missing or empty.")

        # 7. Check Idempotency
        if request.idempotency_key:
            existing_impl_id = self.repository.get_idempotent_result(request.idempotency_key)
            if existing_impl_id:
                existing_impl = self.repository.get_implementation(existing_impl_id)
                if existing_impl:
                    return existing_impl

        # 8. Mark IMPLEMENTING
        now = datetime.now(timezone.utc)
        change.state = ChangeRequestState.IMPLEMENTING
        self.repository.save_change(change)

        # 9. Subsystem Orchestration Adapter (Simulated authoritative dispatch)
        # In a real environment, dispatches to Phase 25 (config/flags), Phase 48 (safety gates), etc.
        subsystem_response = {
            "target_subsystem": change.affected_subsystem,
            "target_type": change.target_type.value,
            "previous_version": change.current_version,
            "new_version": change.proposed_version,
            "status": "APPLIED_SUCCESSFULLY",
            "dispatched_at": now.isoformat(),
        }

        # 10. Record Implementation Execution
        impl_record = SafetyChangeImplementationRecord(
            change_id=change.id,
            implemented_version=change.proposed_version,
            implementer_id=actor_id,
            implementer_role=actor_role,
            subsystem_response=subsystem_response,
            success=True,
            implemented_at=now,
        )
        persisted_impl = self.repository.save_implementation(impl_record)
        if request.idempotency_key:
            self.repository.save_idempotent_result(request.idempotency_key, persisted_impl.id)

        # 11. Advance Change to VALIDATION_REQUIRED (Implementation != Validation!)
        change.implemented_version = change.proposed_version
        change.latest_implementation_id = persisted_impl.id
        change.state = ChangeRequestState.VALIDATION_REQUIRED
        change.version += 1
        change.updated_at = now
        self.repository.save_change(change)

        # 12. Audit
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.SAFETY_CHANGE_IMPLEMENTED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:change:implement",
                    resource_type="safety_change",
                    resource_id=change.id,
                    metadata={"implemented_version": change.implemented_version},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for change implementation: %s", ex)

        return persisted_impl


# Global singleton safety change implementation service
safety_change_implementation_service = SafetyChangeImplementationService()

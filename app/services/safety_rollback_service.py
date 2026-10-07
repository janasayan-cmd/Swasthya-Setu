"""Phase 51: Safety Change Rollback & Reversion Service.

Enforces:
- Authorized and version-aware safety rollbacks
- Rollback Safety Principles (Section 32):
  - Rollback NEVER deletes change history
  - Rollback NEVER rewrites audit history
  - Rollback NEVER modifies incident history
  - Rollback NEVER hides implementation failures
  - Rollback NEVER automatically closes risk or incidents
- Rollback is treated as a new, auditable, governed action.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import (
    SafetyChangeAlreadyRolledBackException,
    SafetyChangeInvalidStateException,
    SafetyChangeNotFoundException,
    SafetyChangeRollbackDeniedException,
    SafetyChangeVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.safety_change import SafetyChangeRecord
from app.schemas.safety_governance import ChangeRequestState
from app.schemas.safety_rollback import (
    SafetyChangeRollbackRecord,
    SafetyChangeRollbackRequest,
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

logger = logging.getLogger("app.safety_rollback_service")


class SafetyRollbackService:
    """Service governing controlled rollbacks, reversion to verified baselines, and history preservation."""

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

    async def rollback_change(
        self,
        change_id: str,
        request: SafetyChangeRollbackRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SafetyChangeRollbackRecord:
        """Execute a controlled rollback to restore a known stable safety state without history deletion."""
        # 1. Authority validation (AI cannot initiate rollbacks)
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "rollback_change")

        # 2. Retrieve change & validate
        change = self.repository.get_change(change_id)
        if not change:
            raise SafetyChangeNotFoundException(f"Safety change request '{change_id}' not found.")
        self.policy_service.validate_org_boundary(change.organization_id, organization_id, "safety_change")

        if change.state == ChangeRequestState.ROLLED_BACK:
            raise SafetyChangeAlreadyRolledBackException(
                f"Safety change '{change_id}' has already been rolled back."
            )

        # Only implemented, validating, failed, or completed changes can be rolled back
        if change.state not in (
            ChangeRequestState.IMPLEMENTING,
            ChangeRequestState.VALIDATION_REQUIRED,
            ChangeRequestState.VALIDATED,
            ChangeRequestState.FAILED,
            ChangeRequestState.ROLLOUT_APPROVED,
            ChangeRequestState.MONITORING,
            ChangeRequestState.COMPLETED,
        ):
            raise SafetyChangeInvalidStateException(
                f"Cannot rollback change '{change_id}' from state '{change.state.value}'. "
                "Rollback is only valid for implemented changes."
            )

        # 3. Concurrency check
        if request.expected_change_version is not None and change.version != request.expected_change_version:
            raise SafetyChangeVersionConflictException(
                f"Version conflict during rollback: expected {request.expected_change_version}, current {change.version}."
            )

        # 4. Check Idempotency
        if request.idempotency_key:
            existing_rbk_id = self.repository.get_idempotent_result(request.idempotency_key)
            if existing_rbk_id:
                existing_rbk = self.repository.get_rollback(existing_rbk_id)
                if existing_rbk:
                    return existing_rbk

        # 5. Execute Subsystem Reversion (Simulated Authoritative Dispatch)
        now = datetime.now(timezone.utc)
        subsystem_response = {
            "target_subsystem": change.affected_subsystem,
            "reverted_from_version": change.implemented_version,
            "reverted_to_version": request.target_reversion_version,
            "status": "ROLLBACK_SUCCESSFUL",
            "executed_at": now.isoformat(),
        }

        # 6. Record Rollback
        rollback_record = SafetyChangeRollbackRecord(
            change_id=change.id,
            reason=request.reason,
            rollback_scope=request.rollback_scope,
            target_reversion_version=request.target_reversion_version,
            rolled_back_by_id=actor_id,
            rolled_back_by_role=actor_role,
            history_preserved=True,  # Rollback never deletes history!
            subsystem_response=subsystem_response,
            rolled_back_at=now,
        )

        persisted_rbk = self.repository.save_rollback(rollback_record)
        if request.idempotency_key:
            self.repository.save_idempotent_result(request.idempotency_key, persisted_rbk.id)

        # 7. Update Change Record
        change.latest_rollback_id = persisted_rbk.id
        change.state = ChangeRequestState.ROLLED_BACK
        change.implemented_version = request.target_reversion_version
        change.version += 1
        change.updated_at = now
        self.repository.save_change(change)

        # 8. Telemetry & Audit
        self.metrics_service.increment("rollback_count")
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.SAFETY_ROLLBACK_COMPLETED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:change:rollback",
                    resource_type="safety_change",
                    resource_id=change.id,
                    metadata={"target_reversion_version": request.target_reversion_version, "reason": request.reason},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for rollback: %s", ex)

        return persisted_rbk

    def list_rollbacks(self, change_id: str) -> List[SafetyChangeRollbackRecord]:
        """List all rollback events for a safety change."""
        return self.repository.list_rollbacks(change_id)


# Global singleton safety rollback service
safety_rollback_service = SafetyRollbackService()

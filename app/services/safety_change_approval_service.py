"""Phase 51: Safety Change Approval & Stale-Binding Service.

Enforces:
- Explicit, authorized, and version-bound approvals
- Separation of duties (author cannot approve own change)
- Mandatory impact assessment before approval
- Rejection of AI autonomous approvals
- Stale-approval detection and invalidation upon upstream version shifts
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import time

from app.core.exceptions import (
    SafetyChangeApprovalDeniedException,
    SafetyChangeInvalidStateException,
    SafetyChangeNotFoundException,
    SafetyChangeStaleException,
    SafetyChangeVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.safety_approval import (
    SafetyChangeApprovalRecord,
    SafetyChangeApprovalRequest,
)
from app.schemas.safety_change import SafetyChangeRecord
from app.schemas.safety_governance import ChangeRequestState
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.safety_change_approval_service")


class SafetyChangeApprovalService:
    """Service governing formal safety change authorization and staleness validation."""

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

    async def approve_change(
        self,
        change_id: str,
        request: SafetyChangeApprovalRequest,
        approver_id: str,
        approver_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SafetyChangeApprovalRecord:
        """Formally approve, reject, or defer a safety change request."""
        # 1. Authority validation (AI cannot approve changes)
        self.policy_service.assert_human_safety_authority(approver_id, approver_role, "approve_change")

        # 2. Retrieve change & validate
        change = self.repository.get_change(change_id)
        if not change:
            raise SafetyChangeNotFoundException(f"Safety change request '{change_id}' not found.")
        self.policy_service.validate_org_boundary(change.organization_id, organization_id, "safety_change")

        # 3. Retrieve parent risk
        risk = self.repository.get_risk(change.risk_id)
        if not risk:
            raise SafetyChangeNotFoundException(f"Parent risk for change '{change_id}' not found.")

        # 4. Enforce Separation of Duties
        self.policy_service.validate_separation_of_duties(
            creator_id=change.created_by_id,
            approver_id=approver_id,
            operation_name="approve",
        )

        # 5. Enforce Impact Assessment prerequisite (Section 24)
        if not change.impact_assessment:
            raise SafetyChangeApprovalDeniedException(
                f"Safety change '{change_id}' cannot be approved without a completed impact assessment."
            )

        # 6. Check Version Binding (Section 26)
        if request.bound_change_version != change.version:
            raise SafetyChangeVersionConflictException(
                f"Approval bound to change version {request.bound_change_version}, but change is at version {change.version}."
            )
        if request.bound_risk_version != risk.version:
            raise SafetyChangeVersionConflictException(
                f"Approval bound to risk version {request.bound_risk_version}, but risk is at version {risk.version}."
            )

        # 7. Evaluate decision
        decision_upper = request.decision.upper()
        now = datetime.now(timezone.utc)

        approval = SafetyChangeApprovalRecord(
            change_id=change.id,
            decision=decision_upper,
            approver_id=approver_id,
            approver_role=approver_role,
            bound_risk_version=risk.version,
            bound_change_version=change.version,
            bound_evidence_hash=request.bound_evidence_hash,
            approval_scope=request.approval_scope,
            scope_details=request.scope_details,
            notes=request.notes,
            is_stale=False,
            approved_at=now,
        )

        persisted_approval = self.repository.save_approval(approval)
        change.latest_approval_id = persisted_approval.id

        if decision_upper == "APPROVE":
            change.state = ChangeRequestState.APPROVED
            change.implementation_scope = request.approval_scope
            event_type = AuditEventType.SAFETY_CHANGE_APPROVED
            self.metrics_service.increment("change_approved_count")
        elif decision_upper == "REJECT":
            change.state = ChangeRequestState.REJECTED
            event_type = AuditEventType.SAFETY_CHANGE_REJECTED
        else:
            change.state = ChangeRequestState.DEFERRED
            event_type = AuditEventType.SAFETY_CHANGE_REJECTED

        change.version += 1
        change.updated_at = now
        self.repository.save_change(change)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=event_type,
                    outcome="ALLOW",
                    actor_id=approver_id,
                    action=f"safety_governance:change:{decision_upper.lower()}",
                    resource_type="safety_approval",
                    resource_id=persisted_approval.id,
                    metadata={"change_id": change.id, "decision": decision_upper},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for safety approval: %s", ex)

        return persisted_approval

    def verify_approval_staleness(self, change_id: str) -> None:
        """Check whether an approval is stale due to upstream version modifications."""
        change = self.repository.get_change(change_id)
        if not change or not change.latest_approval_id:
            return

        approval = self.repository.get_approval(change.latest_approval_id)
        if not approval:
            return

        risk = self.repository.get_risk(change.risk_id)
        if not risk:
            return

        # If either change or risk version has mutated since approval, mark STALE
        if approval.bound_risk_version != risk.version or approval.bound_change_version != (change.version - 1):
            approval.is_stale = True
            self.repository.save_approval(approval)
            change.state = ChangeRequestState.STALE
            self.repository.save_change(change)
            self.metrics_service.increment("stale_approval_count")
            raise SafetyChangeStaleException(
                f"Approval for safety change '{change_id}' is STALE due to upstream version shifts. Re-approval required."
            )


# Global singleton safety change approval service
safety_change_approval_service = SafetyChangeApprovalService()

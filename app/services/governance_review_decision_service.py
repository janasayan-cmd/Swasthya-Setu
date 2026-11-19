"""Phase 67: Governance Review and Decision Coordination Service.

Coordinates governance reviews, records formal decisions, enforces separation of duties,
and tracks required action outcomes across safety workflows.

Mandatory Invariants:
1. A recommendation does not constitute approval.
2. Automated routing must never bypass role-based authorization or separation-of-duties requirements.
3. Only authorized users may record governance decisions.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_escalation_repository import (
    GovernanceEscalationRepository,
    get_governance_escalation_repository,
)
from app.schemas.auth import UserRole
from app.schemas.governance_decision_coordination import (
    GovernanceDecisionRecord,
    GovernanceReviewOutcome,
    GovernanceReviewRecord,
    RecordGovernanceDecisionRequest,
    RecordGovernanceReviewRequest,
)
from app.schemas.governance_escalation import (
    EscalationHistoryRecord,
    EscalationLifecycleState,
    GovernanceEscalationRecord,
)
from app.schemas.governance_resolution_requirement import (
    RequirementCategory,
    RequirementStatus,
    ResolutionRequirementRecord,
)
from app.schemas.user import AuthenticatedUserContext


class GovernanceReviewDecisionService:
    """Service coordinating governance reviews, decision recording, and authorization boundaries."""

    def __init__(
        self,
        repository: Optional[GovernanceEscalationRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_escalation_repository()

    def record_review(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: RecordGovernanceReviewRequest,
    ) -> GovernanceReviewRecord:
        """Record a formal governance review execution on an escalation."""
        escalation = self.repository.get_escalation(escalation_id)
        if not escalation:
            raise AppException(
                code=ErrorCode.GOVERNANCE_ESCALATION_NOT_FOUND,
                message=f"Governance escalation {escalation_id} not found.",
                status_code=404,
            )
        if escalation.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot review escalation across tenant boundaries.",
                status_code=403,
            )

        # Role verification: patients cannot conduct governance reviews
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role is not authorized to conduct governance reviews.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = GovernanceReviewRecord(
            escalation_id=escalation_id,
            reviewer_id=user.user_id,
            reviewer_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            outcome=payload.outcome,
            rationale=payload.rationale,
            policy_version=payload.policy_version or "v1.0.0",
            reviewed_exception_ids=payload.reviewed_exception_ids or [],
            evidence_refs=payload.evidence_refs or [],
            required_follow_up_actions=payload.required_follow_up_actions or [],
            required_downstream_workflows=payload.required_downstream_workflows or [],
            reviewed_at=now,
            metadata=payload.metadata or {},
        )

        self.repository.save_review(record)

        # Transition escalation state according to review outcome
        prev_state = escalation.lifecycle_state
        if payload.outcome in {
            GovernanceReviewOutcome.ACCEPT_FOR_REVIEW,
            GovernanceReviewOutcome.ACTION_REQUIRED,
            GovernanceReviewOutcome.ADDITIONAL_EVIDENCE_REQUIRED,
            GovernanceReviewOutcome.REASSESSMENT_REQUIRED,
            GovernanceReviewOutcome.SPECIALIST_REVIEW_REQUIRED,
            GovernanceReviewOutcome.GOVERNANCE_COMMITTEE_REVIEW_REQUIRED,
        }:
            escalation.lifecycle_state = EscalationLifecycleState.REVIEW_IN_PROGRESS
        elif payload.outcome == GovernanceReviewOutcome.RESOLUTION_RECOMMENDED:
            escalation.lifecycle_state = EscalationLifecycleState.DECISION_PENDING

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=escalation.lifecycle_state,
                action="RECORD_GOVERNANCE_REVIEW",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.rationale,
                details={"outcome": payload.outcome.value, "review_id": record.review_id},
            )
        )

        return record

    def record_decision(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: RecordGovernanceDecisionRequest,
    ) -> GovernanceDecisionRecord:
        """Record an authorized governance decision."""
        escalation = self.repository.get_escalation(escalation_id)
        if not escalation:
            raise AppException(
                code=ErrorCode.GOVERNANCE_ESCALATION_NOT_FOUND,
                message=f"Governance escalation {escalation_id} not found.",
                status_code=404,
            )
        if escalation.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot record decision across tenant boundaries.",
                status_code=403,
            )

        # Role check: only ADMIN or authorized DOCTOR
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Role not authorized to record authoritative governance decisions.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = GovernanceDecisionRecord(
            escalation_id=escalation_id,
            decided_by=user.user_id,
            decided_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            decision_type=payload.decision_type,
            decision_title=payload.decision_title,
            rationale=payload.rationale,
            policy_reference=payload.policy_reference or "gov-decision-policy-v1",
            policy_version=payload.policy_version or "v1.0.0",
            approved_actions=payload.approved_actions or [],
            required_resolution_requirements=payload.required_resolution_requirements or [],
            target_workflow_instructions=payload.target_workflow_instructions or {},
            decided_at=now,
            metadata=payload.metadata or {},
        )

        self.repository.save_decision(record)

        # Automatically spawn resolution requirements if specified in decision
        if payload.required_resolution_requirements:
            for req_title in payload.required_resolution_requirements:
                req = ResolutionRequirementRecord(
                    escalation_id=escalation_id,
                    title=req_title,
                    category=RequirementCategory.GOVERNANCE_APPROVAL,
                    is_mandatory=True,
                    status=RequirementStatus.PENDING,
                    responsible_phase="PHASE_67",
                    responsible_owner=user.user_id,
                )
                self.repository.save_requirement(req)

        prev_state = escalation.lifecycle_state
        escalation.lifecycle_state = EscalationLifecycleState.ACTION_REQUIRED
        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=escalation.lifecycle_state,
                action="RECORD_GOVERNANCE_DECISION",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.rationale,
                details={
                    "decision_type": payload.decision_type,
                    "decision_id": record.decision_id,
                },
            )
        )

        return record


# Global singleton
_global_review_decision_service = GovernanceReviewDecisionService()


def get_governance_review_decision_service() -> GovernanceReviewDecisionService:
    """Dependency provider for review and decision service."""
    return _global_review_decision_service

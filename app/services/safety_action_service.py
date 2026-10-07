"""Phase 54: Primary Safety Action Lifecycle Orchestration Service.

Coordinates finding intake, classification, human approval, owner assignment,
execution gating, verification, effectiveness evaluation, and closed-loop assurance.

Preserves all 20+ core safety distinctions from TRD Section 2.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_action_repository import (
    SafetyActionRepository,
    safety_action_repository,
)
from app.schemas.safety_action import (
    ActionApprovalDecision,
    ActionApprovalState,
    ActionEffectivenessState,
    ActionHistoryEntry,
    ActionLifecycleState,
    ActionOwnerDomain,
    ActionPriority,
    ActionType,
    ActionabilityState,
    FindingSourceType,
    SafetyActionApproveRequest,
    SafetyActionAssignRequest,
    SafetyActionCloseRequest,
    SafetyActionCompleteRequest,
    SafetyActionCreateRequest,
    SafetyActionEscalateRequest,
    SafetyActionExecuteRequest,
    SafetyActionRecord,
    SafetyActionReopenRequest,
    SafetyActionRetryRequest,
    SafetyActionRollbackRequest,
    SafetyActionScope,
    SafetyActionVerifyRequest,
    TargetSubsystem,
)
from app.services.safety_action_approval_service import (
    SafetyActionApprovalService,
    safety_action_approval_service,
)
from app.services.safety_action_classification_service import (
    SafetyActionClassificationService,
    safety_action_classification_service,
)
from app.services.safety_action_effectiveness_service import (
    SafetyActionEffectivenessService,
    safety_action_effectiveness_service,
)
from app.services.safety_action_escalation_service import (
    SafetyActionEscalationService,
    safety_action_escalation_service,
)
from app.services.safety_action_routing_service import (
    SafetyActionRoutingService,
    safety_action_routing_service,
)
from app.services.safety_action_validation_service import (
    SafetyActionValidationService,
    safety_action_validation_service,
)

logger = logging.getLogger("app.services.safety_action_service")


class SafetyActionService:
    """Primary facade managing Phase 54 controlled action lifecycle."""

    def __init__(
        self,
        repo: Optional[SafetyActionRepository] = None,
        classification: Optional[SafetyActionClassificationService] = None,
        validation: Optional[SafetyActionValidationService] = None,
        approval: Optional[SafetyActionApprovalService] = None,
        routing: Optional[SafetyActionRoutingService] = None,
        effectiveness: Optional[SafetyActionEffectivenessService] = None,
        escalation: Optional[SafetyActionEscalationService] = None,
    ) -> None:
        self._repo = repo or safety_action_repository
        self._classification = classification or safety_action_classification_service
        self._validation = validation or safety_action_validation_service
        self._approval = approval or safety_action_approval_service
        self._routing = routing or safety_action_routing_service
        self._effectiveness = effectiveness or safety_action_effectiveness_service
        self._escalation = escalation or safety_action_escalation_service

    def _record_history(
        self,
        action: SafetyActionRecord,
        prev_state: ActionLifecycleState,
        actor_id: str,
        actor_role: str,
        reason: str,
    ) -> None:
        """Helper to append an immutable history entry and increment version."""
        entry = ActionHistoryEntry(
            action_id=action.action_id,
            version=action.version,
            previous_state=prev_state,
            new_state=action.lifecycle_state,
            actor_id=actor_id,
            actor_role=actor_role,
            transition_reason=reason,
        )
        self._repo.record_history(entry)

    def create_action(
        self,
        request: SafetyActionCreateRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
        actor_facility_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Create a candidate safety action from an oversight finding."""
        # Check idempotency
        if request.idempotency_key:
            existing = self._repo.get_by_idempotency_key(request.idempotency_key)
            if existing:
                return existing

        # Validate scope
        scope = request.scope or SafetyActionScope()
        resolved_org_id = actor_organization_id or scope.organization_id
        resolved_fac_id = scope.facility_id
        scope.organization_id = resolved_org_id
        scope.facility_id = resolved_fac_id

        self._validation.validate_scope_access(scope, actor_organization_id, actor_facility_id)

        # Policy-driven classification & server-side priority/urgency
        actionability, priority, is_urgent, target_subsystem = (
            self._classification.classify_finding(request.finding, request.action_type)
        )

        now = datetime.now(timezone.utc)
        due_at = now + timedelta(hours=request.due_in_hours or 72)

        action = SafetyActionRecord(
            title=request.title,
            description=request.description,
            action_type=request.action_type,
            lifecycle_state=ActionLifecycleState.IDENTIFIED,
            actionability=actionability,
            priority=priority,
            is_urgent=is_urgent,
            scope=scope,
            finding=request.finding,
            target_subsystem=target_subsystem,
            organization_id=resolved_org_id,
            facility_id=resolved_fac_id,
            created_by_id=actor_id,
            created_by_role=actor_role,
            idempotency_key=request.idempotency_key,
            due_at=due_at,
        )

        # Move to ACTIONABILITY_DETERMINED or REVIEW_REQUIRED
        prev_state = action.lifecycle_state
        if actionability == ActionabilityState.REVIEW_REQUIRED or action.priority in (
            ActionPriority.HIGH,
            ActionPriority.CRITICAL,
        ):
            action.lifecycle_state = ActionLifecycleState.REVIEW_REQUIRED
        else:
            action.lifecycle_state = ActionLifecycleState.READY

        action = self._repo.save_action(action)
        self._record_history(action, prev_state, actor_id, actor_role, "Safety action candidate created.")
        return action

    def get_action(
        self,
        action_id: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Retrieve action by ID with tenant boundary validation."""
        action = self._repo.get_action(action_id)
        if not action:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_NOT_FOUND,
                message=f"Safety action '{action_id}' not found.",
                status_code=404,
            )
        if (
            actor_organization_id
            and action.organization_id
            and action.organization_id != actor_organization_id
        ):
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_ACCESS_DENIED,
                message="Access denied to this safety action.",
                status_code=403,
            )
        return action

    def approve_action(
        self,
        action_id: str,
        request: SafetyActionApproveRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Submit formal human governance review and approval."""
        action = self.get_action(action_id, actor_organization_id)
        self._validation.validate_concurrency(action, request.action_version)
        self._validation.validate_separation_of_duties(action, actor_id, actor_role, "approve")

        prev_state = action.lifecycle_state
        target_state = (
            ActionLifecycleState.APPROVED
            if request.decision == ActionApprovalDecision.APPROVE
            else ActionLifecycleState.REJECTED
        )
        self._validation.validate_transition(prev_state, target_state)

        approval_record = self._approval.submit_approval(action, request, actor_id, actor_role)
        action.approval = approval_record
        action.lifecycle_state = target_state

        if target_state == ActionLifecycleState.APPROVED:
            # Transition to READY
            action.lifecycle_state = ActionLifecycleState.READY

        action.version += 1
        action = self._repo.save_action(action)
        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Approval decision: {request.decision.value}. Reason: {request.reason}",
        )
        return action

    def assign_action(
        self,
        action_id: str,
        request: SafetyActionAssignRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Assign authorized operational owner to action."""
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state
        self._validation.validate_transition(prev_state, ActionLifecycleState.ASSIGNED)

        from app.schemas.safety_action import ActionAssignmentRecord

        assignment = ActionAssignmentRecord(
            owner_id=request.owner_id,
            owner_role=request.owner_role,
            owner_domain=request.owner_domain,
            assigned_by_id=actor_id,
            assignment_notes=request.notes,
        )

        action.assignment = assignment
        action.lifecycle_state = ActionLifecycleState.ASSIGNED
        action.version += 1
        action = self._repo.save_action(action)
        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Assigned to {request.owner_id} ({request.owner_domain.value})",
        )
        return action

    def start_action(
        self,
        action_id: str,
        request: Optional[SafetyActionExecuteRequest],
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """
        EXECUTION GATE (Section 15):
        Validate all prerequisites before executing action in authoritative subsystem.
        """
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state
        self._validation.validate_transition(prev_state, ActionLifecycleState.IN_PROGRESS)

        # 1. Approval Freshness Gate
        self._approval.check_approval_freshness(action)

        # 2. Clinical Action Boundary Gate
        payload = request.execution_payload if request else {}
        self._validation.validate_clinical_action_boundary(action.action_type, payload)

        # 3. Dispatch to Authoritative Subsystem
        if request and request.target_subsystem:
            action.target_subsystem = request.target_subsystem

        dispatch_res = self._routing.dispatch_to_subsystem(action, payload)

        now = datetime.now(timezone.utc)
        action.started_at = now
        action.lifecycle_state = ActionLifecycleState.IN_PROGRESS
        action.version += 1
        action = self._repo.save_action(action)

        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Action execution started in {action.target_subsystem.value}. Ref: {dispatch_res.get('reference_id')}",
        )
        return action

    def complete_action(
        self,
        action_id: str,
        request: SafetyActionCompleteRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Record operational completion of an action. COMPLETION != EFFECTIVENESS."""
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state
        self._validation.validate_transition(prev_state, ActionLifecycleState.COMPLETED)

        now = datetime.now(timezone.utc)
        action.completed_at = now
        action.lifecycle_state = ActionLifecycleState.COMPLETED
        action.version += 1
        action = self._repo.save_action(action)

        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Completed: {request.completion_summary}",
        )
        return action

    def verify_action(
        self,
        action_id: str,
        request: SafetyActionVerifyRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """
        Perform independent verification of completed action and trigger
        closed-loop effectiveness evaluation into Phase 52.
        """
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state
        self._validation.validate_separation_of_duties(action, actor_id, actor_role, "verify")

        if not request.verified:
            action.lifecycle_state = ActionLifecycleState.FAILED
            action.version += 1
            action = self._repo.save_action(action)
            self._record_history(action, prev_state, actor_id, actor_role, f"Verification failed: {request.verification_notes}")
            return action

        self._validation.validate_transition(prev_state, ActionLifecycleState.VERIFIED)

        now = datetime.now(timezone.utc)
        action.verified_at = now
        action.lifecycle_state = ActionLifecycleState.VERIFIED

        # Trigger Phase 52 closed-loop effectiveness evaluation
        self._effectiveness.evaluate_effectiveness(
            action=action,
            evaluator_id=actor_id,
            effectiveness_state=ActionEffectivenessState.EFFECTIVE_OBSERVED,
            notes=request.verification_notes,
        )

        action.version += 1
        action = self._repo.save_action(action)
        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Verified successfully: {request.verification_notes}",
        )
        return action

    def fail_action(
        self,
        action_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Mark action failed and evaluate retry / reassessment requirement."""
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state
        self._validation.validate_transition(prev_state, ActionLifecycleState.FAILED)

        action.lifecycle_state = ActionLifecycleState.FAILED
        action.version += 1
        action = self._repo.save_action(action)
        self._record_history(action, prev_state, actor_id, actor_role, f"Action failed: {reason}")
        return action

    def retry_action(
        self,
        action_id: str,
        request: SafetyActionRetryRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Execute bounded, policy-controlled retry."""
        action = self.get_action(action_id, actor_organization_id)
        if action.retry_count >= action.max_retries:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_RETRY_DENIED,
                message=f"Action exceeded maximum retry limit ({action.max_retries}).",
                status_code=400,
            )

        prev_state = action.lifecycle_state
        self._validation.validate_transition(prev_state, ActionLifecycleState.IN_PROGRESS)

        action.retry_count += 1
        action.lifecycle_state = ActionLifecycleState.IN_PROGRESS
        action.version += 1
        action = self._repo.save_action(action)
        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Retry #{action.retry_count}: {request.retry_reason}",
        )
        return action

    def rollback_action(
        self,
        action_id: str,
        request: SafetyActionRollbackRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Rollback executed action if safety degrades. Preserves history."""
        action = self.get_action(action_id, actor_organization_id)
        self._validation.validate_concurrency(action, request.action_version)

        prev_state = action.lifecycle_state
        action.is_rolled_back = True
        action.rollback_reason = request.rollback_reason
        action.lifecycle_state = ActionLifecycleState.REQUIRES_REASSESSMENT
        action.version += 1
        action = self._repo.save_action(action)

        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Rolled back: {request.rollback_reason}",
        )
        return action

    def escalate_action(
        self,
        action_id: str,
        request: SafetyActionEscalateRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Process policy-backed escalation."""
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state

        self._escalation.escalate_action(action, request, actor_id)
        action.version += 1
        action = self._repo.save_action(action)

        self._record_history(
            action,
            prev_state,
            actor_id,
            actor_role,
            f"Escalated to {request.escalation_level.value}: {request.reason}",
        )
        return action

    def close_action(
        self,
        action_id: str,
        request: SafetyActionCloseRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Close an action after verifying completion and safety prerequisites."""
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state

        # Precondition check: must have been verified or completed
        if action.lifecycle_state not in (
            ActionLifecycleState.VERIFIED,
            ActionLifecycleState.MONITORING,
            ActionLifecycleState.COMPLETED,
        ):
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_VERIFICATION_REQUIRED,
                message=f"Cannot close action in state '{action.lifecycle_state.value}'. Verification required.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        action.closed_at = now
        action.lifecycle_state = ActionLifecycleState.CLOSED
        action.version += 1
        action = self._repo.save_action(action)

        self._record_history(action, prev_state, actor_id, actor_role, f"Closed: {request.closure_summary}")
        return action

    def reopen_action(
        self,
        action_id: str,
        request: SafetyActionReopenRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyActionRecord:
        """Reopen a closed action when new evidence or regression appears."""
        action = self.get_action(action_id, actor_organization_id)
        prev_state = action.lifecycle_state
        self._validation.validate_transition(prev_state, ActionLifecycleState.REOPENED)

        action.closed_at = None
        action.lifecycle_state = ActionLifecycleState.REOPENED
        action.version += 1
        action = self._repo.save_action(action)

        self._record_history(action, prev_state, actor_id, actor_role, f"Reopened: {request.reopen_reason}")
        return action


# Global singleton
safety_action_service = SafetyActionService()

"""Phase 58: Safety Verification Closure & Reopen Governance Service.

Governs closure eligibility evaluation, controlled closure execution,
post-closure monitoring registration, and historical reopening workflows.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_rollout_repository import (
    SafetyRolloutRepository,
    get_safety_rollout_repository,
)
from app.schemas.safety_rollout import CheckpointStatus, RolloutLifecycleState
from app.schemas.safety_verification import (
    AssuranceOutcomeStatus,
    ClosureEligibilityResponse,
    EffectivenessOutcomeStatus,
    HumanVerificationDecision,
    PostClosureMonitoringRecord,
    ReopenRecord,
    SafetyVerificationRecord,
    VerificationCondition,
    VerificationHistoryEntry,
    VerificationLifecycleState,
)


class SafetyVerificationClosureService:
    """Evaluates closure eligibility and executes controlled closure or reopening."""

    def __init__(self, rollout_repository: Optional[SafetyRolloutRepository] = None) -> None:
        self.rollout_repository = rollout_repository or get_safety_rollout_repository()

    def evaluate_closure_eligibility(
        self, verification: SafetyVerificationRecord
    ) -> ClosureEligibilityResponse:
        """Evaluate if the verified rollout satisfies all required criteria for formal closure."""
        blocking_reasons: List[Dict[str, str]] = []
        required_actions: List[str] = []

        rollout = self.rollout_repository.get(verification.rollout_id)
        if not rollout:
            blocking_reasons.append({"code": "ROLLOUT_NOT_FOUND", "message": f"Source rollout '{verification.rollout_id}' not found"})
            required_actions.append("Ensure source rollout exists")
        else:
            # 1. Rollout must have completed or verified full scope
            if rollout.lifecycle_state not in {RolloutLifecycleState.COMPLETED, RolloutLifecycleState.POST_DEPLOYMENT_VALIDATION}:
                blocking_reasons.append({
                    "code": "ROLLOUT_NOT_COMPLETE",
                    "message": f"Rollout lifecycle is '{rollout.lifecycle_state.value}', expected COMPLETED",
                })
                required_actions.append("Complete Phase 57 rollout and post-deployment validation")

            # 2. Checkpoints passed
            if any(cp.status != CheckpointStatus.PASSED for cp in rollout.checkpoints):
                blocking_reasons.append({
                    "code": "CHECKPOINTS_INCOMPLETE",
                    "message": "One or more rollout checkpoints have not passed",
                })
                required_actions.append("Satisfy all pending or failed rollout checkpoints")

            # 3. Safety controls verified
            if verification.safety_control_status != "PASSED":
                blocking_reasons.append({
                    "code": "SAFETY_CONTROL_FAILED",
                    "message": f"Active runtime safety controls status is {verification.safety_control_status}",
                })
                required_actions.append("Verify active runtime safety gates in Phase 48")

        # 4. Version alignment
        if verification.approved_version != verification.deployed_version:
            blocking_reasons.append({
                "code": "VERSION_MISMATCH",
                "message": f"Approved version '{verification.approved_version}' differs from deployed '{verification.deployed_version}'",
            })
            required_actions.append("Resolve version discrepancy with governance")

        # 5. Assurance status (Phase 52)
        if verification.assurance_status == AssuranceOutcomeStatus.ASSURANCE_FAILED:
            blocking_reasons.append({"code": "ASSURANCE_FAILED", "message": "Clinical safety assurance failed"})
            required_actions.append("Remediate assurance failure with Phase 52")
        elif verification.assurance_status == AssuranceOutcomeStatus.ASSURANCE_PENDING:
            blocking_reasons.append({"code": "ASSURANCE_PENDING", "message": "Assurance confirmation is pending"})
            required_actions.append("Obtain Phase 52 assurance confirmation")

        # 6. Effectiveness status (Phase 55)
        if verification.effectiveness_status == EffectivenessOutcomeStatus.EFFECTIVENESS_FAILED:
            blocking_reasons.append({"code": "EFFECTIVENESS_FAILED", "message": "Post-action outcome effectiveness failed"})
            required_actions.append("Remediate outcome effectiveness with Phase 55")
        elif verification.effectiveness_status == EffectivenessOutcomeStatus.EFFECTIVENESS_PENDING:
            blocking_reasons.append({"code": "EFFECTIVENESS_PENDING", "message": "Outcome effectiveness observation pending"})
            required_actions.append("Complete Phase 55 post-action observation period")

        # 7. Human review requirement
        if not verification.human_reviews or not any(
            r.decision in (HumanVerificationDecision.VERIFY, HumanVerificationDecision.VERIFY_WITH_CONDITIONS)
            for r in verification.human_reviews
        ):
            blocking_reasons.append({"code": "REVIEW_REQUIRED", "message": "Authorized human verification signoff has not been completed"})
            required_actions.append("Submit human verification review decision")

        eligible = len(blocking_reasons) == 0
        status_text = "CLOSURE_ELIGIBLE" if eligible else "CLOSURE_NOT_ELIGIBLE"

        return ClosureEligibilityResponse(
            verification_id=verification.verification_id,
            eligible=eligible,
            status=status_text,
            blocking_reasons=blocking_reasons,
            conditions=verification.conditions,
            required_actions=required_actions,
        )

    def execute_closure(
        self,
        verification: SafetyVerificationRecord,
        rationale: str,
        actor_id: str,
        actor_role: str,
        monitoring_window_days: int = 30,
        monitoring_owner: Optional[str] = None,
        expected_signals: Optional[List[str]] = None,
    ) -> SafetyVerificationRecord:
        """Perform controlled change closure after validating eligibility."""
        if verification.verification_status == VerificationLifecycleState.CLOSED:
            raise AppException(
                code=ErrorCode.CLOSURE_ALREADY_COMPLETED,
                message="Safety verification is already closed",
                status_code=400,
            )

        eligibility = self.evaluate_closure_eligibility(verification)
        if not eligibility.eligible:
            reasons_summary = ", ".join(r["message"] for r in eligibility.blocking_reasons)
            raise AppException(
                code=ErrorCode.CLOSURE_BLOCKED,
                message=f"Change closure is blocked by governed criteria: {reasons_summary}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        from_state = verification.verification_status.value
        verification.verification_status = VerificationLifecycleState.CLOSED
        verification.closed_at = now
        verification.closed_by = actor_id
        verification.closure_notes = rationale
        verification.version += 1

        # Register Post-Closure Monitoring (TRD Section 26)
        verification.post_closure_monitoring = PostClosureMonitoringRecord(
            monitoring_window_days=monitoring_window_days,
            monitoring_owner=monitoring_owner or actor_id,
            expected_signals=expected_signals or ["NO_SAFETY_INTERCEPT_BYPASS", "ZERO_CRITICAL_INCIDENTS"],
            observation_threshold=f"{monitoring_window_days} days uninterrupted nominal telemetry",
            review_schedule="Bi-weekly clinical safety audit review",
            registered_at=now,
            status="ACTIVE",
        )

        verification.history.append(
            VerificationHistoryEntry(
                from_state=from_state,
                to_state=VerificationLifecycleState.CLOSED.value,
                action="CONTROLLED_CLOSURE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=rationale,
                timestamp=now,
            )
        )

        return verification

    def execute_reopen(
        self,
        verification: SafetyVerificationRecord,
        reason: str,
        actor_id: str,
        actor_role: str,
        triggering_evidence_id: Optional[str] = None,
    ) -> SafetyVerificationRecord:
        """Reopen a previously closed change for review or reassessment."""
        if verification.verification_status != VerificationLifecycleState.CLOSED:
            raise AppException(
                code=ErrorCode.REOPEN_NOT_ALLOWED,
                message=f"Cannot reopen verification in state '{verification.verification_status.value}'. Must be CLOSED.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        from_state = verification.verification_status.value
        verification.verification_status = VerificationLifecycleState.REOPENED
        verification.closure_eligible = False
        verification.version += 1

        reopen_record = ReopenRecord(
            previous_closure_id=f"cls-{verification.verification_id}-{verification.version - 1}",
            reason=reason,
            triggering_evidence_id=triggering_evidence_id,
            actor_id=actor_id,
            actor_role=actor_role,
            reopened_at=now,
        )
        verification.reopen_history.append(reopen_record)

        if verification.post_closure_monitoring:
            verification.post_closure_monitoring.status = "TRIGGERED_REOPEN"

        verification.history.append(
            VerificationHistoryEntry(
                from_state=from_state,
                to_state=VerificationLifecycleState.REOPENED.value,
                action="CONTROLLED_REOPEN",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                timestamp=now,
            )
        )

        return verification

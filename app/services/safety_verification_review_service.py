"""Phase 58: Safety Verification Human Review Service.

Enforces human-in-the-loop governance, separation of duties constraints,
and AI boundary enforcement per TRD Section 19, 20, and 27.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_rollout_repository import (
    SafetyRolloutRepository,
    get_safety_rollout_repository,
)
from app.schemas.safety_verification import (
    HumanVerificationDecision,
    HumanVerificationReviewRecord,
    SafetyVerificationRecord,
    VerificationCondition,
    VerificationLifecycleState,
)


class SafetyVerificationReviewService:
    """Manages human review gates, separation of duties, and verification decisions."""

    ALLOWED_REVIEWER_ROLES = {
        "CLINICAL_SAFETY_OFFICER",
        "GOVERNANCE_LEAD",
        "CHIEF_MEDICAL_OFFICER",
        "ADMIN",
        "SUPER_ADMIN",
        "SAFETY_LEAD",
        "SAFETY_OFFICER",
    }

    def __init__(self, rollout_repository: Optional[SafetyRolloutRepository] = None) -> None:
        self.rollout_repository = rollout_repository or get_safety_rollout_repository()

    def submit_review(
        self,
        verification: SafetyVerificationRecord,
        decision: HumanVerificationDecision,
        rationale: str,
        reviewer_id: str,
        reviewer_role: str,
        conditions: Optional[List[str]] = None,
        is_ai_agent: bool = False,
    ) -> HumanVerificationReviewRecord:
        """Evaluate and record a human verification decision."""
        # 1. AI Boundary Enforcement (TRD Section 27)
        if is_ai_agent or reviewer_role.upper() in {"AI", "AI_AGENT", "AUTOMATION"}:
            raise AppException(
                code=ErrorCode.REVIEW_INVALID,
                message="AI systems cannot approve safety verification, release signoff, or closure decisions",
                status_code=400,
            )

        # 2. Reviewer Role Authorization
        clean_role = reviewer_role.replace("UserRole.", "").upper()
        if clean_role not in self.ALLOWED_REVIEWER_ROLES and reviewer_role.upper() not in self.ALLOWED_REVIEWER_ROLES:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Role '{reviewer_role}' is not authorized to perform safety verification signoff",
                status_code=403,
            )

        # 3. Separation of Duties Enforcement (TRD Section 20)
        # CHANGE_APPROVER != IMPLEMENTER != FINAL_VERIFIER
        rollout = self.rollout_repository.get(verification.rollout_id)
        if rollout:
            # Check approver
            if rollout.approval.approver_id == reviewer_id:
                raise AppException(
                    code=ErrorCode.SEPARATION_OF_DUTIES_FAILED,
                    message=(
                        f"Separation of duties violation: reviewer '{reviewer_id}' "
                        f"cannot be the same person who approved the change proposal"
                    ),
                    status_code=400,
                )
            # Check implementer / rollout creator
            if rollout.created_by == reviewer_id:
                raise AppException(
                    code=ErrorCode.SEPARATION_OF_DUTIES_FAILED,
                    message=(
                        f"Separation of duties violation: reviewer '{reviewer_id}' "
                        f"cannot be the same person who initiated/implemented the rollout"
                    ),
                    status_code=400,
                )

        now = datetime.now(timezone.utc)
        review_record = HumanVerificationReviewRecord(
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            rationale=rationale,
            reviewed_at=now,
            conditions=conditions or [],
        )

        verification.human_reviews.append(review_record)

        # Transition lifecycle based on decision
        if decision == HumanVerificationDecision.VERIFY:
            verification.verification_status = VerificationLifecycleState.VERIFIED
            verification.closure_eligible = True
        elif decision == HumanVerificationDecision.VERIFY_WITH_CONDITIONS:
            verification.verification_status = VerificationLifecycleState.CONDITIONALLY_VERIFIED
            verification.closure_eligible = True
            for c_text in (conditions or []):
                verification.conditions.append(
                    VerificationCondition(
                        owner=reviewer_id,
                        required_evidence=c_text,
                        completion_criteria=f"Evidence provided for: {c_text}",
                        escalation_rule="Escalate to Clinical Safety Officer after 7 days if unfulfilled",
                    )
                )
        elif decision == HumanVerificationDecision.BLOCK:
            verification.verification_status = VerificationLifecycleState.VERIFICATION_BLOCKED
            verification.closure_eligible = False
            verification.blocking_reasons.append(f"Blocked by reviewer {reviewer_id}: {rationale}")
        elif decision == HumanVerificationDecision.REASSESS:
            verification.verification_status = VerificationLifecycleState.REASSESSMENT_REQUIRED
            verification.closure_eligible = False
            verification.blocking_reasons.append(f"Reassessment requested: {rationale}")
        elif decision == HumanVerificationDecision.REQUEST_MORE_EVIDENCE:
            verification.verification_status = VerificationLifecycleState.EVIDENCE_INCOMPLETE
            verification.closure_eligible = False
            verification.blocking_reasons.append(f"More evidence requested: {rationale}")

        return review_record

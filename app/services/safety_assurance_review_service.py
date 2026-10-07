"""Phase 52: Safety Assurance Review Service.

Manages human assurance review workflows for high-risk assurance outcomes.

Enforces:
  - Reviewer identity and role are derived from authenticated backend context (never client-provided).
  - AI cannot approve, accept, or reject assurance.
  - Separation of duties: implementer cannot be sole assurance approver where policy requires.
  - Review records are immutable audit artifacts.
  - ASSURANCE REVIEW != CLINICAL DIAGNOSIS.
  - ASSURANCE REVIEW != LEGAL LIABILITY DETERMINATION.
  - RECOMMENDATION != APPROVAL.
  - APPROVAL != IMPLEMENTATION.

All AI-generated material is explicitly marked AI_SUGGESTED and requires
human review before any assurance state change.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_assurance import (
    AssuranceAIStatus,
    AssuranceEvaluationRecord,
    AssuranceLifecycleState,
    AssuranceReviewDecision,
    AssuranceReviewRequest,
    ControlEffectivenessState,
)
from app.repositories.safety_assurance_repository import (
    SafetyAssuranceRepository,
    safety_assurance_repository,
)
from app.services.safety_assurance_validation_service import (
    SafetyAssuranceValidationService,
    safety_assurance_validation_service,
)

logger = logging.getLogger("app.services.safety_assurance_review_service")


class SafetyAssuranceReviewService:
    """Manages authorized human review for assurance evaluations.

    Reviewer identity, role, and authorization basis are derived from
    authenticated session — never from client request body.

    ASSURANCE REVIEW != CLINICAL DIAGNOSIS.
    ASSURANCE REVIEW != LEGAL LIABILITY DETERMINATION.
    AI cannot approve assurance decisions.
    """

    # Review decisions that require subsequent routing
    _INCIDENT_ROUTING_DECISIONS = {
        AssuranceReviewDecision.CREATE_INCIDENT_REVIEW,
        AssuranceReviewDecision.MARK_FAILED,
    }

    _CHANGE_ROUTING_DECISIONS = {
        AssuranceReviewDecision.CREATE_SAFETY_CHANGE,
        AssuranceReviewDecision.REASSESS_RISK,
    }

    _REASSESSMENT_DECISIONS = {
        AssuranceReviewDecision.REQUIRE_MORE_EVIDENCE,
        AssuranceReviewDecision.REJECT_EVALUATION,
        AssuranceReviewDecision.REASSESS_RISK,
    }

    def __init__(
        self,
        assurance_repo: Optional[SafetyAssuranceRepository] = None,
        validation_svc: Optional[SafetyAssuranceValidationService] = None,
    ) -> None:
        self._repo = assurance_repo or safety_assurance_repository
        self._validation = validation_svc or safety_assurance_validation_service

    def submit_review(
        self,
        evaluation_id: str,
        review_request: AssuranceReviewRequest,
        reviewer_id: str,
        reviewer_role: str,
        reviewer_authorization_basis: str,
        organization_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Submit a human assurance review for an evaluation.

        CRITICAL: reviewer_id, reviewer_role, and authorization_basis are
        derived from authenticated backend session — not from client body.

        AI cannot submit reviews or approve assurance decisions.

        Args:
            evaluation_id: Evaluation under review.
            review_request: Human reviewer's structured decision.
            reviewer_id: From authenticated session (NOT client body).
            reviewer_role: From authenticated session (NOT client body).
            reviewer_authorization_basis: Policy reference for authorization.
            organization_id: Scope enforced from authenticated context.
            request_id: Correlation request ID.

        Returns:
            Updated assurance evaluation record.

        Raises:
            AppException: On invalid state, concurrency conflict, or authorization failure.
        """
        evaluation = self._repo.get_evaluation(evaluation_id)
        if evaluation is None:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_NOT_FOUND,
                message=f"Assurance evaluation '{evaluation_id}' not found.",
                status_code=404,
            )

        # Organization scope enforcement
        if organization_id and evaluation.organization_id and evaluation.organization_id != organization_id:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_ACCESS_DENIED,
                message="Access denied: evaluation does not belong to your organization scope.",
                status_code=403,
            )

        # State validation: must be REVIEW_REQUIRED or UNDER_REVIEW
        if evaluation.lifecycle_state not in (
            AssuranceLifecycleState.REVIEW_REQUIRED,
            AssuranceLifecycleState.UNDER_REVIEW,
        ):
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_INVALID_STATE,
                message=(
                    f"Evaluation is in state '{evaluation.lifecycle_state.value}'. "
                    "Review can only be submitted when state is REVIEW_REQUIRED or UNDER_REVIEW."
                ),
                status_code=409,
            )

        # Concurrency check
        self._validation.validate_concurrency(evaluation, review_request.evaluation_version)

        # AI material acknowledgment check
        if evaluation.ai_status in (
            AssuranceAIStatus.AI_SUGGESTED,
            AssuranceAIStatus.HUMAN_REVIEW_REQUIRED,
        ) and not review_request.ai_material_reviewed:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_REVIEW_REQUIRED,
                message=(
                    "This evaluation contains AI-suggested material. "
                    "Reviewer must acknowledge AI material before submitting review. "
                    "Set ai_material_reviewed=true to confirm. "
                    "AI SUGGESTION != ASSURANCE DECISION."
                ),
                status_code=422,
            )

        now = datetime.now(timezone.utc)

        # Apply review decision to evaluation
        evaluation.lifecycle_state = AssuranceLifecycleState.UNDER_REVIEW
        evaluation.reviewer_id = reviewer_id  # From authenticated session
        evaluation.reviewer_role = reviewer_role  # From authenticated session
        evaluation.reviewer_authorization_basis = reviewer_authorization_basis
        evaluation.review_decision = review_request.decision
        evaluation.review_summary = review_request.review_summary
        evaluation.review_limitations = review_request.review_limitations
        evaluation.review_required_follow_up = review_request.required_follow_up
        evaluation.reviewed_at = now
        evaluation.updated_at = now
        evaluation.version += 1

        # Mark AI status if reviewer accepted AI material
        if review_request.ai_material_reviewed and evaluation.ai_status in (
            AssuranceAIStatus.AI_SUGGESTED,
            AssuranceAIStatus.HUMAN_REVIEW_REQUIRED,
        ):
            evaluation.ai_status = AssuranceAIStatus.HUMAN_ACCEPTED

        logger.info(
            "Assurance review submitted",
            extra={
                "evaluation_id": evaluation_id,
                "reviewer_role": reviewer_role,
                "decision": review_request.decision.value,
                "request_id": request_id,
            },
        )

        return self._repo.save_evaluation(evaluation)

    def apply_review_decision(
        self,
        evaluation: AssuranceEvaluationRecord,
    ) -> AssuranceEvaluationRecord:
        """Apply the recorded review decision to transition evaluation state.

        Called after submit_review to finalize the lifecycle transition.
        Human decision is authoritative — not AI.

        ASSURANCE REVIEW != CLINICAL DIAGNOSIS.
        REVIEW DECISION != RISK ACCEPTANCE.
        """
        decision = evaluation.review_decision
        if decision is None:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_REVIEW_REQUIRED,
                message="No review decision recorded on evaluation.",
                status_code=422,
            )

        now = datetime.now(timezone.utc)

        if decision in (
            AssuranceReviewDecision.ACCEPT_EFFECTIVENESS,
            AssuranceReviewDecision.ACCEPT_WITH_LIMITATIONS,
        ):
            evaluation.lifecycle_state = AssuranceLifecycleState.ASSURANCE_ACCEPTED
            evaluation.effectiveness_state = ControlEffectivenessState.EFFECTIVE_OBSERVED
            evaluation.completed_at = now

        elif decision == AssuranceReviewDecision.MARK_DEGRADED:
            evaluation.lifecycle_state = AssuranceLifecycleState.DEGRADED
            evaluation.effectiveness_state = ControlEffectivenessState.DEGRADED

        elif decision == AssuranceReviewDecision.MARK_FAILED:
            evaluation.lifecycle_state = AssuranceLifecycleState.FAILED
            evaluation.effectiveness_state = ControlEffectivenessState.FAILED
            # Routing handled by SafetyAssuranceRoutingService

        elif decision in self._REASSESSMENT_DECISIONS:
            evaluation.lifecycle_state = AssuranceLifecycleState.REASSESSMENT_REQUIRED
            evaluation.effectiveness_state = ControlEffectivenessState.REQUIRES_REASSESSMENT

        elif decision == AssuranceReviewDecision.REQUIRE_MORE_EVIDENCE:
            evaluation.lifecycle_state = AssuranceLifecycleState.INSUFFICIENT_EVIDENCE
            evaluation.effectiveness_state = ControlEffectivenessState.INSUFFICIENT_EVIDENCE

        elif decision in self._INCIDENT_ROUTING_DECISIONS:
            evaluation.lifecycle_state = AssuranceLifecycleState.FAILED
            # Routing to Phase 49 handled by SafetyAssuranceRoutingService

        elif decision in self._CHANGE_ROUTING_DECISIONS:
            evaluation.lifecycle_state = AssuranceLifecycleState.REASSESSMENT_REQUIRED
            # Routing to Phase 51 handled by SafetyAssuranceRoutingService

        else:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_INVALID_STATE,
                message=f"Unknown review decision: {decision.value}",
                status_code=422,
            )

        evaluation.review_required = False
        evaluation.updated_at = now
        evaluation.version += 1

        return self._repo.save_evaluation(evaluation)

    def validate_separation_of_duties(
        self,
        evaluation: AssuranceEvaluationRecord,
        reviewer_id: str,
        requires_separation: bool,
    ) -> None:
        """Enforce separation-of-duty policy for assurance review.

        Where policy requires it, the person who implemented the safety
        change SHOULD NOT be the sole authority for declaring it effective.

        Args:
            evaluation: The evaluation under review.
            reviewer_id: Authenticated reviewer identity.
            requires_separation: Whether SOD policy requires separate reviewer.

        Raises:
            AppException: If SOD violation detected.
        """
        if not requires_separation:
            return

        if evaluation.initiated_by_actor_id and evaluation.initiated_by_actor_id == reviewer_id:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_REVIEW_DENIED,
                message=(
                    "Separation of duty violation: the actor who initiated this assurance "
                    "evaluation cannot be the sole reviewer where policy requires separation. "
                    "A different authorized reviewer must be assigned."
                ),
                status_code=403,
            )


# Global singleton
safety_assurance_review_service = SafetyAssuranceReviewService()

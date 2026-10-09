"""Phase 64: Clinical Safety Risk Handoff Eligibility Service.

Validates that a recorded Phase 63 disposition is authoritative, not superseded,
and eligible for downstream handoff.
"""

from typing import Optional, Set
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_risk_review_repository import (
    SafetyRiskReviewRepository,
    get_safety_risk_review_repository,
)
from app.schemas.safety_risk_disposition import RiskDispositionRecord, RiskDispositionType
from app.schemas.safety_risk_handoff import HandoffDestinationPhase
from app.schemas.safety_risk_review import ReviewLifecycleState, SafetyRiskReviewRecord


class SafetyRiskHandoffEligibilityService:
    """Enforces eligibility criteria for converting Phase 63 dispositions into handoffs."""

    PERMITTED_DESTINATIONS_BY_DISPOSITION = {
        RiskDispositionType.INCIDENT_REVIEW_REQUIRED: {HandoffDestinationPhase.PHASE_49_INCIDENT},
        RiskDispositionType.SAFETY_LEARNING_REQUIRED: {HandoffDestinationPhase.PHASE_50_LEARNING},
        RiskDispositionType.GOVERNANCE_REVIEW_REQUIRED: {HandoffDestinationPhase.PHASE_51_GOVERNANCE},
        RiskDispositionType.ASSURANCE_REVIEW_REQUIRED: {HandoffDestinationPhase.PHASE_52_ASSURANCE},
        RiskDispositionType.CONTROLLED_ACTION_REVIEW_REQUIRED: {HandoffDestinationPhase.PHASE_54_SAFETY_ACTION},
        RiskDispositionType.EFFECTIVENESS_REVIEW_REQUIRED: {HandoffDestinationPhase.PHASE_55_EFFECTIVENESS},
        RiskDispositionType.SAFETY_IMPROVEMENT_REQUIRED: {HandoffDestinationPhase.PHASE_56_IMPROVEMENT},
        RiskDispositionType.CONTINUE_MONITORING: {HandoffDestinationPhase.PHASE_59_SURVEILLANCE},
        RiskDispositionType.REASSESSMENT_REQUIRED: {HandoffDestinationPhase.PHASE_62_REASSESSMENT},
        RiskDispositionType.MULTI_ROUTE: {
            HandoffDestinationPhase.PHASE_49_INCIDENT,
            HandoffDestinationPhase.PHASE_50_LEARNING,
            HandoffDestinationPhase.PHASE_51_GOVERNANCE,
            HandoffDestinationPhase.PHASE_52_ASSURANCE,
            HandoffDestinationPhase.PHASE_54_SAFETY_ACTION,
            HandoffDestinationPhase.PHASE_55_EFFECTIVENESS,
            HandoffDestinationPhase.PHASE_56_IMPROVEMENT,
            HandoffDestinationPhase.PHASE_59_SURVEILLANCE,
            HandoffDestinationPhase.PHASE_62_REASSESSMENT,
        },
        RiskDispositionType.NO_FURTHER_REVIEW_AT_THIS_TIME: {HandoffDestinationPhase.PHASE_59_SURVEILLANCE},
    }

    @classmethod
    def validate_disposition_eligibility(
        cls,
        review_id: str,
        disposition_id: str,
        destination_phase: Optional[HandoffDestinationPhase] = None,
        review_repo: Optional[SafetyRiskReviewRepository] = None,
    ) -> tuple[SafetyRiskReviewRecord, RiskDispositionRecord, HandoffDestinationPhase]:
        """Validate source review, recorded disposition, and destination eligibility."""
        repo = review_repo or get_safety_risk_review_repository()
        review = repo.get(review_id)
        if not review:
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_NOT_FOUND,
                message=f"Source review '{review_id}' does not exist.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Check if source review is superseded or cancelled
        if review.state in (ReviewLifecycleState.SUPERSEDED, ReviewLifecycleState.CANCELLED):
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_SUPERSEDED,
                message=f"Source review '{review_id}' is in state '{review.state.value}' and cannot generate active downstream handoffs.",
                status_code=status.HTTP_409_CONFLICT,
            )

        # Locate disposition
        matched_disp = next((d for d in review.dispositions if d.disposition_id == disposition_id), None)
        if not matched_disp:
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_NOT_FOUND,
                message=f"Disposition '{disposition_id}' not found on review '{review_id}'.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Blocked disposition check
        if matched_disp.disposition_type == RiskDispositionType.BLOCKED:
            raise AppException(
                code=ErrorCode.HANDOFF_NOT_ELIGIBLE,
                message="Disposition is marked BLOCKED. Downstream handoff is prohibited.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Determine/validate destination phase
        permitted = cls.PERMITTED_DESTINATIONS_BY_DISPOSITION.get(matched_disp.disposition_type, set())
        if not permitted:
            raise AppException(
                code=ErrorCode.HANDOFF_NOT_ELIGIBLE,
                message=f"Disposition type '{matched_disp.disposition_type.value}' is not configured for downstream action handoff.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        final_destination: HandoffDestinationPhase
        if destination_phase is not None:
            if destination_phase not in permitted:
                raise AppException(
                    code=ErrorCode.DESTINATION_NOT_ALLOWED,
                    message=f"Destination '{destination_phase.value}' is not permitted for disposition type '{matched_disp.disposition_type.value}'. Permitted: {[p.value for p in permitted]}.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            final_destination = destination_phase
        else:
            final_destination = next(iter(permitted))

        return review, matched_disp, final_destination

"""Phase 63: Clinical Safety Risk Disposition Service.

Enforces rules for recording governed risk dispositions.
Non-Negotiable Invariants:
- AI CANNOT finalize risk disposition.
- RISK DISPOSITION != RISK ACCEPTANCE (Phase 51 owns risk acceptance).
- RISK DISPOSITION != CLINICAL ACTION (Cannot diagnose, prescribe, or change treatments).
- NO_FURTHER_REVIEW_AT_THIS_TIME must NEVER be interpreted as SAFE, NO_RISK,
  RISK_ELIMINATED, RISK_ACCEPTED, or CLINICALLY_CLEAR.
"""

from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_disposition import (
    RecordDispositionRequest,
    RiskDispositionRecord,
    RiskDispositionType,
)
from app.schemas.safety_risk_review import ReviewLifecycleState, SafetyRiskReviewRecord
from app.schemas.user import AuthenticatedUserContext


class SafetyRiskDispositionService:
    """Validates and records governed risk dispositions."""

    @classmethod
    def record_disposition(
        cls,
        review: SafetyRiskReviewRecord,
        request: RecordDispositionRequest,
        user: AuthenticatedUserContext,
    ) -> RiskDispositionRecord:
        """Validate criteria and persist governed disposition."""
        # 1. AI cannot finalize risk disposition
        if request.is_ai:
            raise AppException(
                code=ErrorCode.REVIEWER_NOT_AUTHORIZED,
                message="AI cannot finalize risk disposition or declare safety outcomes. Human reviewer authorization required.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 2. State validation
        allowed_states = {
            ReviewLifecycleState.READY,
            ReviewLifecycleState.REVIEW_PENDING,
            ReviewLifecycleState.REVIEW_IN_PROGRESS,
            ReviewLifecycleState.DECISION_PENDING,
            ReviewLifecycleState.CONFLICT_REVIEW,
        }
        if review.state not in allowed_states:
            raise AppException(
                code=ErrorCode.INVALID_REVIEW_STATE,
                message=f"Review '{review.review_id}' in state '{review.state.value}' cannot accept a risk disposition. Must be in active review.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Guard against autonomous risk acceptance
        # Phase 63 cannot independently accept risk
        if "ACCEPT" in request.disposition_type.value:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DECISION_REQUIRED,
                message="Phase 63 cannot independently accept risk. Risk acceptance must be routed to Phase 51 Governance.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 4. Map resulting routes if not explicitly provided
        routes: List[str] = request.resulting_routes or []
        disp_type = request.disposition_type

        if disp_type == RiskDispositionType.INCIDENT_REVIEW_REQUIRED and "PHASE_49_INCIDENT" not in routes:
            routes.append("PHASE_49_INCIDENT")
        elif disp_type == RiskDispositionType.GOVERNANCE_REVIEW_REQUIRED and "PHASE_51_GOVERNANCE" not in routes:
            routes.append("PHASE_51_GOVERNANCE")
        elif disp_type == RiskDispositionType.ASSURANCE_REVIEW_REQUIRED and "PHASE_52_ASSURANCE" not in routes:
            routes.append("PHASE_52_ASSURANCE")
        elif disp_type == RiskDispositionType.CONTROLLED_ACTION_REVIEW_REQUIRED and "PHASE_54_SAFETY_ACTION" not in routes:
            routes.append("PHASE_54_SAFETY_ACTION")
        elif disp_type == RiskDispositionType.EFFECTIVENESS_REVIEW_REQUIRED and "PHASE_55_EFFECTIVENESS" not in routes:
            routes.append("PHASE_55_EFFECTIVENESS")
        elif disp_type == RiskDispositionType.SAFETY_LEARNING_REQUIRED and "PHASE_50_LEARNING" not in routes:
            routes.append("PHASE_50_LEARNING")
        elif disp_type == RiskDispositionType.SAFETY_IMPROVEMENT_REQUIRED and "PHASE_56_IMPROVEMENT" not in routes:
            routes.append("PHASE_56_IMPROVEMENT")
        elif disp_type == RiskDispositionType.CONTINUE_MONITORING and "PHASE_59_SURVEILLANCE" not in routes:
            routes.append("PHASE_59_SURVEILLANCE")
        elif disp_type == RiskDispositionType.REASSESSMENT_REQUIRED and "PHASE_62_REASSESSMENT" not in routes:
            routes.append("PHASE_62_REASSESSMENT")

        # Create record
        record = RiskDispositionRecord(
            review_id=review.review_id,
            disposition_type=disp_type,
            authorized_by=user.user_id,
            authorizer_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            reasoning=request.reasoning,
            resulting_routes=routes,
            prohibited_claims_acknowledged=True,
            metadata=request.metadata or {},
        )

        review.dispositions.append(record)
        review.current_disposition = disp_type

        # Update review lifecycle state
        if routes:
            review.state = ReviewLifecycleState.ROUTING_REQUIRED
        elif disp_type == RiskDispositionType.NO_FURTHER_REVIEW_AT_THIS_TIME:
            review.state = ReviewLifecycleState.COMPLETED
            review.completed_at = record.recorded_at
        elif disp_type == RiskDispositionType.BLOCKED:
            review.state = ReviewLifecycleState.BLOCKED
        elif disp_type == RiskDispositionType.REASSESSMENT_REQUIRED:
            review.state = ReviewLifecycleState.REASSESSMENT_REQUIRED
            review.requires_reassessment = True
        else:
            review.state = ReviewLifecycleState.DISPOSITION_RECORDED

        return record

"""Phase 62: Safety Risk Review Service.

Governs human review workflows for consolidated cross-domain safety risk assessments.
Enforces non-negotiable architectural boundaries: AI cannot approve assessments or declare safety.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    HumanRiskReviewDecision,
    RiskAssessmentReviewRecord,
    RiskRoutingDestination,
    SafetyRiskAssessmentRecord,
)


class SafetyRiskReviewService:
    """Manages human review verification and disposition of consolidated risk assessments."""

    def submit_review(
        self,
        assessment: SafetyRiskAssessmentRecord,
        reviewer_id: str,
        reviewer_role: str,
        decision: HumanRiskReviewDecision,
        reason: str,
        resulting_routes: Optional[List[RiskRoutingDestination]] = None,
        is_ai: bool = False,
    ) -> RiskAssessmentReviewRecord:
        """Record human review decision enforcing AI restriction and state transitions."""
        # 1. Non-negotiable AI boundary check
        if is_ai:
            raise AppException(
                code=ErrorCode.CLINICAL_ACTION_RESTRICTED,
                message="AI agents cannot approve safety risk assessments, resolve evidence conflicts, or declare system safety autonomously.",
                status_code=403,
            )

        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_EVIDENCE,
                message="A substantive clinical safety justification is required for risk assessment review.",
                status_code=400,
            )

        routes = resulting_routes or []

        # Determine target destinations based on review decision
        if decision == HumanRiskReviewDecision.ROUTE_TO_INCIDENT:
            routes.append(RiskRoutingDestination.PHASE_49_INCIDENT_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_ASSURANCE:
            routes.append(RiskRoutingDestination.PHASE_52_ASSURANCE_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_EFFECTIVENESS:
            routes.append(RiskRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_GOVERNANCE:
            routes.append(RiskRoutingDestination.PHASE_51_GOVERNANCE_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_ACTION:
            routes.append(RiskRoutingDestination.PHASE_54_CONTROLLED_ACTION_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_LEARNING:
            routes.append(RiskRoutingDestination.PHASE_50_SAFETY_LEARNING)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_IMPROVEMENT:
            routes.append(RiskRoutingDestination.PHASE_56_SAFETY_IMPROVEMENT)
        elif decision == HumanRiskReviewDecision.REASSESS:
            routes.append(RiskRoutingDestination.PHASE_60_REASSESSMENT)
        elif decision == HumanRiskReviewDecision.CONTINUE_MONITORING:
            routes.append(RiskRoutingDestination.CONTINUE_MONITORING)

        review_rec = RiskAssessmentReviewRecord(
            reviewed_by=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            reason=reason,
            resulting_routes=list(set(routes)),
            reviewed_at=datetime.now(timezone.utc),
            is_ai_agent=False,
        )

        assessment.reviews.append(review_rec)
        assessment.requires_human_review = False

        # Transition lifecycle state based on review outcome
        if decision == HumanRiskReviewDecision.REJECT_RISK_CHARACTERIZATION:
            assessment.lifecycle_state = AssessmentLifecycleState.FAILED
        elif decision == HumanRiskReviewDecision.ESCALATE:
            assessment.lifecycle_state = AssessmentLifecycleState.ESCALATION_REQUIRED
            assessment.requires_escalation = True
        elif decision == HumanRiskReviewDecision.REASSESS:
            assessment.lifecycle_state = AssessmentLifecycleState.REASSESSMENT_REQUIRED
            assessment.requires_reassessment = True
        else:
            if routes:
                assessment.lifecycle_state = AssessmentLifecycleState.ROUTED
            else:
                assessment.lifecycle_state = AssessmentLifecycleState.RESOLVED

        return review_rec


_risk_review_service: Optional[SafetyRiskReviewService] = None


def get_safety_risk_review_service() -> SafetyRiskReviewService:
    global _risk_review_service
    if _risk_review_service is None:
        _risk_review_service = SafetyRiskReviewService()
    return _risk_review_service

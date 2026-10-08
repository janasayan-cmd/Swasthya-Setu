"""Phase 61: Safety Analytics Review Service.

Governs human review workflows for longitudinal safety surveillance analytics.
Enforces non-negotiable architectural boundaries: AI cannot approve reviews or declare safety.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_analytics import (
    AnalysisLifecycleState,
    AnalyticsReviewRecord,
    AnalyticsRoutingDestination,
    HumanAnalyticsReviewDecision,
    RiskIndicatorLifecycleState,
    SafetyAnalysisRecord,
)


class SafetyAnalyticsReviewService:
    """Manages human review verification and disposition of analytical findings."""

    def submit_review(
        self,
        analysis: SafetyAnalysisRecord,
        reviewer_id: str,
        reviewer_role: str,
        decision: HumanAnalyticsReviewDecision,
        reason: str,
        resulting_routes: Optional[List[AnalyticsRoutingDestination]] = None,
        is_ai: bool = False,
    ) -> AnalyticsReviewRecord:
        """Record human review decision enforcing AI restriction and state transitions."""
        # 1. Non-negotiable AI boundary check
        if is_ai:
            raise AppException(
                code=ErrorCode.CLINICAL_ACTION_RESTRICTED,
                message="AI agents cannot approve safety surveillance reviews, declare findings false, or resolve risk indicators autonomously.",
                status_code=403,
            )

        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_DATA,
                message="A substantive justification is required for human surveillance review.",
                status_code=400,
            )

        routes = resulting_routes or []

        # Determine target destinations based on review decision
        if decision == HumanAnalyticsReviewDecision.ROUTE_TO_INCIDENT:
            routes.append(AnalyticsRoutingDestination.PHASE_49_INCIDENT_REVIEW)
        elif decision == HumanAnalyticsReviewDecision.ROUTE_TO_ASSURANCE:
            routes.append(AnalyticsRoutingDestination.PHASE_52_ASSURANCE_REVIEW)
        elif decision == HumanAnalyticsReviewDecision.ROUTE_TO_EFFECTIVENESS:
            routes.append(AnalyticsRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW)
        elif decision == HumanAnalyticsReviewDecision.ROUTE_TO_GOVERNANCE:
            routes.append(AnalyticsRoutingDestination.PHASE_51_GOVERNANCE_REVIEW)
        elif decision == HumanAnalyticsReviewDecision.ROUTE_TO_ACTION:
            routes.append(AnalyticsRoutingDestination.PHASE_54_CONTROLLED_ACTION_REVIEW)
        elif decision == HumanAnalyticsReviewDecision.REASSESS:
            routes.append(AnalyticsRoutingDestination.PHASE_60_REASSESSMENT)
        elif decision == HumanAnalyticsReviewDecision.CONTINUE_MONITORING:
            routes.append(AnalyticsRoutingDestination.CONTINUE_MONITORING)

        review_rec = AnalyticsReviewRecord(
            reviewed_by=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            reason=reason,
            resulting_routes=list(set(routes)),
            reviewed_at=datetime.now(timezone.utc),
            is_ai_agent=False,
        )

        analysis.reviews.append(review_rec)
        analysis.requires_human_review = False

        # Transition lifecycle state based on decision
        if decision == HumanAnalyticsReviewDecision.REJECT_ANALYSIS:
            analysis.lifecycle_state = AnalysisLifecycleState.FAILED
            for ind in analysis.risk_indicators:
                ind.lifecycle_state = RiskIndicatorLifecycleState.REJECTED
        elif decision == HumanAnalyticsReviewDecision.ESCALATE:
            analysis.lifecycle_state = AnalysisLifecycleState.ESCALATION_REQUIRED
            analysis.requires_escalation = True
            for ind in analysis.risk_indicators:
                ind.lifecycle_state = RiskIndicatorLifecycleState.ESCALATION_REQUIRED
        elif decision == HumanAnalyticsReviewDecision.REASSESS:
            analysis.lifecycle_state = AnalysisLifecycleState.REASSESSMENT_REQUIRED
            analysis.requires_reassessment = True
            for ind in analysis.risk_indicators:
                ind.lifecycle_state = RiskIndicatorLifecycleState.REASSESSMENT_REQUIRED
        else:
            if routes:
                analysis.lifecycle_state = AnalysisLifecycleState.ROUTED
            else:
                analysis.lifecycle_state = AnalysisLifecycleState.COMPLETED

            for ind in analysis.risk_indicators:
                ind.lifecycle_state = RiskIndicatorLifecycleState.RESOLVED

        return review_rec


_review_service: Optional[SafetyAnalyticsReviewService] = None


def get_safety_analytics_review_service() -> SafetyAnalyticsReviewService:
    global _review_service
    if _review_service is None:
        _review_service = SafetyAnalyticsReviewService()
    return _review_service

"""Phase 62: Safety Risk Routing Service.

Dispatches consolidated risk assessments to authoritative downstream phases
(Phase 49 Incident, Phase 51 Governance, Phase 52 Assurance, Phase 55 Effectiveness,
Phase 54 Action, Phase 60 Reassessment, Phase 61 Reanalysis).
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    RiskAssessmentRoutingRecord,
    RiskRoutingDestination,
    SafetyRiskAssessmentRecord,
)

RISK_DESTINATION_PHASE_MAP = {
    RiskRoutingDestination.PHASE_60_REASSESSMENT: "PHASE_60_SIGNAL_TRIAGE",
    RiskRoutingDestination.PHASE_61_REANALYSIS: "PHASE_61_SURVEILLANCE_ANALYTICS",
    RiskRoutingDestination.PHASE_59_SURVEILLANCE: "PHASE_59_SURVEILLANCE",
    RiskRoutingDestination.PHASE_49_INCIDENT_REVIEW: "PHASE_49_INCIDENT_MANAGEMENT",
    RiskRoutingDestination.PHASE_52_ASSURANCE_REVIEW: "PHASE_52_SAFETY_ASSURANCE",
    RiskRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW: "PHASE_55_ACTION_EFFECTIVENESS",
    RiskRoutingDestination.PHASE_51_GOVERNANCE_REVIEW: "PHASE_51_SAFETY_GOVERNANCE",
    RiskRoutingDestination.PHASE_54_CONTROLLED_ACTION_REVIEW: "PHASE_54_SAFETY_ACTION",
    RiskRoutingDestination.PHASE_50_SAFETY_LEARNING: "PHASE_50_SAFETY_LEARNING",
    RiskRoutingDestination.PHASE_56_SAFETY_IMPROVEMENT: "PHASE_56_SAFETY_IMPROVEMENT",
    RiskRoutingDestination.CONTINUE_MONITORING: "CONTINUOUS_MONITORING",
    RiskRoutingDestination.HUMAN_REVIEW: "CLINICAL_SAFETY_COMMITTEE",
}


class SafetyRiskRoutingService:
    """Executes governed routing and multi-routing of consolidated risk assessments."""

    def execute_routing(
        self,
        assessment: SafetyRiskAssessmentRecord,
        destinations: List[RiskRoutingDestination],
        actor_id: str,
        reason: str,
        target_reference: Optional[str] = None,
    ) -> List[RiskAssessmentRoutingRecord]:
        """Dispatch risk assessment to one or multiple authoritative destinations."""
        if not destinations:
            raise AppException(
                code=ErrorCode.ROUTING_FAILED,
                message="At least one valid routing destination must be provided.",
                status_code=400,
            )

        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_EVIDENCE,
                message="A substantive clinical reason must be provided for risk assessment routing.",
                status_code=400,
            )

        records: List[RiskAssessmentRoutingRecord] = []
        now = datetime.now(timezone.utc)

        for dst in destinations:
            target_phase = RISK_DESTINATION_PHASE_MAP.get(dst, "PHASE_UNKNOWN")
            rec = RiskAssessmentRoutingRecord(
                destination=dst,
                status="ROUTED",
                routed_by=actor_id,
                reason=reason,
                routed_at=now,
                target_reference=target_reference or assessment.assessment_id,
                target_phase=target_phase,
            )
            assessment.routings.append(rec)
            records.append(rec)

        assessment.lifecycle_state = AssessmentLifecycleState.ROUTED
        assessment.requires_human_review = False
        assessment.requires_escalation = False

        return records

    def route_review(
        self,
        review: Any,
        destinations: List[Any],
        actor_id: str,
        reason: str,
        target_reference: Optional[str] = None,
    ) -> List[Any]:
        """Dispatch governed risk review to one or multiple authoritative downstream phases (Phase 63)."""
        from app.schemas.safety_risk_review import ReviewLifecycleState
        from app.schemas.safety_routing import RiskRoutingRecord, RoutingDestination

        if not destinations:
            raise AppException(
                code=ErrorCode.ROUTING_FAILED,
                message="At least one valid routing destination must be provided.",
                status_code=400,
            )

        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_EVIDENCE,
                message="A substantive clinical reasoning must be provided for risk review routing.",
                status_code=400,
            )

        records: List[RiskRoutingRecord] = []
        now = datetime.now(timezone.utc)

        for dst in destinations:
            rec = RiskRoutingRecord(
                review_id=review.review_id,
                destination=dst if isinstance(dst, RoutingDestination) else RoutingDestination(str(dst)),
                reason=reason,
                target_reference=target_reference or review.review_id,
                routed_by=actor_id,
                routed_at=now,
                status="ROUTED",
            )
            review.routings.append(rec)
            records.append(rec)

        # Update review lifecycle state
        if any(d in (RoutingDestination.PHASE_59_SURVEILLANCE, "PHASE_59_SURVEILLANCE") for d in destinations):
            review.state = ReviewLifecycleState.MONITORING
        elif any(d in (RoutingDestination.PHASE_62_REASSESSMENT, "PHASE_62_REASSESSMENT") for d in destinations):
            review.state = ReviewLifecycleState.REASSESSMENT_REQUIRED
            review.requires_reassessment = True
        else:
            review.state = ReviewLifecycleState.ROUTED

        return records


_risk_routing_service: Optional[SafetyRiskRoutingService] = None


def get_safety_risk_routing_service() -> SafetyRiskRoutingService:
    global _risk_routing_service
    if _risk_routing_service is None:
        _risk_routing_service = SafetyRiskRoutingService()
    return _risk_routing_service


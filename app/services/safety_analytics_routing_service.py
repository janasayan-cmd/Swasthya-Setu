"""Phase 61: Safety Analytics Routing Service.

Routes governed analytical findings and emerging risk indicators to authoritative
phases (Phase 49 Incident, Phase 51 Governance, Phase 52 Assurance, Phase 55 Effectiveness,
Phase 54 Action, Phase 60 Reassessment).
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_analytics import (
    AnalysisLifecycleState,
    AnalyticsRoutingDestination,
    AnalyticsRoutingRecord,
    RiskIndicatorLifecycleState,
    SafetyAnalysisRecord,
)

DESTINATION_PHASE_MAP = {
    AnalyticsRoutingDestination.PHASE_60_REASSESSMENT: "PHASE_60_SIGNAL_TRIAGE",
    AnalyticsRoutingDestination.PHASE_59_SURVEILLANCE: "PHASE_59_SURVEILLANCE",
    AnalyticsRoutingDestination.PHASE_49_INCIDENT_REVIEW: "PHASE_49_INCIDENT_MANAGEMENT",
    AnalyticsRoutingDestination.PHASE_52_ASSURANCE_REVIEW: "PHASE_52_SAFETY_ASSURANCE",
    AnalyticsRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW: "PHASE_55_ACTION_EFFECTIVENESS",
    AnalyticsRoutingDestination.PHASE_51_GOVERNANCE_REVIEW: "PHASE_51_SAFETY_GOVERNANCE",
    AnalyticsRoutingDestination.PHASE_54_CONTROLLED_ACTION_REVIEW: "PHASE_54_SAFETY_ACTION",
    AnalyticsRoutingDestination.PHASE_50_SAFETY_LEARNING: "PHASE_50_SAFETY_LEARNING",
    AnalyticsRoutingDestination.PHASE_56_SAFETY_IMPROVEMENT: "PHASE_56_SAFETY_IMPROVEMENT",
    AnalyticsRoutingDestination.CONTINUE_MONITORING: "CONTINUOUS_MONITORING",
    AnalyticsRoutingDestination.HUMAN_REVIEW: "CLINICAL_SAFETY_COMMITTEE",
}


class SafetyAnalyticsRoutingService:
    """Executes governed routing and multi-routing of analytical findings."""

    def execute_routing(
        self,
        analysis: SafetyAnalysisRecord,
        destinations: List[AnalyticsRoutingDestination],
        actor_id: str,
        reason: str,
        target_reference: Optional[str] = None,
    ) -> List[AnalyticsRoutingRecord]:
        """Dispatch analytical findings to one or multiple authoritative destinations."""
        if not destinations:
            raise AppException(
                code=ErrorCode.ROUTING_FAILED,
                message="At least one valid routing destination must be provided.",
                status_code=400,
            )

        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_DATA,
                message="Routing reason and clinical safety context must be provided.",
                status_code=400,
            )

        records: List[AnalyticsRoutingRecord] = []
        now = datetime.now(timezone.utc)

        for dst in destinations:
            target_phase = DESTINATION_PHASE_MAP.get(dst, "PHASE_UNKNOWN")
            rec = AnalyticsRoutingRecord(
                destination=dst,
                status="ROUTED",
                routed_by=actor_id,
                reason=reason,
                routed_at=now,
                target_reference=target_reference or analysis.analysis_id,
                target_phase=target_phase,
            )
            analysis.routings.append(rec)
            records.append(rec)

        analysis.lifecycle_state = AnalysisLifecycleState.ROUTED
        analysis.requires_human_review = False
        analysis.requires_escalation = False

        for ind in analysis.risk_indicators:
            ind.lifecycle_state = RiskIndicatorLifecycleState.ROUTED

        return records


_routing_service: Optional[SafetyAnalyticsRoutingService] = None


def get_safety_analytics_routing_service() -> SafetyAnalyticsRoutingService:
    global _routing_service
    if _routing_service is None:
        _routing_service = SafetyAnalyticsRoutingService()
    return _routing_service

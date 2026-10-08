"""Phase 61: Safety Risk Indicator Service.

Generates governed emerging risk indicators from analytical patterns,
trends, recurrences, and concentrations.
Architectural invariant: A risk indicator means 'the evidence warrants governed attention' — not confirmed risk.
"""

from typing import List, Optional

from app.schemas.safety_analytics import (
    AnalyticalUncertaintyState,
    AnalyticsRoutingDestination,
    ConcentrationFinding,
    PatternClass,
    RecurrenceFinding,
    RecurrenceState,
    RiskIndicatorLifecycleState,
    RiskIndicatorType,
    SafetyPatternFinding,
    SafetyRiskIndicatorFinding,
    TrendDirection,
    TrendFinding,
)


class SafetyRiskIndicatorService:
    """Evaluates surveillance findings into governed risk indicators."""

    def evaluate_risk_indicators(
        self,
        patterns: List[SafetyPatternFinding],
        trends: List[TrendFinding],
        recurrences: List[RecurrenceFinding],
        concentrations: List[ConcentrationFinding],
    ) -> List[SafetyRiskIndicatorFinding]:
        """Synthesize analytical findings into governed emerging risk indicators."""
        indicators: List[SafetyRiskIndicatorFinding] = []

        # 1. Safety Control Degradation Indicator (from Repeated Failure or Control Cluster)
        control_patterns = [
            p
            for p in patterns
            if p.pattern_class in (PatternClass.REPEATED_FAILURE, PatternClass.SAFETY_CONTROL_CLUSTER)
        ]
        if control_patterns:
            all_sigs = []
            for p in control_patterns:
                all_sigs.extend(p.source_signal_ids)

            indicators.append(
                SafetyRiskIndicatorFinding(
                    indicator_type=RiskIndicatorType.SAFETY_CONTROL_DEGRADATION,
                    lifecycle_state=RiskIndicatorLifecycleState.DETECTED,
                    governed_severity="HIGH",
                    confidence=0.9,
                    uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                    warrants_governed_attention=True,
                    associated_pattern_ids=[p.pattern_id for p in control_patterns],
                    associated_signal_ids=list(set(all_sigs)),
                    recommended_routes=[
                        AnalyticsRoutingDestination.PHASE_52_ASSURANCE_REVIEW,
                        AnalyticsRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW,
                        AnalyticsRoutingDestination.PHASE_51_GOVERNANCE_REVIEW,
                    ],
                    requires_human_review=True,
                    notes="Repeated control failures warrant Phase 52 assurance review and Phase 55 effectiveness review.",
                )
            )

        # 2. Increasing Failure Rate Indicator (from Trend Findings)
        increasing_trends = [
            t
            for t in trends
            if t.direction in (TrendDirection.INCREASING, TrendDirection.SPIKE)
            and "high_severity" in t.metric_name
        ]
        if increasing_trends:
            indicators.append(
                SafetyRiskIndicatorFinding(
                    indicator_type=RiskIndicatorType.INCREASING_FAILURE_RATE,
                    lifecycle_state=RiskIndicatorLifecycleState.DETECTED,
                    governed_severity="HIGH",
                    confidence=0.85,
                    uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                    warrants_governed_attention=True,
                    associated_pattern_ids=[],
                    associated_signal_ids=[],
                    recommended_routes=[
                        AnalyticsRoutingDestination.HUMAN_REVIEW,
                        AnalyticsRoutingDestination.PHASE_51_GOVERNANCE_REVIEW,
                    ],
                    requires_human_review=True,
                    notes="Upward rate trend in high-severity surveillance signals observed.",
                )
            )

        # 3. Post-Change Regression Pattern Indicator
        post_change_patterns = [p for p in patterns if p.pattern_class == PatternClass.POST_CHANGE_PATTERN]
        if post_change_patterns:
            all_sigs = []
            for p in post_change_patterns:
                all_sigs.extend(p.source_signal_ids)

            indicators.append(
                SafetyRiskIndicatorFinding(
                    indicator_type=RiskIndicatorType.POST_CHANGE_REGRESSION_PATTERN,
                    lifecycle_state=RiskIndicatorLifecycleState.DETECTED,
                    governed_severity="HIGH",
                    confidence=0.85,
                    uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                    warrants_governed_attention=True,
                    associated_pattern_ids=[p.pattern_id for p in post_change_patterns],
                    associated_signal_ids=list(set(all_sigs)),
                    recommended_routes=[
                        AnalyticsRoutingDestination.PHASE_60_REASSESSMENT,
                        AnalyticsRoutingDestination.PHASE_51_GOVERNANCE_REVIEW,
                    ],
                    requires_human_review=True,
                    notes="Surveillance signals concentrated post-rollout require change reassessment.",
                )
            )

        # 4. Facility Concentrated Pattern Indicator
        disprop_conc = [c for c in concentrations if c.is_disproportionate and c.dimension == "FACILITY"]
        if disprop_conc:
            top_fac = disprop_conc[0].concentrated_key
            indicators.append(
                SafetyRiskIndicatorFinding(
                    indicator_type=RiskIndicatorType.FACILITY_CONCENTRATED_PATTERN,
                    lifecycle_state=RiskIndicatorLifecycleState.DETECTED,
                    governed_severity="MODERATE",
                    confidence=0.8,
                    uncertainty=AnalyticalUncertaintyState.MODERATE_UNCERTAINTY,
                    warrants_governed_attention=True,
                    associated_pattern_ids=[],
                    associated_signal_ids=[],
                    recommended_routes=[AnalyticsRoutingDestination.HUMAN_REVIEW],
                    requires_human_review=True,
                    notes=f"Disproportionate signal concentration observed at facility {top_fac} (distribution finding, not causality).",
                )
            )

        # 5. Repeated High Severity Signal Indicator (from Recurrence)
        high_recurrence = [
            r
            for r in recurrences
            if r.state in (RecurrenceState.HIGH_RECURRENCE, RecurrenceState.RECURRENT)
        ]
        if high_recurrence:
            all_sigs = []
            for r in high_recurrence:
                all_sigs.extend(r.signal_ids)

            indicators.append(
                SafetyRiskIndicatorFinding(
                    indicator_type=RiskIndicatorType.REPEATED_HIGH_SEVERITY_SIGNAL,
                    lifecycle_state=RiskIndicatorLifecycleState.DETECTED,
                    governed_severity="HIGH",
                    confidence=0.9,
                    uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                    warrants_governed_attention=True,
                    associated_pattern_ids=[],
                    associated_signal_ids=list(set(all_sigs)),
                    recommended_routes=[
                        AnalyticsRoutingDestination.PHASE_49_INCIDENT_REVIEW,
                        AnalyticsRoutingDestination.PHASE_52_ASSURANCE_REVIEW,
                    ],
                    requires_human_review=True,
                    notes="Materially recurrent signals meet criteria for Phase 49 incident review and Phase 52 assurance review.",
                )
            )

        return indicators


_risk_indicator_service: Optional[SafetyRiskIndicatorService] = None


def get_safety_risk_indicator_service() -> SafetyRiskIndicatorService:
    global _risk_indicator_service
    if _risk_indicator_service is None:
        _risk_indicator_service = SafetyRiskIndicatorService()
    return _risk_indicator_service

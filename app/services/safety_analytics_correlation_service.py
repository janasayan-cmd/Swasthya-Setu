"""Phase 61: Safety Analytics Correlation Service.

Evaluates cross-signal correlation across operational and architectural dimensions.
Mandatory architectural rule: Correlation does not equal causation.
"""

from typing import List, Optional

from app.schemas.safety_analytics import (
    AnalyticalUncertaintyState,
    CorrelationFinding,
    CorrelationState,
    EligibleSignalReference,
)


class SafetyAnalyticsCorrelationService:
    """Detects pairwise and cross-signal correlations on common operational attributes."""

    def evaluate_correlations(
        self, signals: List[EligibleSignalReference]
    ) -> List[CorrelationFinding]:
        """Correlate signals sharing operational attributes."""
        if len(signals) < 2:
            return []

        findings: List[CorrelationFinding] = []

        # Compare adjacent or paired signals up to a bounded limit
        for i in range(len(signals)):
            for j in range(i + 1, min(i + 4, len(signals))):
                sig_a = signals[i]
                sig_b = signals[j]

                shared_dimensions: List[str] = []

                # 1. Safety Control
                ctrl_a = sig_a.metadata.get("safety_control_id") or sig_a.provenance.get("safety_control_id")
                ctrl_b = sig_b.metadata.get("safety_control_id") or sig_b.provenance.get("safety_control_id")
                if ctrl_a and ctrl_b and ctrl_a == ctrl_b:
                    shared_dimensions.append(f"SAFETY_CONTROL({ctrl_a})")

                # 2. Workflow
                wf_a = sig_a.metadata.get("workflow") or sig_a.provenance.get("workflow")
                wf_b = sig_b.metadata.get("workflow") or sig_b.provenance.get("workflow")
                if wf_a and wf_b and wf_a == wf_b:
                    shared_dimensions.append(f"WORKFLOW({wf_a})")

                # 3. Version
                if sig_a.version and sig_b.version and sig_a.version == sig_b.version:
                    shared_dimensions.append(f"VERSION({sig_a.version})")

                # 4. Classification
                if sig_a.classification == sig_b.classification:
                    shared_dimensions.append(f"CLASSIFICATION({sig_a.classification})")

                if len(shared_dimensions) >= 2:
                    findings.append(
                        CorrelationFinding(
                            signal_a_id=sig_a.signal_id,
                            signal_b_id=sig_b.signal_id,
                            dimension=",".join(shared_dimensions),
                            state=CorrelationState.CORRELATED,
                            confidence=0.9,
                            uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                            evidence_summary=f"Signals share attributes: {', '.join(shared_dimensions)}",
                            analytical_note="Correlation indicates shared operational attributes and does not prove causation.",
                        )
                    )
                elif len(shared_dimensions) == 1:
                    findings.append(
                        CorrelationFinding(
                            signal_a_id=sig_a.signal_id,
                            signal_b_id=sig_b.signal_id,
                            dimension=shared_dimensions[0],
                            state=CorrelationState.POSSIBLY_CORRELATED,
                            confidence=0.7,
                            uncertainty=AnalyticalUncertaintyState.MODERATE_UNCERTAINTY,
                            evidence_summary=f"Signals share single attribute: {shared_dimensions[0]}",
                            analytical_note="Correlation indicates shared operational attributes and does not prove causation.",
                        )
                    )

        return findings


_correlation_service: Optional[SafetyAnalyticsCorrelationService] = None


def get_safety_analytics_correlation_service() -> SafetyAnalyticsCorrelationService:
    global _correlation_service
    if _correlation_service is None:
        _correlation_service = SafetyAnalyticsCorrelationService()
    return _correlation_service

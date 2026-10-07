"""Phase 53: Safety Report Aggregation Service.

Consolidates Phase 52 assurance evaluations into safe, bounded
report distributions. Enforces that missing data is not ignored
and metrics are not improperly combined.
"""

from typing import List, Tuple

from app.schemas.safety_assurance import (
    AssuranceEvaluationRecord,
    ControlEffectivenessState,
    EvidenceQualityState,
)
from app.schemas.safety_report import (
    ControlAssuranceDistribution,
    ControlFinding,
    SafetyReportQualityState,
)


class SafetyReportAggregationService:
    """Aggregates assurance findings into report distributions safely."""

    def aggregate_evaluations(
        self, evaluations: List[AssuranceEvaluationRecord]
    ) -> Tuple[ControlAssuranceDistribution, List[ControlFinding]]:
        """
        Aggregate Phase 52 evaluations into a report distribution and finding list.
        
        This explicitly groups effectiveness states and builds normalized findings.
        It does NOT produce a global "HealthSetu is X% safe" claim.
        """
        distribution = ControlAssuranceDistribution()
        findings: List[ControlFinding] = []

        for eval_record in evaluations:
            # Update distribution
            distribution.total_controls_evaluated += 1
            
            state = eval_record.effectiveness_state
            if state == ControlEffectivenessState.EFFECTIVE_OBSERVED:
                distribution.effective_observed += 1
            elif state == ControlEffectivenessState.PARTIALLY_EFFECTIVE:
                distribution.partially_effective += 1
            elif state == ControlEffectivenessState.DEGRADED:
                distribution.degraded += 1
            elif state == ControlEffectivenessState.FAILED:
                distribution.failed += 1
            elif state == ControlEffectivenessState.INSUFFICIENT_EVIDENCE:
                distribution.insufficient_evidence += 1
            elif state == ControlEffectivenessState.EFFECTIVENESS_UNCLEAR:
                distribution.effectiveness_unclear += 1
            elif state == ControlEffectivenessState.REQUIRES_REASSESSMENT:
                distribution.requires_reassessment += 1
                
            # Create a finding
            findings.append(
                ControlFinding(
                    control_id=eval_record.control_id,
                    control_version=eval_record.control_version,
                    control_category=eval_record.control_category,
                    effectiveness_state=eval_record.effectiveness_state,
                    degradation_state=eval_record.degradation_state,
                    evidence_quality=eval_record.evidence_quality,
                    evaluation_id=eval_record.evaluation_id,
                    bypass_count=eval_record.bypass_count,
                    regression_detected=eval_record.regression_detected,
                )
            )

        return distribution, findings

    def assess_report_quality(self, findings: List[ControlFinding]) -> SafetyReportQualityState:
        """
        Determine the overall evidence quality of the consolidated report.
        This represents the strength of the evidence, NOT clinical safety.
        """
        if not findings:
            return SafetyReportQualityState.INSUFFICIENT_EVIDENCE
            
        qualities = [f.evidence_quality for f in findings]
        
        if EvidenceQualityState.CONFLICTED in qualities:
            return SafetyReportQualityState.CONFLICTED_EVIDENCE
            
        if EvidenceQualityState.STALE in qualities:
            return SafetyReportQualityState.STALE_EVIDENCE
            
        # If there are any missing or invalid sources
        if any(q in (EvidenceQualityState.MISSING, EvidenceQualityState.INVALID, EvidenceQualityState.INSUFFICIENT) for q in qualities):
            return SafetyReportQualityState.INSUFFICIENT_EVIDENCE
            
        if EvidenceQualityState.PARTIAL in qualities:
            return SafetyReportQualityState.PARTIAL_EVIDENCE
            
        if EvidenceQualityState.UNVERIFIED in qualities:
            return SafetyReportQualityState.UNVERIFIED_EVIDENCE
            
        # If all are COMPLETE, it's high confidence
        if all(q == EvidenceQualityState.COMPLETE for q in qualities):
            return SafetyReportQualityState.HIGH_CONFIDENCE_EVIDENCE
            
        return SafetyReportQualityState.SUFFICIENT_EVIDENCE


# Global singleton
safety_report_aggregation_service = SafetyReportAggregationService()

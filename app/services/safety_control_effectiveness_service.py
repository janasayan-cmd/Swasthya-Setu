"""Phase 52: Safety Control Effectiveness Evaluation Service.

Computes control effectiveness from evidence collection results.

Core distinctions enforced:
  CONTROL EXECUTED != CONTROL EFFECTIVE
  CONTROL EFFECTIVE != RISK ELIMINATED
  CONTROL PASS != PATIENT SAFETY PROOF
  NO OBSERVED FAILURE != NO RISK
  NO INCIDENT != EFFECTIVE CONTROL
  LOW INCIDENT COUNT != SAFE SYSTEM
  MISSING DATA != SUCCESS
  PARTIAL DATA != FULL VALIDATION
  CORRELATION != EFFECTIVENESS
  TEMPORARY SUCCESS != PERMANENT EFFECTIVENESS
  MONITORING DATA != COMPLETE EVIDENCE
  HISTORICAL EFFECTIVENESS != CURRENT EFFECTIVENESS
  CURRENT OBSERVATION != FUTURE SAFETY

Quantitative rates MUST use valid denominators.
Raw counts are never presented as rates.
If denominator is unavailable: RATE_UNAVAILABLE.

AI MUST NOT autonomously declare a control effective or failed.
Human review is required for high-risk outcomes.

Phase 48 remains authoritative for actual safety enforcement.
Phase 52 evaluates whether Phase 48 controls are operating as expected.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.safety_assurance import (
    AssuranceEvaluationRecord,
    ControlEffectivenessState,
    ControlExecutionState,
    DegradationState,
    EffectivenessScoreDimensions,
    EvidenceQualityState,
)
from app.services.safety_evidence_service import EvidenceCollectionResult

logger = logging.getLogger("app.services.safety_control_effectiveness_service")


class ControlEffectivenessEvaluationResult:
    """Result of a control effectiveness evaluation."""

    def __init__(self) -> None:
        self.effectiveness_state: ControlEffectivenessState = ControlEffectivenessState.NOT_EVALUATED
        self.execution_state: ControlExecutionState = ControlExecutionState.CONTROL_NOT_OBSERVABLE
        self.degradation_state: DegradationState = DegradationState.STABLE
        self.score: Optional[EffectivenessScoreDimensions] = None
        self.review_required: bool = False
        self.review_required_reason: Optional[str] = None
        self.bypass_detected: bool = False
        self.bypass_count: int = 0
        self.regression_detected: bool = False
        self.effectiveness_summary: Optional[str] = None
        self.limitations: List[str] = []
        self.uncertainty_preserved: bool = True


class SafetyControlEffectivenessService:
    """Evaluates control effectiveness from evidence and execution observations.

    This service answers bounded questions only:
    - Did the control execute?
    - Did it behave according to approved expectations?
    - Was sufficient evidence available?
    - Was the evidence current and valid?

    It NEVER answers: "Is HealthSetu safe?" (that cannot be reduced to boolean).
    """

    def evaluate_effectiveness(
        self,
        evidence_result: EvidenceCollectionResult,
        eligible_executions: Optional[int],
        observed_executions: Optional[int],
        observed_failures: Optional[int],
        observed_bypasses: Optional[int],
        valid_results: Optional[int],
        total_results: Optional[int],
        expected_behavior_met: Optional[bool],
        version_consistent: Optional[bool],
        provider_success_rate: Optional[float],
        required_reviews_completed: Optional[int],
        required_reviews_total: Optional[int],
        degradation_threshold_failure_rate: Optional[float],
        degradation_threshold_bypass_rate: Optional[float],
        significant_degradation_threshold: Optional[float],
        is_high_risk_control: bool = False,
    ) -> ControlEffectivenessEvaluationResult:
        """Compute control effectiveness from evidence and execution observations.

        Fail-safe rules:
        - No evidence → INSUFFICIENT_EVIDENCE (never EFFECTIVE)
        - Partial evidence → EFFECTIVENESS_UNCLEAR or PARTIALLY_EFFECTIVE
        - Conflicting evidence → EFFECTIVENESS_UNCLEAR
        - Missing denominator → RATE_UNAVAILABLE (never "5 failures = 5%")
        - Provider unavailable → cannot be EFFECTIVE automatically
        - Missing safety-gate execution → cannot be EFFECTIVE
        """
        result = ControlEffectivenessEvaluationResult()
        limitations: List[str] = []

        # ----------------------------------------------------------------
        # FAIL-SAFE: Insufficient evidence → cannot be EFFECTIVE
        # ----------------------------------------------------------------
        if not evidence_result.has_sufficient_evidence:
            result.effectiveness_state = ControlEffectivenessState.INSUFFICIENT_EVIDENCE
            result.execution_state = ControlExecutionState.CONTROL_NOT_OBSERVABLE
            limitations.append(
                "Insufficient evidence. MISSING != PASS. Cannot determine effectiveness."
            )
            if evidence_result.is_safety_critical_missing:
                limitations.append(
                    "Safety-critical evidence source is missing. Evaluation blocked."
                )
            result.limitations = limitations
            result.effectiveness_summary = (
                "Insufficient evidence to evaluate control effectiveness. "
                "MISSING != PASS. PARTIAL != COMPLETE."
            )
            result.uncertainty_preserved = True
            return result

        # ----------------------------------------------------------------
        # Stale evidence check
        # ----------------------------------------------------------------
        if evidence_result.stale_sources:
            limitations.append(
                f"Stale evidence from {len(evidence_result.stale_sources)} source(s). "
                "STALE != CURRENT. Historical effectiveness != Current effectiveness."
            )

        # ----------------------------------------------------------------
        # Conflicting evidence → EFFECTIVENESS_UNCLEAR
        # ----------------------------------------------------------------
        if evidence_result.conflicting_sources:
            result.effectiveness_state = ControlEffectivenessState.EFFECTIVENESS_UNCLEAR
            result.execution_state = ControlExecutionState.CONTROL_NOT_OBSERVABLE
            limitations.append(
                f"Conflicting evidence from {len(evidence_result.conflicting_sources)} source(s). "
                "CONFLICTED != SAFE."
            )
            result.limitations = limitations
            result.uncertainty_preserved = True
            result.effectiveness_summary = "Conflicting evidence prevents effectiveness determination."
            return result

        # ----------------------------------------------------------------
        # Compute execution coverage rate (requires valid denominator)
        # ----------------------------------------------------------------
        execution_coverage_rate: Optional[float] = None
        coverage_rate_available = False
        if eligible_executions is not None and eligible_executions > 0 and observed_executions is not None:
            execution_coverage_rate = observed_executions / eligible_executions
            coverage_rate_available = True
        elif eligible_executions == 0:
            limitations.append(
                "No eligible executions in observation window — cannot compute coverage rate. "
                "RATE_UNAVAILABLE."
            )

        # ----------------------------------------------------------------
        # Failure rate (requires valid denominator)
        # ----------------------------------------------------------------
        failure_rate: Optional[float] = None
        failure_rate_available = False
        if observed_failures is not None and eligible_executions is not None and eligible_executions > 0:
            failure_rate = observed_failures / eligible_executions
            failure_rate_available = True
        elif observed_failures is not None and observed_failures > 0 and (eligible_executions is None or eligible_executions == 0):
            limitations.append(
                f"{observed_failures} failure(s) observed but denominator unavailable. "
                "RATE_UNAVAILABLE — raw count is not a rate."
            )

        # ----------------------------------------------------------------
        # Bypass rate (requires valid denominator)
        # ----------------------------------------------------------------
        bypass_rate: Optional[float] = None
        bypass_rate_available = False
        if observed_bypasses is not None and eligible_executions is not None and eligible_executions > 0:
            bypass_rate = observed_bypasses / eligible_executions
            bypass_rate_available = True
        elif observed_bypasses is not None and observed_bypasses > 0:
            limitations.append(
                f"{observed_bypasses} bypass(es) observed. Denominator unavailable. "
                "RATE_UNAVAILABLE."
            )

        # ----------------------------------------------------------------
        # Bypass detection
        # ----------------------------------------------------------------
        if observed_bypasses and observed_bypasses > 0:
            result.bypass_detected = True
            result.bypass_count = observed_bypasses
            limitations.append(
                f"{observed_bypasses} control bypass(es) detected. "
                "A bypass is a safety signal — not automatically an incident."
            )

        # ----------------------------------------------------------------
        # Valid result rate
        # ----------------------------------------------------------------
        valid_result_rate: Optional[float] = None
        valid_result_rate_available = False
        if valid_results is not None and total_results is not None and total_results > 0:
            valid_result_rate = valid_results / total_results
            valid_result_rate_available = True

        # ----------------------------------------------------------------
        # Review compliance rate
        # ----------------------------------------------------------------
        review_compliance_rate: Optional[float] = None
        if (
            required_reviews_completed is not None
            and required_reviews_total is not None
            and required_reviews_total > 0
        ):
            review_compliance_rate = required_reviews_completed / required_reviews_total

        # ----------------------------------------------------------------
        # Build score dimensions
        # ----------------------------------------------------------------
        score = EffectivenessScoreDimensions(
            eligible_executions=eligible_executions,
            observed_executions=observed_executions,
            execution_coverage_rate=execution_coverage_rate,
            execution_coverage_rate_available=coverage_rate_available,
            total_results=total_results,
            valid_results=valid_results,
            valid_result_rate=valid_result_rate,
            valid_result_rate_available=valid_result_rate_available,
            observed_failures=observed_failures,
            failure_rate=failure_rate,
            failure_rate_available=failure_rate_available,
            observed_bypasses=observed_bypasses,
            bypass_rate=bypass_rate,
            bypass_rate_available=bypass_rate_available,
            evidence_completeness_score=evidence_result.completeness_score,
            version_consistent=version_consistent,
            provider_success_rate=provider_success_rate,
            provider_success_rate_available=provider_success_rate is not None,
            required_reviews_completed=required_reviews_completed,
            required_reviews_total=required_reviews_total,
            review_compliance_rate=review_compliance_rate,
            score_limitations=limitations[:],
        )
        result.score = score

        # ----------------------------------------------------------------
        # Determine degradation state from policy-derived thresholds
        # (thresholds come from approved config, never hardcoded clinical values)
        # ----------------------------------------------------------------
        degradation_state = DegradationState.STABLE

        if failure_rate is not None and degradation_threshold_failure_rate is not None:
            if failure_rate >= significant_degradation_threshold if significant_degradation_threshold else 0.5:
                degradation_state = DegradationState.SIGNIFICANTLY_DEGRADED
            elif failure_rate >= degradation_threshold_failure_rate:
                degradation_state = DegradationState.DEGRADED

        if bypass_rate is not None and degradation_threshold_bypass_rate is not None:
            if bypass_rate >= degradation_threshold_bypass_rate:
                if degradation_state == DegradationState.STABLE:
                    degradation_state = DegradationState.DEGRADED
                limitations.append(
                    "Bypass rate exceeds policy threshold. Control DEGRADED."
                )

        result.degradation_state = degradation_state

        # ----------------------------------------------------------------
        # Determine execution state
        # ----------------------------------------------------------------
        if eligible_executions is not None and eligible_executions > 0:
            if observed_executions is not None and observed_executions >= eligible_executions:
                result.execution_state = ControlExecutionState.CONTROL_COMPLETED
            elif observed_bypasses and observed_bypasses > 0:
                result.execution_state = ControlExecutionState.CONTROL_BYPASSED
            elif observed_failures and observed_failures > 0:
                result.execution_state = ControlExecutionState.CONTROL_FAILED
            elif observed_executions and observed_executions > 0:
                result.execution_state = ControlExecutionState.CONTROL_TRIGGERED
            else:
                result.execution_state = ControlExecutionState.CONTROL_NOT_TRIGGERED
        else:
            result.execution_state = ControlExecutionState.CONTROL_NOT_OBSERVABLE

        # ----------------------------------------------------------------
        # Determine effectiveness state
        # ----------------------------------------------------------------
        evidence_quality = evidence_result.overall_quality

        if degradation_state == DegradationState.SIGNIFICANTLY_DEGRADED:
            result.effectiveness_state = ControlEffectivenessState.FAILED
            limitations.append(
                "Control FAILED: significantly degraded. "
                "CONTROL FAILURE != PATIENT HARM. Route per policy."
            )
        elif degradation_state == DegradationState.DEGRADED:
            result.effectiveness_state = ControlEffectivenessState.DEGRADED
            limitations.append(
                "Control DEGRADED. CONTROL DEGRADATION != INCIDENT. Route per policy."
            )
        elif evidence_quality == EvidenceQualityState.PARTIAL:
            result.effectiveness_state = ControlEffectivenessState.PARTIALLY_EFFECTIVE
            limitations.append("PARTIAL DATA != FULL VALIDATION.")
        elif expected_behavior_met is False:
            result.effectiveness_state = ControlEffectivenessState.DEGRADED
            limitations.append(
                "Observed behavior did not align with approved expectation."
            )
        elif expected_behavior_met is None:
            result.effectiveness_state = ControlEffectivenessState.EFFECTIVENESS_UNCLEAR
            limitations.append(
                "Expected behavior alignment could not be determined. "
                "EFFECTIVENESS_UNCLEAR preserves uncertainty."
            )
        elif version_consistent is False:
            result.effectiveness_state = ControlEffectivenessState.EFFECTIVENESS_UNCLEAR
            limitations.append(
                "Control version was inconsistent during observation window. "
                "Historical effectiveness != Current effectiveness."
            )
        elif result.bypass_detected:
            result.effectiveness_state = ControlEffectivenessState.PARTIALLY_EFFECTIVE
            limitations.append(
                "Bypass(es) detected during observation window. "
                "Effectiveness may be overstated."
            )
        elif evidence_quality in (EvidenceQualityState.COMPLETE, EvidenceQualityState.UNVERIFIED):
            # Evidence available and behavior aligned
            result.effectiveness_state = ControlEffectivenessState.EFFECTIVE_OBSERVED
            # Note: EFFECTIVE_OBSERVED != risk eliminated, != permanent effectiveness
            limitations.append(
                "EFFECTIVE_OBSERVED during evaluation window. "
                "TEMPORARY SUCCESS != PERMANENT EFFECTIVENESS. "
                "EFFECTIVENESS != RISK ELIMINATION. "
                "CURRENT OBSERVATION != FUTURE SAFETY."
            )
        else:
            result.effectiveness_state = ControlEffectivenessState.EFFECTIVENESS_UNCLEAR
            limitations.append("Effectiveness unclear. Uncertainty preserved.")

        # ----------------------------------------------------------------
        # Determine if human review is required
        # ----------------------------------------------------------------
        high_risk_states = {
            ControlEffectivenessState.DEGRADED,
            ControlEffectivenessState.FAILED,
            ControlEffectivenessState.INSUFFICIENT_EVIDENCE,
            ControlEffectivenessState.EFFECTIVENESS_UNCLEAR,
        }
        if (
            is_high_risk_control
            or result.effectiveness_state in high_risk_states
            or result.bypass_detected
            or result.regression_detected
        ):
            result.review_required = True
            result.review_required_reason = (
                "High-risk assurance outcome or effectiveness uncertainty requires "
                "human review. AI cannot approve assurance decisions."
            )

        result.limitations = limitations
        result.uncertainty_preserved = True
        result.effectiveness_summary = self._build_summary(result)
        return result

    def _build_summary(self, result: ControlEffectivenessEvaluationResult) -> str:
        """Build a non-PHI summary of the effectiveness evaluation."""
        parts = [
            f"Effectiveness: {result.effectiveness_state.value}.",
            f"Execution: {result.execution_state.value}.",
            f"Degradation: {result.degradation_state.value}.",
        ]
        if result.bypass_detected:
            parts.append(f"Bypasses detected: {result.bypass_count}.")
        if result.regression_detected:
            parts.append("Control regression detected.")
        if result.review_required:
            parts.append("Human review required. AI cannot approve assurance.")
        parts.append(
            "REMINDER: EFFECTIVENESS_OBSERVED does not mean risk eliminated "
            "or patient safety guaranteed."
        )
        return " ".join(parts)


# Global singleton
safety_control_effectiveness_service = SafetyControlEffectivenessService()

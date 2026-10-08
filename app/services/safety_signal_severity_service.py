"""Phase 60: Safety Signal Severity & Uncertainty Evaluation Service.

Evaluates governed operational/routing severity, evidence uncertainty,
and routing priority per TRD Section 11, 12, 13 & 49.
"""

from typing import Any, Dict, List, Tuple

from app.schemas.safety_triage import (
    EscalationRoutingPriority,
    GovernedSignalSeverity,
    SafetyTriageRecord,
    SignalClassification,
    TriageLifecycleState,
    UncertaintyState,
)


class SafetySignalSeverityService:
    """Evaluates governed severity, uncertainty, and routing priority."""

    def evaluate_severity_and_uncertainty(
        self,
        record: SafetyTriageRecord,
    ) -> Tuple[GovernedSignalSeverity, UncertaintyState, EscalationRoutingPriority]:
        """Run fail-safe severity and uncertainty evaluation across triage evidence."""
        primary_sig = record.signals[0] if record.signals else None
        signal_count = len(record.signals)
        evidence_count = len(record.evidence)

        # 1. Uncertainty Evaluation (TRD Section 13 & 49)
        conflicted = any(s.metadata.get("conflicted", False) for s in record.signals)
        missing_data = signal_count == 0 or (primary_sig and primary_sig.metadata.get("insufficient_data", False))

        if conflicted:
            uncertainty = UncertaintyState.CONFLICTED_EVIDENCE
        elif missing_data:
            uncertainty = UncertaintyState.INSUFFICIENT_DATA
        elif evidence_count == 0 and signal_count == 1:
            uncertainty = UncertaintyState.MODERATE_UNCERTAINTY
        elif evidence_count > 0:
            uncertainty = UncertaintyState.LOW_UNCERTAINTY
        else:
            uncertainty = UncertaintyState.UNKNOWN

        # 2. Governed Severity Evaluation (TRD Section 11 & 12)
        # Check explicit severity in primary signal or signals
        severities = [s.severity.upper() for s in record.signals] if record.signals else []
        has_critical = "CRITICAL" in severities or (primary_sig and primary_sig.severity.upper() == "CRITICAL")
        has_high = "HIGH" in severities or (primary_sig and primary_sig.severity.upper() == "HIGH")
        has_warning = "WARNING" in severities or "MEDIUM" in severities or "MODERATE" in severities

        if record.classification in {
            SignalClassification.SAFETY_CONTROL,
            SignalClassification.DATA_INTEGRITY,
            SignalClassification.SECURITY,
        }:
            # Safety control breaches and security anomalies elevate severity
            if has_critical or signal_count >= 3:
                severity = GovernedSignalSeverity.CRITICAL
            else:
                severity = GovernedSignalSeverity.HIGH
        elif has_critical:
            severity = GovernedSignalSeverity.CRITICAL
        elif has_high or signal_count >= 5:
            severity = GovernedSignalSeverity.HIGH
        elif has_warning or signal_count >= 2:
            severity = GovernedSignalSeverity.MODERATE
        elif signal_count == 1 and not missing_data and not conflicted:
            severity = GovernedSignalSeverity.LOW
        elif missing_data or conflicted:
            severity = GovernedSignalSeverity.UNKNOWN
        else:
            severity = GovernedSignalSeverity.UNKNOWN

        # 3. System-Routing Priority Calculation (TRD Section 17)
        if severity == GovernedSignalSeverity.CRITICAL:
            priority = EscalationRoutingPriority.CRITICAL_ESCALATION
            record.requires_human_review = True
            record.is_escalated = True
        elif severity == GovernedSignalSeverity.HIGH:
            priority = EscalationRoutingPriority.URGENT_GOVERNANCE_REVIEW
            record.requires_human_review = True
            record.is_escalated = True
        elif uncertainty in {UncertaintyState.CONFLICTED_EVIDENCE, UncertaintyState.INSUFFICIENT_DATA, UncertaintyState.HIGH_UNCERTAINTY}:
            # Fail-safe: High uncertainty / conflicted evidence requires human review (TRD Section 49)
            priority = EscalationRoutingPriority.HIGH_PRIORITY_REVIEW
            record.requires_human_review = True
        elif severity == GovernedSignalSeverity.MODERATE:
            priority = EscalationRoutingPriority.REVIEW
            record.requires_human_review = True
        elif severity == GovernedSignalSeverity.LOW and uncertainty == UncertaintyState.LOW_UNCERTAINTY:
            priority = EscalationRoutingPriority.ROUTINE
        else:
            priority = EscalationRoutingPriority.UNKNOWN_PRIORITY
            record.requires_human_review = True

        record.governed_severity = severity
        record.uncertainty_state = uncertainty
        record.priority = priority
        record.lifecycle_state = TriageLifecycleState.SEVERITY_EVALUATED

        return severity, uncertainty, priority

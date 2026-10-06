"""Phase 48: Safety Conflict Service.

Detects and surfaces contradictory clinical decisions, multi-provider disagreements,
patient-reported discrepancies, and triage override conflicts.
Ensures that no system component silently resolves conflicts without human oversight.
"""

from typing import Any
from app.core.exceptions import DecisionConflictedException
from app.schemas.safety_result import SafetyStatus


class SafetyConflictService:
    """Service detecting and managing clinical conflicts."""

    def detect_provider_disagreement(
        self,
        provider_results: list[dict[str, Any]],
    ) -> tuple[bool, str | None, list[str]]:
        """Evaluate outputs from multiple safety providers for disagreements.

        Returns (is_conflicted, conflict_code, details).
        """
        if len(provider_results) < 2:
            return False, None, []

        outcomes = set()
        for res in provider_results:
            outcome = res.get("outcome") or res.get("result") or res.get("status")
            if outcome:
                outcomes.add(str(outcome).upper())

        # If one provider says interaction / risk and another says clear / no interaction
        has_risk = any("INTERACTION" in o or "CONTRAINDICATION" in o or "RISK" in o or "HIGH" in o for o in outcomes)
        has_clear = any("CLEAR" in o or "NO_INTERACTION" in o or "SAFE" in o or "LOW" in o for o in outcomes)

        if has_risk and has_clear:
            reasons = [f"Provider {r.get('provider_id', 'unknown')} reported {r.get('outcome')}" for r in provider_results]
            return True, "PROVIDER_DISAGREEMENT", reasons

        return False, None, []

    def detect_triage_override_conflict(
        self,
        rule_urgency: str | None,
        ai_urgency: str | None,
    ) -> tuple[bool, str | None]:
        """Detect conflict when an AI suggestion attempts to downgrade or contradict a rule-based triage assessment."""
        if not rule_urgency or not ai_urgency:
            return False, None

        rule_val = rule_urgency.upper()
        ai_val = ai_urgency.upper()

        if rule_val != ai_val:
            return True, f"TRIAGE_OVERRIDE_CONFLICT: Rule engine ({rule_val}) disagrees with AI ({ai_val})"

        return False, None

    def detect_clinical_data_conflict(
        self,
        patient_reported: dict[str, Any] | None,
        authoritative_record: dict[str, Any] | None,
    ) -> tuple[bool, str | None]:
        """Detect conflict between patient-reported information and EHR records."""
        if not patient_reported or not authoritative_record:
            return False, None

        # Check for allergy conflict
        if patient_reported.get("allergy") and not authoritative_record.get("allergy"):
            return True, "PATIENT_REPORTED_ALLERGY_CONFLICT"

        return False, None

    def assert_no_unresolved_conflicts(
        self,
        provider_results: list[dict[str, Any]] | None = None,
        rule_urgency: str | None = None,
        ai_urgency: str | None = None,
    ) -> None:
        """Assert no clinical conflicts exist; raise DecisionConflictedException if conflicted."""
        if provider_results:
            is_conf, code, reasons = self.detect_provider_disagreement(provider_results)
            if is_conf:
                raise DecisionConflictedException(
                    f"Contradictory provider outcomes detected ({code}). Human resolution required.",
                    details={"conflict_code": code, "disagreements": reasons},
                )

        if rule_urgency and ai_urgency:
            is_conf, code = self.detect_triage_override_conflict(rule_urgency, ai_urgency)
            if is_conf:
                raise DecisionConflictedException(
                    f"Triage conflict detected: {code}. Authoritative rule engine cannot be silently overridden.",
                    details={"conflict_code": code},
                )


# Global singleton
safety_conflict_service = SafetyConflictService()

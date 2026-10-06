"""Phase 48: Safety Validation Service.

Validates clinical input completeness, detects client-side bypass attempts,
guards against prompt injection and unauthorized AI clinical actions,
and verifies decision lifecycle preconditions.
"""

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import (
    AIClinicalActionProhibitedException,
    AmbiguousDataException,
    DecisionAlreadySupersededException,
    DecisionExpiredException,
    DecisionStaleException,
    HumanReviewMissingException,
    InsufficientInformationException,
    InvalidClinicalInputException,
    SafetyBypassAttemptBlockedException,
)
from app.schemas.decisions import DecisionRecord, DecisionStatus, DecisionType


PROHIBITED_AI_KEYWORDS = [
    "DIAGNOSE",
    "PRESCRIBE",
    "MODIFY_MEDICATION",
    "OVERRIDE_TRIAGE",
    "VERIFY_CLINICAL_TRUTH",
    "GRANT_CONSENT",
    "GRANT_AUTHORIZATION",
    "EMERGENCY_DISPATCH",
]

PROMPT_INJECTION_INDICATORS = [
    "IGNORE PREVIOUS INSTRUCTIONS",
    "OVERRIDE SAFETY",
    "BYPASS GUARDRAIL",
    "MARK AS SAFE",
    "DISREGARD RULES",
    "SYSTEM PROMPT:",
    "ADMIN_OVERRIDE",
]


class SafetyValidationService:
    """Service enforcing input validation, guardrails, and bypass detection."""

    def validate_client_bypass_attempts(self, payload: dict[str, Any]) -> None:
        """Check for and reject client attempts to disable safety controls.

        Parameters like skip_safety=True or emergency=True from clients are prohibited.
        """
        bypass_keys = [
            "skip_safety",
            "force_apply",
            "ignore_review",
            "bypass_consent",
            "override_version",
            "mark_safe",
            "verified",
            "approve",
        ]
        for key in bypass_keys:
            if payload.get(key) is True:
                raise SafetyBypassAttemptBlockedException(
                    f"Client parameter '{key}=true' is an unauthorized safety bypass attempt.",
                    details={"attempted_bypass_field": key},
                )

        # Uncontrolled client emergency override
        if payload.get("emergency") is True and not payload.get("_server_verified_break_glass"):
            raise SafetyBypassAttemptBlockedException(
                "Client cannot self-declare 'emergency=true' to bypass safety gates.",
                details={"attempted_bypass_field": "emergency"},
            )

    def validate_input_completeness(self, domain: str, input_data: dict[str, Any]) -> None:
        """Validate that all mandatory domain fields are present and valid."""
        if domain == "medication":
            med_id = input_data.get("medication_id") or input_data.get("name")
            if not med_id:
                raise InsufficientInformationException("Medication identity is required for safety evaluation.")
            if str(med_id).upper() in ["UNKNOWN", "UNCERTAIN", "AMBIGUOUS"]:
                raise AmbiguousDataException(f"Medication identity '{med_id}' is ambiguous and cannot be evaluated safely.")

            # Dose and route / frequency
            dose = input_data.get("dose")
            route = input_data.get("route")
            if not dose and not input_data.get("strength"):
                raise InsufficientInformationException("Medication dose or strength is required for safety check.")
            if not route and not input_data.get("frequency"):
                raise InsufficientInformationException("Medication route or frequency is required for safety check.")

        elif domain == "triage":
            vitals = input_data.get("vitals")
            symptoms = input_data.get("symptoms")
            if vitals is None and symptoms is None:
                raise InsufficientInformationException("Triage evaluation requires at least vitals or symptoms context.")
            # Check for missing emergency indicators: missing data must NOT be assumed negative
            if "chest_pain" in input_data and input_data["chest_pain"] is None:
                raise InsufficientInformationException("Missing chest pain indicator cannot be converted to negative.")

    def sanitize_untrusted_text(self, text: str) -> None:
        """Inspect untrusted document/user text for prompt injection attempts."""
        upper_text = text.upper()
        for indicator in PROMPT_INJECTION_INDICATORS:
            if indicator in upper_text:
                raise SafetyBypassAttemptBlockedException(
                    f"Potential prompt injection detected in clinical input: '{indicator}'.",
                    details={"indicator": indicator},
                )

    def assert_ai_output_boundaries(self, action: str, output_data: dict[str, Any] | None = None) -> None:
        """Assert that an AI output does not attempt prohibited clinical actions."""
        action_upper = action.upper().replace(":", "_").replace("-", "_")
        for prohibited in PROHIBITED_AI_KEYWORDS:
            if prohibited in action_upper:
                raise AIClinicalActionProhibitedException(
                    f"AI outputs cannot execute '{action}'. Prohibited boundary: {prohibited}.",
                    details={"action": action, "prohibited_boundary": prohibited},
                )

        if output_data:
            # Check for embedded prohibited action claims
            if output_data.get("is_definitive_diagnosis") is True:
                raise AIClinicalActionProhibitedException("AI output claimed definitive clinical diagnosis.")
            if output_data.get("auto_prescribed") is True:
                raise AIClinicalActionProhibitedException("AI output claimed autonomous prescription authority.")

    def validate_decision_for_application(self, decision: DecisionRecord) -> None:
        """Validate that a decision is in a valid state to be applied."""
        now = datetime.now(timezone.utc)

        # Check supersession
        if not getattr(decision, "is_current", True) or decision.status == DecisionStatus.SUPERSEDED or getattr(decision, "superseded_by_id", None):
            raise DecisionAlreadySupersededException(
                f"Decision '{decision.id}' is superseded and cannot be applied.",
                details={"decision_id": decision.id, "superseded_by": getattr(decision, "superseded_by_id", None)},
            )

        # Check expiration
        if decision.expires_at and decision.expires_at < now:
            raise DecisionExpiredException(
                f"Decision '{decision.id}' expired at {decision.expires_at.isoformat()} and cannot be applied.",
                details={"decision_id": decision.id, "expired_at": decision.expires_at.isoformat()},
            )

        # Check human review requirement
        if decision.requires_human_oversight and decision.status != DecisionStatus.APPROVED:
            raise HumanReviewMissingException(
                f"Decision '{decision.id}' requires human clinician approval before application (current status: {decision.status.value}).",
                details={"decision_id": decision.id, "current_status": decision.status.value},
            )


# Global singleton
safety_validation_service = SafetyValidationService()

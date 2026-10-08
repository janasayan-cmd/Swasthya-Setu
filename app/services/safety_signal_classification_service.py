"""Phase 60: Safety Signal Classification Service.

Classifies incoming surveillance signals into governed categories while
preserving provenance and ensuring unknown/uncertain classifications remain explicit.
"""

from typing import Any, Dict, Optional, Tuple

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_triage import (
    SafetyTriageRecord,
    SignalClassification,
    TriageLifecycleState,
)


class SafetySignalClassificationService:
    """Manages signal classification and validation per TRD Section 9 & 10."""

    @staticmethod
    def infer_classification(signal_type: str, metadata: Optional[Dict[str, Any]] = None) -> SignalClassification:
        """Categorize signal based on authoritative signal type and provenance."""
        st = signal_type.upper()
        if "SAFETY_CONTROL" in st or "SAFETY_GATE" in st:
            return SignalClassification.SAFETY_CONTROL
        elif "DATA_INTEGRITY" in st or "CORRUPTION" in st:
            return SignalClassification.DATA_INTEGRITY
        elif "PRIVACY" in st or "CONSENT" in st or "PHI" in st:
            return SignalClassification.PRIVACY
        elif "SECURITY" in st or "AUTH" in st or "BREACH" in st:
            return SignalClassification.SECURITY
        elif "WORKFLOW" in st or "ORDER" in st or "DISCHARGE" in st:
            return SignalClassification.WORKFLOW
        elif "PROVIDER" in st or "ADAPTER" in st:
            return SignalClassification.PROVIDER
        elif "CONFIGURATION" in st or "CONFIG" in st:
            return SignalClassification.CONFIGURATION
        elif "VERSION" in st:
            return SignalClassification.VERSION
        elif "EFFECTIVENESS" in st:
            return SignalClassification.EFFECTIVENESS
        elif "ASSURANCE" in st:
            return SignalClassification.ASSURANCE
        elif "INCIDENT" in st or "CLINICAL" in st:
            return SignalClassification.CLINICAL_SAFETY_REFERENCE
        elif "USER_REPORTED" in st or "PATIENT" in st:
            return SignalClassification.USER_REPORTED
        elif "HUMAN_REVIEW" in st:
            return SignalClassification.HUMAN_REVIEW
        elif "ERROR_RATE" in st or "LATENCY" in st or "TIMEOUT" in st or "TECHNICAL" in st:
            return SignalClassification.TECHNICAL
        else:
            return SignalClassification.UNKNOWN

    def classify(
        self,
        record: SafetyTriageRecord,
        explicit_classification: Optional[SignalClassification] = None,
        is_ai_agent: bool = False,
        ai_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[SignalClassification, bool]:
        """Classify signal, updating triage state and enforcing AI boundaries.

        Returns (classification, requires_human_review).
        """
        if explicit_classification and explicit_classification != SignalClassification.UNKNOWN:
            target_class = explicit_classification
        else:
            # Infer from primary signal
            sig_type = record.signals[0].signal_type if record.signals else "UNKNOWN"
            meta = record.signals[0].metadata if record.signals else {}
            target_class = self.infer_classification(sig_type, meta)

        record.classification = target_class
        record.lifecycle_state = TriageLifecycleState.CLASSIFIED

        requires_review = False
        # If AI suggested, human review is mandatory (TRD Section 23)
        if is_ai_agent:
            requires_review = True
            record.requires_human_review = True
            record.metadata["ai_classification_metadata"] = ai_metadata or {}

        # High risk classes mandate human review
        if target_class in {
            SignalClassification.SAFETY_CONTROL,
            SignalClassification.DATA_INTEGRITY,
            SignalClassification.PRIVACY,
            SignalClassification.SECURITY,
            SignalClassification.CLINICAL_SAFETY_REFERENCE,
            SignalClassification.UNKNOWN,
        }:
            requires_review = True
            record.requires_human_review = True

        return target_class, requires_review

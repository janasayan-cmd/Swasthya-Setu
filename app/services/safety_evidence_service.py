"""Phase 52: Safety Evidence Service.

Collects, validates, classifies, and aggregates evidence references
for control assurance evaluations.

Key distinctions enforced by this service:
  MISSING != PASS
  PARTIAL != COMPLETE
  STALE != CURRENT
  CONFLICTED != SAFE
  UNVERIFIED != VERIFIED
  INVALID != SUCCESS

If a required evidence source is unavailable, the evaluation becomes
INSUFFICIENT_EVIDENCE or EFFECTIVENESS_UNCLEAR — never EFFECTIVE.

Partial source failure:
  If Source C is unavailable from {A, B, C},
  evidence_status = PARTIAL — not "A + B = complete".

Phase 18 remains authoritative for telemetry.
Phase 48 remains authoritative for safety gate records.
Phase 52 consumes references to authoritative records.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.safety_assurance import (
    EvidenceQualityState,
    EvidenceReference,
    EvidenceSourceType,
)

logger = logging.getLogger("app.services.safety_evidence_service")

# Maximum age for evidence to be considered "current" (configurable via policy)
_DEFAULT_EVIDENCE_STALENESS_THRESHOLD_HOURS = 72


class EvidenceCollectionResult:
    """Result of an evidence collection attempt."""

    def __init__(self) -> None:
        self.evidence_references: List[EvidenceReference] = []
        self.missing_sources: List[str] = []
        self.unavailable_sources: List[str] = []
        self.conflicting_sources: List[str] = []
        self.stale_sources: List[str] = []
        self.partial_sources: List[str] = []
        self.overall_quality: EvidenceQualityState = EvidenceQualityState.MISSING
        self.is_safety_critical_missing: bool = False
        self.completeness_score: Optional[float] = None
        self.notes: List[str] = []

    @property
    def has_sufficient_evidence(self) -> bool:
        """False if any safety-critical source is missing or evaluation is blocked."""
        if self.is_safety_critical_missing:
            return False
        return self.overall_quality not in (
            EvidenceQualityState.MISSING,
            EvidenceQualityState.INVALID,
            EvidenceQualityState.OUT_OF_SCOPE,
        )


class SafetyEvidenceService:
    """Collects and validates evidence for assurance evaluations.

    Evidence is stored as references to authoritative records — not raw
    clinical data — minimizing PHI exposure.

    Partial source failure is explicitly preserved (not silently collapsed).
    """

    def __init__(
        self,
        staleness_threshold_hours: int = _DEFAULT_EVIDENCE_STALENESS_THRESHOLD_HOURS,
    ) -> None:
        self._staleness_threshold_hours = staleness_threshold_hours

    def classify_evidence_quality(
        self,
        references: List[EvidenceReference],
        expected_sources: List[EvidenceSourceType],
        evaluation_start: datetime,
        evaluation_end: datetime,
        safety_critical_sources: Optional[List[EvidenceSourceType]] = None,
    ) -> EvidenceCollectionResult:
        """Classify evidence quality across collected references.

        Enforces:
          - MISSING != PASS
          - PARTIAL != COMPLETE
          - STALE != CURRENT

        Returns structured result with detailed quality state.
        """
        result = EvidenceCollectionResult()
        safety_critical = set(safety_critical_sources or [])
        now = datetime.now(timezone.utc)
        staleness_threshold = timedelta(hours=self._staleness_threshold_hours)

        available_sources: set[EvidenceSourceType] = set()

        for ref in references:
            # Check staleness
            if ref.observation_timestamp < evaluation_start:
                ref.quality_state = EvidenceQualityState.STALE
                ref.reliability_note = (
                    f"Evidence observation timestamp {ref.observation_timestamp.isoformat()} "
                    f"precedes evaluation window start {evaluation_start.isoformat()}."
                )
                result.stale_sources.append(ref.source_type.value)
            elif now - ref.observation_timestamp > staleness_threshold:
                ref.quality_state = EvidenceQualityState.STALE
                ref.reliability_note = (
                    f"Evidence is older than {self._staleness_threshold_hours}h "
                    f"threshold. STALE != CURRENT."
                )
                result.stale_sources.append(ref.source_type.value)
            else:
                if ref.quality_state == EvidenceQualityState.UNVERIFIED:
                    # Mark as available but still unverified — not auto-verified
                    pass
                available_sources.add(ref.source_type)

            result.evidence_references.append(ref)

        # Detect missing expected sources
        for expected in expected_sources:
            if expected not in available_sources:
                result.missing_sources.append(expected.value)
                if expected in safety_critical:
                    result.is_safety_critical_missing = True

        # Detect conflicts (same source appears with contradictory quality)
        source_qualities: Dict[str, List[EvidenceQualityState]] = {}
        for ref in result.evidence_references:
            qs = source_qualities.setdefault(ref.source_type.value, [])
            qs.append(ref.quality_state)

        for src, qualities in source_qualities.items():
            if len(set(qualities)) > 1:
                result.conflicting_sources.append(src)

        # Determine overall quality
        total_expected = len(expected_sources)
        total_missing = len(result.missing_sources)
        total_stale = len(result.stale_sources)
        total_conflicted = len(result.conflicting_sources)

        if total_expected > 0 and total_missing == total_expected:
            result.overall_quality = EvidenceQualityState.MISSING
        elif total_missing > 0 or total_stale > 0:
            result.overall_quality = EvidenceQualityState.PARTIAL
            result.notes.append(
                f"Partial evidence: {total_missing} missing source(s), "
                f"{total_stale} stale source(s). PARTIAL != COMPLETE."
            )
        elif total_conflicted > 0:
            result.overall_quality = EvidenceQualityState.CONFLICTED
            result.notes.append(
                "Conflicting evidence detected. CONFLICTED != SAFE."
            )
        elif any(r.quality_state == EvidenceQualityState.UNVERIFIED for r in result.evidence_references):
            result.overall_quality = EvidenceQualityState.UNVERIFIED
            result.notes.append("Some evidence remains unverified. UNVERIFIED != VERIFIED.")
        elif result.evidence_references:
            result.overall_quality = EvidenceQualityState.COMPLETE
        else:
            result.overall_quality = EvidenceQualityState.MISSING

        # Completeness score (0.0 – 1.0)
        if total_expected > 0:
            available_count = total_expected - total_missing
            result.completeness_score = max(0.0, available_count / total_expected)
        else:
            result.completeness_score = None  # Cannot compute without expected sources

        return result

    def validate_evidence_provenance(
        self, reference: EvidenceReference
    ) -> Tuple[bool, Optional[str]]:
        """Validate that an evidence reference has traceable provenance.

        Returns (is_valid, error_reason).
        """
        if not reference.source_id or not reference.source_id.strip():
            return False, "Evidence source_id is missing — cannot establish provenance."

        if not reference.source_type:
            return False, "Evidence source_type is missing — cannot classify evidence."

        if reference.observation_timestamp is None:
            return False, "Evidence observation_timestamp is missing — cannot determine freshness."

        return True, None

    def detect_partial_source_failure(
        self,
        expected_sources: List[EvidenceSourceType],
        collected_sources: List[EvidenceSourceType],
        unavailable_sources: Optional[List[EvidenceSourceType]] = None,
        safety_critical_sources: Optional[List[EvidenceSourceType]] = None,
    ) -> Dict[str, Any]:
        """Detect and report partial source failure.

        A + B available when C is expected DOES NOT equal complete evidence.
        Returns a structured partial-failure report.
        """
        unavailable = set(unavailable_sources or [])
        safety_critical = set(safety_critical_sources or [])
        missing = [s for s in expected_sources if s not in collected_sources]

        critical_missing = [s for s in missing if s in safety_critical]
        critical_unavailable = [s for s in unavailable if s in safety_critical]

        is_partial_failure = bool(missing) or bool(unavailable)
        is_critical_failure = bool(critical_missing) or bool(critical_unavailable)

        return {
            "is_partial_failure": is_partial_failure,
            "is_critical_failure": is_critical_failure,
            "missing_sources": [s.value for s in missing],
            "unavailable_sources": [s.value for s in unavailable],
            "critical_missing": [s.value for s in critical_missing],
            "critical_unavailable": [s.value for s in critical_unavailable],
            "note": (
                "Partial source failure: available sources do not constitute "
                "complete evidence. PARTIAL != COMPLETE. MISSING != PASS."
            ),
            "evaluation_recommendation": (
                "BLOCKED or INSUFFICIENT_EVIDENCE"
                if is_critical_failure
                else "EFFECTIVENESS_UNCLEAR"
            ),
        }

    def build_mock_evidence_references(
        self,
        control_id: str,
        observation_start: datetime,
        observation_end: datetime,
        source_types: Optional[List[EvidenceSourceType]] = None,
    ) -> List[EvidenceReference]:
        """Build mock evidence references for testing.

        NOT for production use. Test data must be clearly distinguishable
        from production clinical data.
        """
        now = datetime.now(timezone.utc)
        sources = source_types or [
            EvidenceSourceType.SAFETY_GATE_EVALUATION,
            EvidenceSourceType.DECISION_TRACE,
        ]
        refs = []
        for src in sources:
            refs.append(
                EvidenceReference(
                    source_type=src,
                    source_id=f"test-{src.value.lower()}-{control_id[:8]}",
                    source_version="test-v1",
                    observation_timestamp=observation_start,
                    recorded_timestamp=now,
                    provenance="SYNTHETIC_TEST",
                    scope_tag=f"control:{control_id}",
                    evaluation_context="TEST_ONLY",
                    quality_state=EvidenceQualityState.COMPLETE,
                    is_safety_critical=False,
                )
            )
        return refs


# Global singleton
safety_evidence_service = SafetyEvidenceService()

"""Phase 55: Action Effectiveness Policy Assessment Service.

Synthesizes comparison results, evidence sufficiency, and conflicts into a controlled effectiveness state.
Strictly enforces:
- INSUFFICIENT EVIDENCE != FAILURE
- MISSING EVIDENCE != PASS
- AI cannot autonomously declare effectiveness or finalize evaluation.
"""

from typing import List, Tuple

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    EffectivenessLifecycleState,
    EffectivenessState,
    EvidenceQualityState,
    ExpectedVsObservedComparison,
    PostActionEvidenceItem,
    UncertaintyLevel,
)


class ActionEffectivenessAssessmentService:
    """Service for evaluating policy-driven effectiveness state and human review requirements."""

    def determine_candidate_state(
        self,
        comparisons: List[ExpectedVsObservedComparison],
        evidence_items: List[PostActionEvidenceItem],
        conflicts: List[str],
    ) -> Tuple[EffectivenessState, EffectivenessLifecycleState, bool]:
        """Determine candidate effectiveness state, lifecycle state, and whether human review is required."""
        # 1. Check evidence sufficiency
        valid_evidence = [
            e for e in evidence_items
            if e.quality_state in (EvidenceQualityState.COMPLETE, EvidenceQualityState.PARTIAL)
        ]

        if not valid_evidence or not comparisons:
            return (
                EffectivenessState.INSUFFICIENT_EVIDENCE,
                EffectivenessLifecycleState.INSUFFICIENT_EVIDENCE,
                True,  # human review required
            )

        # 2. Check for conflicts
        if conflicts:
            return (
                EffectivenessState.INCONCLUSIVE,
                EffectivenessLifecycleState.REVIEW_REQUIRED,
                True,
            )

        # 3. Check confounding factors / high uncertainty
        high_uncertainty = any(c.uncertainty_level == UncertaintyLevel.HIGH for c in comparisons)
        unresolved = any(c.uncertainty_level == UncertaintyLevel.UNRESOLVED for c in comparisons)

        if unresolved:
            return (
                EffectivenessState.INSUFFICIENT_EVIDENCE,
                EffectivenessLifecycleState.INSUFFICIENT_EVIDENCE,
                True,
            )

        if high_uncertainty:
            return (
                EffectivenessState.EFFECTIVENESS_UNCLEAR,
                EffectivenessLifecycleState.REVIEW_REQUIRED,
                True,
            )

        # 4. Conformance evaluation
        total = len(comparisons)
        conforming_count = sum(1 for c in comparisons if c.is_conforming)

        if conforming_count == total:
            # All criteria met
            return (
                EffectivenessState.EFFECTIVE_OBSERVED,
                EffectivenessLifecycleState.REVIEW_REQUIRED,  # requires human sign-off/review
                True,
            )
        elif conforming_count > 0:
            # Partial
            return (
                EffectivenessState.PARTIALLY_EFFECTIVE,
                EffectivenessLifecycleState.REVIEW_REQUIRED,
                True,
            )
        else:
            # None met
            return (
                EffectivenessState.FAILED,
                EffectivenessLifecycleState.REVIEW_REQUIRED,
                True,
            )

    def validate_human_authority(self, is_ai_agent: bool) -> None:
        """Enforce AI boundary: AI cannot approve or finalize effectiveness."""
        if is_ai_agent:
            raise AppException(
                code=ErrorCode.REVIEW_DENIED,
                message=(
                    "AI agents are strictly prohibited from approving effectiveness evaluations "
                    "or finalizing clinical safety outcomes. Human review is mandatory."
                ),
                status_code=403,
            )

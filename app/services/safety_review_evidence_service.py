"""Phase 63: Clinical Safety Review Evidence Service.

Evaluates evidence completeness, consistency, relevance, counter-evidence, and staleness.
Non-Negotiable Invariants:
- EVIDENCE != PROOF OF ZERO RISK
- Missing evidence must NEVER be interpreted as evidence of safety.
- UNKNOWN or INSUFFICIENT evidence must NEVER be automatically converted into LOW RISK or ACCEPTED.
- Contradictory counter-evidence must be preserved explicitly.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_review_evidence import (
    EvidenceReference,
    EvidenceSufficiencyState,
    SubmitEvidenceRequest,
)
from app.schemas.safety_risk_review import SafetyRiskReviewRecord
from app.schemas.user import AuthenticatedUserContext


class SafetyReviewEvidenceService:
    """Service responsible for evaluating evidence sufficiency and attaching evidence."""

    MAX_EVIDENCE_AGE_DAYS = 90

    @classmethod
    def evaluate_evidence_sufficiency(
        cls,
        evidence_items: List[EvidenceReference],
    ) -> Tuple[EvidenceSufficiencyState, List[str], List[str]]:
        """Evaluate evidence sufficiency, returning state, limitations, and blocking issues."""
        if not evidence_items:
            return (
                EvidenceSufficiencyState.INSUFFICIENT,
                ["No supporting evidence has been provided."],
                ["Evidence required for clinical risk decision-making."],
            )

        limitations: List[str] = []
        blocking_issues: List[str] = []
        now = datetime.now(timezone.utc)

        has_stale = False
        has_counter = False
        has_conflicts = False
        has_low_completeness = False

        for ev in evidence_items:
            # Check staleness
            if (now - ev.timestamp) > timedelta(days=cls.MAX_EVIDENCE_AGE_DAYS):
                has_stale = True
                limitations.append(f"Evidence '{ev.evidence_id}' from source '{ev.source}' exceeds {cls.MAX_EVIDENCE_AGE_DAYS} days.")

            # Check counter-evidence / conflict
            if ev.is_counter_evidence:
                has_counter = True
                limitations.append(f"Counter-evidence identified in '{ev.evidence_id}' from '{ev.source}'.")

            if ev.consistency < 0.7:
                has_conflicts = True
                limitations.append(f"Evidence '{ev.evidence_id}' exhibits internal consistency concerns ({ev.consistency:.2f}).")

            if ev.completeness < 0.6:
                has_low_completeness = True
                limitations.append(f"Evidence '{ev.evidence_id}' is incomplete ({ev.completeness:.2f}).")

            if not ev.dependency_available:
                blocking_issues.append(f"Source dependency unavailable for evidence '{ev.evidence_id}'.")

        if blocking_issues:
            return (
                EvidenceSufficiencyState.INSUFFICIENT,
                limitations,
                blocking_issues,
            )

        if has_conflicts or (has_counter and len(evidence_items) == 1):
            return (
                EvidenceSufficiencyState.CONFLICTED,
                limitations,
                ["Evidence conflicts exist that require reconciliation before disposition."],
            )

        if has_stale and len(evidence_items) == 1:
            return (
                EvidenceSufficiencyState.STALE,
                limitations,
                ["Primary evidence is stale and must be refreshed."],
            )

        if has_counter or has_low_completeness or has_stale:
            return (
                EvidenceSufficiencyState.SUFFICIENT_WITH_LIMITATIONS,
                limitations,
                [],
            )

        return (
            EvidenceSufficiencyState.SUFFICIENT,
            [],
            [],
        )

    @classmethod
    def attach_evidence(
        cls,
        review: SafetyRiskReviewRecord,
        request: SubmitEvidenceRequest,
        user: AuthenticatedUserContext,
    ) -> EvidenceReference:
        """Attach newly submitted evidence to the review record."""
        # Validate version alignment
        if request.version and review.risk_context_version and request.version != review.risk_context_version:
            # Record limitation / version mismatch
            request.limitations.append(f"Version mismatch: evidence version '{request.version}' vs review context '{review.risk_context_version}'.")

        ev_ref = EvidenceReference(
            source=request.source,
            provenance=request.provenance,
            scope=review.scope,
            version=request.version,
            is_counter_evidence=request.is_counter_evidence,
            limitations=request.limitations,
            metadata={
                "submitted_by": user.user_id,
                "evidence_payload_keys": list(request.evidence_payload.keys()),
            },
        )
        review.evidence_items.append(ev_ref)

        # Re-evaluate evidence sufficiency
        sufficiency, _, _ = cls.evaluate_evidence_sufficiency(review.evidence_items)
        review.evidence_sufficiency = sufficiency

        return ev_ref

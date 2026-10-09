"""Phase 63: Clinical Safety Risk Decision-Readiness Service.

Evaluates whether a risk review context is prepared for authoritative governed human decision.
Enforces that missing or uncertain evidence never degrades to SAFE.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from fastapi import status

from app.schemas.safety_review_evidence import EvidenceSufficiencyState
from app.schemas.safety_review_question import QuestionStatus
from app.schemas.safety_risk_readiness import (
    DecisionReadinessEvaluation,
    DecisionReadinessState,
)
from app.schemas.safety_risk_review import SafetyRiskReviewRecord


class SafetyRiskReadinessService:
    """Evaluator for review package decision-readiness."""

    MAX_CONTEXT_AGE_DAYS = 30

    @classmethod
    def evaluate_readiness(
        cls,
        review: SafetyRiskReviewRecord,
    ) -> DecisionReadinessEvaluation:
        """Evaluate review context completeness, evidence sufficiency, and question state."""
        reasons: List[str] = []
        limitations: List[str] = []
        blocking_issues: List[str] = []
        now = datetime.now(timezone.utc)

        # 1. Check if review is blocked
        if review.requires_escalation:
            blocking_issues.append("Review marked for critical escalation.")

        # 2. Check context staleness
        context_age = now - review.created_at
        if context_age > timedelta(days=cls.MAX_CONTEXT_AGE_DAYS):
            blocking_issues.append(f"Risk review context is older than {cls.MAX_CONTEXT_AGE_DAYS} days and is stale.")
            return DecisionReadinessEvaluation(
                state=DecisionReadinessState.STALE,
                is_ready_for_review=False,
                reasons=["Context has exceeded maximum age threshold."],
                limitations=limitations,
                blocking_issues=blocking_issues,
            )

        # 3. Check unresolved questions
        open_questions = [
            q for q in review.questions
            if q.status in (QuestionStatus.OPEN, QuestionStatus.ASSIGNED, QuestionStatus.REOPENED)
        ]
        if open_questions:
            reasons.append(f"There are {len(open_questions)} open/unresolved questions.")
            has_blocking_question = any("CONFLICT" in q.category.value or "SCOPE" in q.category.value for q in open_questions)
            if has_blocking_question:
                blocking_issues.append("Unresolved questions concerning conflicting evidence or uncertain scope exist.")

        # 4. Check evidence sufficiency
        ev_state = review.evidence_sufficiency
        if ev_state == EvidenceSufficiencyState.CONFLICTED:
            blocking_issues.append("Underlying evidence exhibits severe cross-source contradiction.")
            return DecisionReadinessEvaluation(
                state=DecisionReadinessState.CONFLICTED,
                is_ready_for_review=False,
                reasons=["Evidence conflict must be resolved before proceeding."],
                limitations=limitations,
                blocking_issues=blocking_issues,
            )
        elif ev_state == EvidenceSufficiencyState.INSUFFICIENT or len(review.evidence_items) == 0:
            reasons.append("Evidence is insufficient for a conclusive governed disposition.")
            return DecisionReadinessEvaluation(
                state=DecisionReadinessState.EVIDENCE_REQUIRED,
                is_ready_for_review=False,
                reasons=reasons,
                limitations=limitations,
                blocking_issues=["Supporting evidence missing."],
            )
        elif ev_state == EvidenceSufficiencyState.STALE:
            blocking_issues.append("Primary supporting evidence is stale.")
            return DecisionReadinessEvaluation(
                state=DecisionReadinessState.STALE,
                is_ready_for_review=False,
                reasons=["Supporting evidence has expired."],
                limitations=limitations,
                blocking_issues=blocking_issues,
            )

        # 5. Check if reassessment is required
        if review.requires_reassessment:
            return DecisionReadinessEvaluation(
                state=DecisionReadinessState.REASSESSMENT_REQUIRED,
                is_ready_for_review=False,
                reasons=["Material changes require context reassessment."],
                limitations=limitations,
                blocking_issues=["Reassessment mandatory before review."],
            )

        # 6. Evaluate blocking vs ready
        if blocking_issues:
            return DecisionReadinessEvaluation(
                state=DecisionReadinessState.BLOCKED,
                is_ready_for_review=False,
                reasons=reasons,
                limitations=limitations,
                blocking_issues=blocking_issues,
            )

        # 7. Check limitations
        if ev_state == EvidenceSufficiencyState.SUFFICIENT_WITH_LIMITATIONS or open_questions:
            for q in open_questions:
                limitations.append(f"Unresolved non-blocking question: {q.question_text}")
            return DecisionReadinessEvaluation(
                state=DecisionReadinessState.READY_WITH_LIMITATIONS,
                is_ready_for_review=True,
                reasons=["Context satisfies minimum criteria but carries noted limitations."],
                limitations=limitations,
                blocking_issues=[],
            )

        # 8. Fully Ready
        return DecisionReadinessEvaluation(
            state=DecisionReadinessState.READY,
            is_ready_for_review=True,
            reasons=["All minimum evidence, provenance, and question criteria satisfied."],
            limitations=[],
            blocking_issues=[],
        )

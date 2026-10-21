"""Phase 65: Safety Completion Readiness Service.

Calculates completion eligibility and readiness states from authoritative sources.
Critical Rule:
A failed readiness evaluation must NEVER default to READY.
Unknown status, missing outcomes, or unresolved follow-ups must remain BLOCKED or PENDING.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.safety_completion_followup import FollowUpObligationRecord, FollowUpStatus
from app.schemas.safety_completion_outcome import (
    CompletionOutcomeReference,
    OutcomeVerificationStatus,
)
from app.schemas.safety_completion_readiness import (
    CompletionReadinessState,
    ReadinessEvaluationRecord,
)
from app.schemas.safety_completion_requirement import (
    CompletionRequirementRecord,
    RequirementStatus,
)
from app.schemas.safety_risk_disposition import RiskDispositionRecord
from app.schemas.safety_risk_handoff import SafetyRiskHandoffRecord


class SafetyCompletionReadinessService:
    """Evaluates readiness of a safety workflow completion package."""

    @staticmethod
    def evaluate(
        completion_id: str,
        disposition: RiskDispositionRecord,
        handoffs: List[SafetyRiskHandoffRecord],
        requirements: List[CompletionRequirementRecord],
        outcomes: List[CompletionOutcomeReference],
        follow_ups: List[FollowUpObligationRecord],
        source_revision: str = "v1.0.0",
        policy_version: str = "v1.0.0",
    ) -> ReadinessEvaluationRecord:
        """Execute comprehensive readiness evaluation."""
        blockers: List[str] = []
        limitations: List[str] = []
        missing_evidence: List[str] = []

        total_reqs = len(requirements)
        sat_reqs = sum(1 for r in requirements if r.status == RequirementStatus.SATISFIED)
        pending_reqs = sum(1 for r in requirements if r.status in (RequirementStatus.PENDING, RequirementStatus.UNRESOLVED))
        blocked_reqs = sum(1 for r in requirements if r.status == RequirementStatus.BLOCKED)

        total_handoffs = len(handoffs)
        completed_handoffs = sum(1 for h in handoffs if h.state.value == "COMPLETED")
        pending_handoffs = total_handoffs - completed_handoffs

        total_outcomes = len(outcomes)
        reconciled_outcomes = sum(1 for o in outcomes if o.is_reconciled and o.is_terminal)
        pending_outcomes = total_outcomes - reconciled_outcomes

        total_fups = len(follow_ups)
        sat_fups = sum(1 for f in follow_ups if f.status in (FollowUpStatus.SATISFIED, FollowUpStatus.WAIVED_BY_AUTHORIZED_POLICY))
        pending_fups = total_fups - sat_fups

        # 1. Check handoffs completeness
        if pending_handoffs > 0:
            blockers.append(f"{pending_handoffs} required handoff(s) have not reached COMPLETED status.")

        # 2. Check destination outcome reconciliation
        for outcome in outcomes:
            if not outcome.is_reconciled:
                blockers.append(f"Outcome from {outcome.destination_phase} is not yet reconciled.")
            elif not outcome.is_terminal:
                blockers.append(f"Outcome from {outcome.destination_phase} is reconciled but not terminal (status: {outcome.authoritative_destination_status}).")
            if outcome.verification_status == OutcomeVerificationStatus.CONFLICTED:
                blockers.append(f"Outcome from {outcome.destination_phase} has conflicting destination records.")

        # 3. Check follow-ups
        for fup in follow_ups:
            if fup.is_mandatory and fup.status == FollowUpStatus.PENDING:
                blockers.append(f"Mandatory follow-up obligation unresolved: {fup.description}")
            elif fup.status == FollowUpStatus.BLOCKED:
                blockers.append(f"Follow-up obligation blocked: {fup.description}")
            elif fup.status == FollowUpStatus.WAIVED_BY_AUTHORIZED_POLICY:
                limitations.append(f"Follow-up waived under policy: {fup.description}")

        # 4. Check requirements
        for req in requirements:
            if req.is_mandatory and req.status not in (RequirementStatus.SATISFIED, RequirementStatus.WAIVED):
                if req.requirement_type != "REQUIRED_REVIEW":  # Review is satisfied at review step
                    blockers.append(f"Mandatory requirement not satisfied: {req.description}")

        # 5. Determine readiness state
        if any("conflicting" in b.lower() for b in blockers):
            readiness_state = CompletionReadinessState.CONFLICTED
        elif pending_handoffs > 0:
            readiness_state = CompletionReadinessState.HANDOFFS_PENDING
        elif pending_outcomes > 0:
            readiness_state = CompletionReadinessState.OUTCOMES_PENDING
        elif pending_fups > 0:
            readiness_state = CompletionReadinessState.FOLLOW_UP_PENDING
        elif len(blockers) > 0:
            readiness_state = CompletionReadinessState.BLOCKED
        elif len(limitations) > 0:
            readiness_state = CompletionReadinessState.READY_WITH_LIMITATIONS
        else:
            readiness_state = CompletionReadinessState.READY

        is_eligible_for_review = readiness_state in (
            CompletionReadinessState.READY,
            CompletionReadinessState.READY_WITH_LIMITATIONS,
        )

        return ReadinessEvaluationRecord(
            completion_id=completion_id,
            readiness_state=readiness_state,
            source_revision=source_revision,
            applicable_policy_version=policy_version,
            total_requirements=total_reqs,
            satisfied_requirements=sat_reqs,
            pending_requirements=pending_reqs,
            blocked_requirements=blocked_reqs,
            total_handoffs=total_handoffs,
            completed_handoffs=completed_handoffs,
            pending_handoffs=pending_handoffs,
            total_outcomes=total_outcomes,
            reconciled_outcomes=reconciled_outcomes,
            pending_outcomes=pending_outcomes,
            total_follow_ups=total_fups,
            satisfied_follow_ups=sat_fups,
            pending_follow_ups=pending_fups,
            blockers=blockers,
            limitations=limitations,
            missing_evidence_refs=missing_evidence,
            is_eligible_for_review=is_eligible_for_review,
            is_eligible_for_closure=False,  # Closure requires explicit authorization after review
            requires_human_review=True,
            evaluated_at=datetime.now(timezone.utc),
            evaluated_by="system",
        )

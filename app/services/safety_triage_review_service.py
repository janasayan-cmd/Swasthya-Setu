"""Phase 60: Safety Triage Human Review Service.

Enforces human surveillance supervisor authority, separation of duties,
and strict AI boundary constraints per TRD Section 21, 22 & 23.
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_triage import (
    HumanTriageReviewDecision,
    RoutingDestination,
    SafetyTriageRecord,
    TriageLifecycleState,
    TriageReviewRecord,
)


class SafetyTriageReviewService:
    """Manages human review submissions and AI boundary enforcement."""

    ALLOWED_REVIEWER_ROLES = {
        "CLINICAL_SAFETY_OFFICER",
        "GOVERNANCE_LEAD",
        "CHIEF_MEDICAL_OFFICER",
        "SAFETY_LEAD",
        "SAFETY_OFFICER",
        "ADMIN",
        "SUPER_ADMIN",
    }

    def submit_review(
        self,
        record: SafetyTriageRecord,
        decision: HumanTriageReviewDecision,
        rationale: str,
        reviewer_id: str,
        reviewer_role: str,
        routing_destination: Optional[RoutingDestination] = None,
        is_ai_agent: bool = False,
    ) -> TriageReviewRecord:
        """Process governed human triage review."""
        # 1. AI Boundary Enforcement (TRD Section 23)
        if is_ai_agent or reviewer_role.upper() in {"AI", "AI_AGENT", "AUTOMATION"}:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="AI systems cannot make governed triage decisions, authorize escalations, or bypass human review",
                status_code=403,
            )

        # 2. Role Authorization Check
        clean_role = reviewer_role.replace("UserRole.", "").upper()
        if clean_role not in self.ALLOWED_REVIEWER_ROLES and reviewer_role.upper() not in self.ALLOWED_REVIEWER_ROLES:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Role '{reviewer_role}' is not authorized to submit safety triage reviews",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        rev = TriageReviewRecord(
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            rationale=rationale,
            reviewed_at=now,
        )
        record.reviews.append(rev)

        # 3. Update Lifecycle State
        if decision == HumanTriageReviewDecision.CONTINUE:
            record.lifecycle_state = TriageLifecycleState.ROUTED
            record.requires_human_review = False
        elif decision == HumanTriageReviewDecision.ESCALATE:
            record.lifecycle_state = TriageLifecycleState.ESCALATION_REQUIRED
            record.is_escalated = True
        elif decision == HumanTriageReviewDecision.REASSESS:
            record.lifecycle_state = TriageLifecycleState.REASSESSMENT_REQUIRED
        elif decision == HumanTriageReviewDecision.REOPEN_REVIEW:
            record.lifecycle_state = TriageLifecycleState.REOPEN_REQUIRED
            record.reopen_triggered = True
        elif decision == HumanTriageReviewDecision.ROUTE_TO_INCIDENT:
            record.lifecycle_state = TriageLifecycleState.INCIDENT_ROUTING_REQUIRED
            record.is_escalated = True
        elif decision == HumanTriageReviewDecision.ROUTE_TO_ASSURANCE:
            record.lifecycle_state = TriageLifecycleState.ASSURANCE_ROUTING_REQUIRED
        elif decision == HumanTriageReviewDecision.ROUTE_TO_EFFECTIVENESS:
            record.lifecycle_state = TriageLifecycleState.EFFECTIVENESS_ROUTING_REQUIRED
        elif decision == HumanTriageReviewDecision.ROUTE_TO_GOVERNANCE:
            record.lifecycle_state = TriageLifecycleState.GOVERNANCE_ROUTING_REQUIRED
        elif decision == HumanTriageReviewDecision.ROUTE_TO_ACTION:
            record.lifecycle_state = TriageLifecycleState.ACTION_ROUTING_REQUIRED
        elif decision == HumanTriageReviewDecision.REQUEST_MORE_EVIDENCE:
            record.lifecycle_state = TriageLifecycleState.REVIEW_REQUIRED
            record.requires_human_review = True
        elif decision == HumanTriageReviewDecision.REJECT_CLASSIFICATION:
            record.lifecycle_state = TriageLifecycleState.TRIAGE_IN_PROGRESS
            record.requires_human_review = True

        return rev

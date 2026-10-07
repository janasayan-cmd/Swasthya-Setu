"""Phase 59: Safety Monitoring Human Review Service.

Governs human surveillance evaluation, disposition of detected safety signals,
and AI boundary enforcement per TRD Section 19 & 28.
"""

from datetime import datetime, timezone

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_monitoring import (
    HumanSurveillanceReviewDecision,
    MonitoringLifecycleState,
    MonitoringReviewRecord,
    SafetyMonitoringRecord,
)


class SafetyMonitoringReviewService:
    """Manages human surveillance reviews and AI boundary enforcement."""

    ALLOWED_REVIEWER_ROLES = {
        "CLINICAL_SAFETY_OFFICER",
        "GOVERNANCE_LEAD",
        "CHIEF_MEDICAL_OFFICER",
        "ADMIN",
        "SUPER_ADMIN",
        "SAFETY_LEAD",
        "SAFETY_OFFICER",
    }

    def submit_review(
        self,
        monitoring: SafetyMonitoringRecord,
        decision: HumanSurveillanceReviewDecision,
        rationale: str,
        reviewer_id: str,
        reviewer_role: str,
        is_ai_agent: bool = False,
    ) -> MonitoringReviewRecord:
        """Record human surveillance review decision."""
        # 1. AI Boundary Enforcement (TRD Section 19)
        if is_ai_agent or reviewer_role.upper() in {"AI", "AI_AGENT", "AUTOMATION"}:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="AI systems cannot approve surveillance reviews, reopen authorizations, or incident classifications",
                status_code=403,
            )

        # 2. Reviewer Role Authorization
        clean_role = reviewer_role.replace("UserRole.", "").upper()
        if clean_role not in self.ALLOWED_REVIEWER_ROLES and reviewer_role.upper() not in self.ALLOWED_REVIEWER_ROLES:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Role '{reviewer_role}' is not authorized to submit surveillance review decisions",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = MonitoringReviewRecord(
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            rationale=rationale,
            reviewed_at=now,
        )

        monitoring.reviews.append(record)

        # Lifecycle update
        if decision == HumanSurveillanceReviewDecision.CONTINUE:
            monitoring.lifecycle_state = MonitoringLifecycleState.OBSERVING
        elif decision == HumanSurveillanceReviewDecision.REASSESS:
            monitoring.lifecycle_state = MonitoringLifecycleState.REASSESSMENT_REQUIRED
        elif decision == HumanSurveillanceReviewDecision.REOPEN_REVIEW:
            monitoring.lifecycle_state = MonitoringLifecycleState.REOPEN_REQUIRED
        elif decision in (
            HumanSurveillanceReviewDecision.ESCALATE,
            HumanSurveillanceReviewDecision.ROUTE_TO_INCIDENT,
            HumanSurveillanceReviewDecision.ROUTE_TO_ASSURANCE,
            HumanSurveillanceReviewDecision.ROUTE_TO_EFFECTIVENESS,
            HumanSurveillanceReviewDecision.ROUTE_TO_GOVERNANCE,
        ):
            monitoring.lifecycle_state = MonitoringLifecycleState.ESCALATION_REQUIRED

        return record

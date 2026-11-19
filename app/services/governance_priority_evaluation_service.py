"""Phase 67: Governance Priority and Escalation Eligibility Service.

Evaluates governance priority deterministically based on policy, source severity,
materiality, exception category, and cross-workflow conflict indicators.

Mandatory Governance Distinction:
A governance priority is a workflow routing and assignment urgency indicator,
NOT an independent clinical severity classification or medical prognosis.
"""

from typing import List, Optional, Tuple

from app.schemas.governance_escalation import GovernanceEscalationRecord
from app.schemas.governance_exception import (
    ExceptionCategory,
    GovernanceExceptionRecord,
    GovernancePriority,
)


class GovernancePriorityEvaluationService:
    """Service evaluating policy-driven governance priority and escalation eligibility."""

    def evaluate_priority(
        self,
        escalation: GovernanceEscalationRecord,
        exceptions: List[GovernanceExceptionRecord],
        policy_version: str = "v1.0.0",
    ) -> Tuple[GovernancePriority, str]:
        """Evaluate deterministic governance priority level for an escalation."""
        # 1. Critical triggers
        has_critical_source = any(
            ex.source_severity.upper() == "CRITICAL" for ex in exceptions
        )
        has_critical_category = any(
            ex.category in {
                ExceptionCategory.SURVEILLANCE_THRESHOLD_ESCALATION,
                ExceptionCategory.INCIDENT_ESCALATION_REQUIRED,
                ExceptionCategory.CONFLICTING_AUTHORITATIVE_DECISIONS,
            }
            for ex in exceptions
        ) or escalation.primary_category in {
            ExceptionCategory.SURVEILLANCE_THRESHOLD_ESCALATION,
            ExceptionCategory.INCIDENT_ESCALATION_REQUIRED,
            ExceptionCategory.CONFLICTING_AUTHORITATIVE_DECISIONS,
        }

        if has_critical_source or has_critical_category:
            return (
                GovernancePriority.CRITICAL,
                f"Evaluated as CRITICAL under policy {policy_version}: Critical source severity or high-urgency category detected.",
            )

        # 2. Urgent triggers: High source severity or multiple material exceptions
        has_high_source = any(
            ex.source_severity.upper() == "HIGH" for ex in exceptions
        )
        material_exceptions_count = sum(1 for ex in exceptions if ex.is_material)
        has_blocking_category = any(
            ex.category in {
                ExceptionCategory.POST_CLOSURE_REASSESSMENT_REQUIRED,
                ExceptionCategory.HANDOFF_OUTCOME_CONFLICT,
                ExceptionCategory.COMPLETION_REQUIREMENT_BLOCKED,
                ExceptionCategory.MATERIAL_INTEGRITY_CHANGE,
            }
            for ex in exceptions
        ) or escalation.primary_category in {
            ExceptionCategory.POST_CLOSURE_REASSESSMENT_REQUIRED,
            ExceptionCategory.HANDOFF_OUTCOME_CONFLICT,
            ExceptionCategory.COMPLETION_REQUIREMENT_BLOCKED,
            ExceptionCategory.MATERIAL_INTEGRITY_CHANGE,
        }

        if has_high_source or (material_exceptions_count >= 3) or has_blocking_category:
            return (
                GovernancePriority.URGENT,
                f"Evaluated as URGENT under policy {policy_version}: High severity findings or blocking cross-workflow condition.",
            )

        # 3. High triggers: Moderate findings or failed governance actions
        has_moderate_source = any(
            ex.source_severity.upper() in {"MODERATE", "MEDIUM"} for ex in exceptions
        )
        has_action_failure = any(
            ex.category in {
                ExceptionCategory.GOVERNANCE_ACTION_FAILED,
                ExceptionCategory.EFFECTIVENESS_REVIEW_FAILED,
                ExceptionCategory.RISK_DISPOSITION_REVIEW_REQUIRED,
            }
            for ex in exceptions
        ) or escalation.primary_category in {
            ExceptionCategory.GOVERNANCE_ACTION_FAILED,
            ExceptionCategory.EFFECTIVENESS_REVIEW_FAILED,
            ExceptionCategory.RISK_DISPOSITION_REVIEW_REQUIRED,
        }

        if has_moderate_source or has_action_failure or len(exceptions) >= 2:
            return (
                GovernancePriority.HIGH,
                f"Evaluated as HIGH under policy {policy_version}: Correlated multi-workflow exceptions or action failure.",
            )

        # 4. Elevated triggers: Single minor/informational exception
        if exceptions:
            return (
                GovernancePriority.ELEVATED,
                f"Evaluated as ELEVATED under policy {policy_version}: Single standard governance exception recorded.",
            )

        # 5. Routine default
        return (
            GovernancePriority.ROUTINE,
            f"Evaluated as ROUTINE under policy {policy_version}: Standard governance coordination workflow.",
        )


# Global singleton
_global_priority_service = GovernancePriorityEvaluationService()


def get_governance_priority_evaluation_service() -> GovernancePriorityEvaluationService:
    """Dependency provider for priority evaluation service."""
    return _global_priority_service

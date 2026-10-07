"""Phase 55: Action Effectiveness Criteria & Objective Service.

Validates bounded safety objectives and resolves policy-driven effectiveness criteria.
Rejects vague, non-testable objectives like 'make the system safer' or 'improve healthcare'.
"""

from typing import List, Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    EffectivenessCriterion,
    EffectivenessCriterionCategory,
    SafetyObjective,
)


_VAGUE_OBJECTIVE_PATTERNS = [
    "make the system safer",
    "improve healthcare",
    "improve patient safety",
    "ensure no patient is harmed",
    "fix everything",
    "make it safe",
    "zero harm",
]


class ActionEffectivenessCriteriaService:
    """Service for resolving and validating bounded safety objectives and criteria."""

    def validate_safety_objective(self, objective: SafetyObjective) -> None:
        """Validate that safety objective is bounded, specific, and testable."""
        if not objective.description or len(objective.description.strip()) < 10:
            raise AppException(
                code=ErrorCode.OBJECTIVE_MISSING,
                message="Safety objective description must be at least 10 characters and clearly bounded.",
                status_code=400,
            )

        desc_lower = objective.description.lower().strip()
        for vague in _VAGUE_OBJECTIVE_PATTERNS:
            if vague in desc_lower:
                raise AppException(
                    code=ErrorCode.OBJECTIVE_MISSING,
                    message=(
                        f"Safety objective contains vague, non-testable claim: '{vague}'. "
                        "Objectives must be bounded to specific failure modes or control metrics."
                    ),
                    status_code=400,
                )

        if not objective.bounded_failure_mode or len(objective.bounded_failure_mode.strip()) < 5:
            raise AppException(
                code=ErrorCode.OBJECTIVE_MISSING,
                message="Safety objective must define a specific bounded failure mode.",
                status_code=400,
            )

        if not objective.is_evidence_testable:
            raise AppException(
                code=ErrorCode.OBJECTIVE_MISSING,
                message="Safety objective must be evidence-testable.",
                status_code=400,
            )

    def resolve_default_criteria(
        self,
        objective: SafetyObjective,
        action_type: Optional[str] = None,
    ) -> List[EffectivenessCriterion]:
        """Generate default policy-driven criteria if caller does not supply custom criteria."""
        criteria: List[EffectivenessCriterion] = []

        # Criterion 1: Control execution rate or failure rate
        if "CONFIG" in (action_type or "") or "CONFIGURATION" in objective.bounded_failure_mode.upper():
            criteria.append(
                EffectivenessCriterion(
                    criterion_id=f"crit-{uuid.uuid4().hex[:8]}",
                    category=EffectivenessCriterionCategory.CONFIGURATION_CONFORMANCE,
                    metric_name="configuration_drift_free",
                    description="Verified that active runtime configuration conforms to approved safety baseline",
                    expected_state="CONFORMANT",
                    operator="==",
                    observation_period_hours=24,
                    min_sample_size=1,
                )
            )
        else:
            criteria.append(
                EffectivenessCriterion(
                    criterion_id=f"crit-{uuid.uuid4().hex[:8]}",
                    category=EffectivenessCriterionCategory.CONTROL_EXECUTION_RATE,
                    metric_name="control_execution_rate",
                    description="Observed execution of safety control on applicable requests",
                    expected_threshold=0.99,
                    operator=">=",
                    unit="ratio",
                    observation_period_hours=24,
                    min_sample_size=10,
                )
            )

        # Criterion 2: Recurrence rate reduction
        criteria.append(
            EffectivenessCriterion(
                criterion_id=f"crit-{uuid.uuid4().hex[:8]}",
                category=EffectivenessCriterionCategory.RECURRENCE_RATE,
                metric_name="safety_finding_recurrence_count",
                description="Observed recurrence of source finding during observation window",
                expected_threshold=0.0,
                operator="==",
                unit="count",
                observation_period_hours=24,
                min_sample_size=1,
            )
        )

        return criteria

    def validate_criteria(self, criteria: List[EffectivenessCriterion]) -> None:
        """Validate list of criteria for completeness and testability."""
        if not criteria:
            raise AppException(
                code=ErrorCode.CRITERIA_MISSING,
                message="At least one effectiveness criterion must be defined.",
                status_code=400,
            )

        for c in criteria:
            if not c.metric_name or not c.description:
                raise AppException(
                    code=ErrorCode.CRITERIA_MISSING,
                    message="Each criterion must specify a metric_name and description.",
                    status_code=400,
                )
            if c.expected_threshold is None and c.expected_state is None:
                raise AppException(
                    code=ErrorCode.CRITERIA_MISSING,
                    message=f"Criterion '{c.metric_name}' must have either expected_threshold or expected_state.",
                    status_code=400,
                )

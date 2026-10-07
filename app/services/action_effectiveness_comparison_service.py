"""Phase 55: Expected vs Observed Comparison Service.

Compares expected criteria against observed post-action state.
Maintains baseline scope/version alignment and accounts for confounding changes.
Strictly prohibits claiming causal proof or universal safety scores.
"""

from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    BaselineMeasurement,
    ConfoundingChange,
    EffectivenessCriterion,
    EffectivenessScope,
    ExpectedVsObservedComparison,
    PostActionEvidenceItem,
    UncertaintyLevel,
)


class ActionEffectivenessComparisonService:
    """Service for comparing expected criteria targets with observed evidence."""

    def validate_baseline_alignment(
        self,
        baseline: Optional[BaselineMeasurement],
        evaluation_scope: EffectivenessScope,
    ) -> None:
        """Ensure baseline matches evaluation scope and environment."""
        if not baseline:
            return

        if baseline.scope.organization_id != evaluation_scope.organization_id:
            raise AppException(
                code=ErrorCode.BASELINE_INVALID,
                message="Baseline organization does not match evaluation organization scope.",
                status_code=400,
            )

        if baseline.scope.environment != evaluation_scope.environment:
            raise AppException(
                code=ErrorCode.BASELINE_INVALID,
                message=(
                    f"Baseline environment ('{baseline.scope.environment}') does not match "
                    f"evaluation environment ('{evaluation_scope.environment}'). "
                    "Cross-environment comparison is prohibited."
                ),
                status_code=400,
            )

    def execute_comparison(
        self,
        criteria: List[EffectivenessCriterion],
        evidence_items: List[PostActionEvidenceItem],
        baseline: Optional[BaselineMeasurement] = None,
        confounding_changes: Optional[List[ConfoundingChange]] = None,
    ) -> List[ExpectedVsObservedComparison]:
        """Perform comparison across all criteria."""
        confounding_changes = confounding_changes or []
        confounding_summaries = [f"{c.change_type}: {c.description}" for c in confounding_changes]

        # Consolidate observed metrics from evidence items
        observed_data: Dict[str, Any] = {}
        numerators: Dict[str, float] = {}
        denominators: Dict[str, float] = {}

        for item in evidence_items:
            for k, v in item.data_payload.items():
                observed_data[k] = v
                if f"{k}_numerator" in item.data_payload:
                    numerators[k] = float(item.data_payload[f"{k}_numerator"])
                if f"{k}_denominator" in item.data_payload:
                    denominators[k] = float(item.data_payload[f"{k}_denominator"])

        comparisons: List[ExpectedVsObservedComparison] = []

        for crit in criteria:
            metric = crit.metric_name
            observed_val = observed_data.get(metric)
            num = numerators.get(metric)
            den = denominators.get(metric)

            # Determine baseline if metric matches
            base_val: Optional[float] = None
            if baseline and baseline.metric_name == metric:
                base_val = baseline.baseline_value

            is_conforming = False
            diff_desc = ""

            if observed_val is None:
                is_conforming = False
                diff_desc = f"No observed evidence available for metric '{metric}'"
            elif crit.operator == ">=" and crit.expected_threshold is not None:
                try:
                    obs_f = float(observed_val)
                    is_conforming = obs_f >= crit.expected_threshold
                    diff_desc = f"Observed {obs_f} vs required >= {crit.expected_threshold}"
                except (ValueError, TypeError):
                    is_conforming = False
                    diff_desc = f"Cannot compare non-numeric observed value '{observed_val}'"
            elif crit.operator == "<=" and crit.expected_threshold is not None:
                try:
                    obs_f = float(observed_val)
                    is_conforming = obs_f <= crit.expected_threshold
                    diff_desc = f"Observed {obs_f} vs required <= {crit.expected_threshold}"
                except (ValueError, TypeError):
                    is_conforming = False
                    diff_desc = f"Cannot compare non-numeric observed value '{observed_val}'"
            elif crit.operator == "==":
                if crit.expected_threshold is not None:
                    try:
                        obs_f = float(observed_val)
                        is_conforming = obs_f == crit.expected_threshold
                        diff_desc = f"Observed {obs_f} vs required == {crit.expected_threshold}"
                    except (ValueError, TypeError):
                        is_conforming = False
                elif crit.expected_state is not None:
                    is_conforming = str(observed_val).strip().upper() == str(crit.expected_state).strip().upper()
                    diff_desc = f"Observed state '{observed_val}' vs required state '{crit.expected_state}'"
            elif crit.operator == "DECREASE" and base_val is not None:
                try:
                    obs_f = float(observed_val)
                    is_conforming = obs_f < base_val
                    diff_desc = f"Observed {obs_f} decreased compared to baseline {base_val}"
                except (ValueError, TypeError):
                    is_conforming = False
            elif crit.expected_state is not None:
                is_conforming = str(observed_val).strip().upper() == str(crit.expected_state).strip().upper()
                diff_desc = f"Observed state '{observed_val}' vs expected '{crit.expected_state}'"

            # Determine uncertainty
            uncertainty = UncertaintyLevel.LOW
            if confounding_changes:
                uncertainty = UncertaintyLevel.HIGH if len(confounding_changes) > 1 else UncertaintyLevel.MODERATE
            elif observed_val is None:
                uncertainty = UncertaintyLevel.UNRESOLVED

            target_display = str(crit.expected_threshold if crit.expected_threshold is not None else crit.expected_state)

            comparisons.append(
                ExpectedVsObservedComparison(
                    criterion_id=crit.criterion_id,
                    metric_name=crit.metric_name,
                    expected_target=f"{crit.operator} {target_display}",
                    observed_value=observed_val if observed_val is not None else "N/A",
                    numerator=num,
                    denominator=den,
                    unit=crit.unit,
                    baseline_value=base_val,
                    is_conforming=is_conforming,
                    difference_description=diff_desc,
                    confounding_factors=confounding_summaries,
                    uncertainty_level=uncertainty,
                )
            )

        return comparisons

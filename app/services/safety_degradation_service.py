"""Phase 52: Safety Degradation Detection Service.

Detects gradual control degradation over observation windows.

Degradation detection identifies:
- Rising safety-gate failures
- Increasing provider timeouts
- Increasing insufficient-context outcomes
- Decreasing validation coverage
- Increasing stale-context events
- Increased workflow bypasses
- Declining human-review completion
- Repeated notification delivery failure
- Increasing reconciliation conflicts
- Increased data-quality failures

Key distinctions:
  CONTROL DEGRADATION != INCIDENT
  CONTROL FAILURE != PATIENT HARM
  CONTROL FAILURE != ROOT CAUSE

Thresholds MUST come from approved configuration/policy.
No clinical thresholds are hardcoded in this service.

Phase 50 remains authoritative for safety learning and trend analysis.
Phase 52 consumes relevant observations to detect assurance degradation.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.safety_assurance import (
    AssuranceEvaluationRecord,
    AssuranceRouteTarget,
    BypassRecord,
    ControlEffectivenessState,
    DegradationRecord,
    DegradationState,
    RegressionRecord,
)
from app.repositories.safety_assurance_repository import (
    SafetyAssuranceRepository,
    safety_assurance_repository,
)

logger = logging.getLogger("app.services.safety_degradation_service")


class SafetyDegradationService:
    """Detects and records control degradation patterns.

    Degradation is an operational signal — not a clinical harm determination.
    Thresholds must be sourced from approved policy configuration.
    """

    def __init__(
        self,
        assurance_repo: Optional[SafetyAssuranceRepository] = None,
    ) -> None:
        self._repo = assurance_repo or safety_assurance_repository

    def detect_degradation(
        self,
        evaluation: AssuranceEvaluationRecord,
        policy_thresholds: Dict[str, Any],
    ) -> Optional[DegradationRecord]:
        """Detect degradation based on evaluation outcome and policy thresholds.

        Thresholds are sourced from policy_thresholds dict (never hardcoded).

        Args:
            evaluation: The completed effectiveness evaluation.
            policy_thresholds: Configuration-derived thresholds (from Phase 25).

        Returns:
            DegradationRecord if degradation detected, None otherwise.
        """
        effectiveness = evaluation.effectiveness_state
        degradation_mapping = {
            ControlEffectivenessState.DEGRADED: DegradationState.DEGRADED,
            ControlEffectivenessState.FAILED: DegradationState.FAILED,
            ControlEffectivenessState.PARTIALLY_EFFECTIVE: DegradationState.DEGRADED,
        }

        degradation_state = degradation_mapping.get(effectiveness)
        if degradation_state is None:
            return None

        # Build signal description (no PHI)
        signals = []
        if evaluation.bypass_detected:
            signals.append(
                f"bypass_count={evaluation.bypass_count}"
            )
        if evaluation.effectiveness_score:
            score = evaluation.effectiveness_score
            if score.failure_rate_available and score.failure_rate is not None:
                threshold = policy_thresholds.get("failure_rate_threshold")
                signals.append(
                    f"failure_rate={score.failure_rate:.3f}"
                    + (f" (threshold={threshold})" if threshold else "")
                )
            if score.bypass_rate_available and score.bypass_rate is not None:
                signals.append(f"bypass_rate={score.bypass_rate:.3f}")
            if score.evidence_completeness_score is not None:
                signals.append(
                    f"evidence_completeness={score.evidence_completeness_score:.2f}"
                )

        signal_description = "; ".join(signals) if signals else effectiveness.value

        record = DegradationRecord(
            control_id=evaluation.control_id,
            control_version=evaluation.control_version,
            evaluation_id=evaluation.evaluation_id,
            degradation_state=degradation_state,
            degradation_signal=signal_description,
            metric_name="assurance_evaluation_outcome",
            observed_value=None,
            threshold_value=policy_thresholds.get("failure_rate_threshold"),
            threshold_source=policy_thresholds.get("threshold_source", "policy_config"),
            organization_id=evaluation.organization_id,
            facility_id=evaluation.facility_id,
            detected_at=datetime.now(timezone.utc),
            observation_start=evaluation.scope.observation_start,
            observation_end=evaluation.scope.observation_end,
        )

        record = self._repo.save_degradation(record)

        logger.warning(
            "Control degradation detected",
            extra={
                "control_id": evaluation.control_id,
                "control_version": evaluation.control_version,
                "evaluation_id": evaluation.evaluation_id,
                "degradation_state": degradation_state.value,
                "signal": signal_description,
            },
        )

        return record

    def detect_regression(
        self,
        current_evaluation: AssuranceEvaluationRecord,
        reference_evaluation: AssuranceEvaluationRecord,
    ) -> Optional[RegressionRecord]:
        """Detect regression between current and a reference evaluation.

        Regression = previously effective control has become degraded.

        IMPORTANT: Do not compare across incompatible versions as equivalent.
        is_version_comparable is set based on version compatibility check.

        Args:
            current_evaluation: Latest evaluation record.
            reference_evaluation: Previously accepted baseline evaluation.

        Returns:
            RegressionRecord if regression detected, None otherwise.
        """
        # Reference must have been effective
        if reference_evaluation.effectiveness_state not in (
            ControlEffectivenessState.EFFECTIVE_OBSERVED,
            ControlEffectivenessState.PARTIALLY_EFFECTIVE,
        ):
            return None

        # Current must show degradation
        regressed_states = {
            ControlEffectivenessState.DEGRADED,
            ControlEffectivenessState.FAILED,
            ControlEffectivenessState.INSUFFICIENT_EVIDENCE,
        }
        if current_evaluation.effectiveness_state not in regressed_states:
            return None

        # Check version comparability
        is_comparable = (
            current_evaluation.control_version == reference_evaluation.control_version
        )
        incompatibility_note = None if is_comparable else (
            f"Current version '{current_evaluation.control_version}' differs from "
            f"reference version '{reference_evaluation.control_version}'. "
            "Version comparison may not be valid. "
            "HISTORICAL EFFECTIVENESS != CURRENT EFFECTIVENESS."
        )

        signals: List[str] = [
            f"Was {reference_evaluation.effectiveness_state.value}",
            f"Now {current_evaluation.effectiveness_state.value}",
        ]
        if current_evaluation.bypass_detected:
            signals.append(f"bypass_count={current_evaluation.bypass_count}")

        record = RegressionRecord(
            control_id=current_evaluation.control_id,
            current_evaluation_id=current_evaluation.evaluation_id,
            reference_evaluation_id=reference_evaluation.evaluation_id,
            current_control_version=current_evaluation.control_version,
            reference_control_version=reference_evaluation.control_version,
            regression_description=(
                f"Control '{current_evaluation.control_id}' regressed from "
                f"{reference_evaluation.effectiveness_state.value} to "
                f"{current_evaluation.effectiveness_state.value}."
            ),
            regression_signals=signals,
            organization_id=current_evaluation.organization_id,
            facility_id=current_evaluation.facility_id,
            detected_at=datetime.now(timezone.utc),
            is_version_comparable=is_comparable,
            incompatibility_note=incompatibility_note,
        )

        record = self._repo.save_regression(record)

        logger.warning(
            "Control regression detected",
            extra={
                "control_id": current_evaluation.control_id,
                "current_version": current_evaluation.control_version,
                "reference_version": reference_evaluation.control_version,
                "current_state": current_evaluation.effectiveness_state.value,
                "is_version_comparable": is_comparable,
            },
        )

        return record

    def detect_bypass(
        self,
        evaluation: AssuranceEvaluationRecord,
        bypass_signal: str,
        bypass_count: int,
        policy_requires_incident_routing: bool = False,
    ) -> Optional[BypassRecord]:
        """Record a detected control bypass event.

        A bypass is a SAFETY SIGNAL — not automatically an incident.
        Route confirmed or policy-defined events to Phase 49.

        Args:
            evaluation: The assurance evaluation that detected the bypass.
            bypass_signal: Observable signal indicating bypass (non-PHI).
            bypass_count: Number of bypasses observed.
            policy_requires_incident_routing: Whether policy mandates Phase 49 routing.

        Returns:
            BypassRecord.
        """
        if bypass_count <= 0:
            return None

        record = BypassRecord(
            control_id=evaluation.control_id,
            control_version=evaluation.control_version,
            evaluation_id=evaluation.evaluation_id,
            bypass_signal=bypass_signal,
            bypass_description=(
                f"{bypass_count} bypass(es) observed for control "
                f"'{evaluation.control_id}' v{evaluation.control_version}."
            ),
            organization_id=evaluation.organization_id,
            facility_id=evaluation.facility_id,
            detected_at=datetime.now(timezone.utc),
            observation_timestamp=evaluation.scope.observation_end,
            requires_incident_routing=policy_requires_incident_routing,
        )

        if policy_requires_incident_routing:
            record.routed_to = AssuranceRouteTarget.PHASE_49_INCIDENT_MANAGEMENT
            logger.warning(
                "Bypass requires incident routing per policy",
                extra={
                    "bypass_id": record.bypass_id,
                    "control_id": evaluation.control_id,
                },
            )

        record = self._repo.save_bypass(record)

        logger.info(
            "Control bypass recorded",
            extra={
                "bypass_id": record.bypass_id,
                "control_id": evaluation.control_id,
                "bypass_count": bypass_count,
            },
        )

        return record

    def list_degradations(
        self,
        control_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        state: Optional[DegradationState] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DegradationRecord]:
        """List degradation records."""
        return self._repo.list_degradations(
            control_id=control_id,
            organization_id=organization_id,
            facility_id=facility_id,
            state=state,
            limit=limit,
            offset=offset,
        )

    def list_regressions(
        self,
        control_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RegressionRecord]:
        """List regression detection records."""
        return self._repo.list_regressions(
            control_id=control_id,
            organization_id=organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_bypasses(
        self,
        control_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BypassRecord]:
        """List bypass detection records."""
        return self._repo.list_bypasses(
            control_id=control_id,
            organization_id=organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )


# Global singleton
safety_degradation_service = SafetyDegradationService()

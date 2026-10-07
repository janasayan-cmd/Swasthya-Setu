"""Phase 57: Safety Rollout Closed-Loop Routing Service.

Dispatches authoritative evidence and operational signals to:
- Phase 52: Clinical Safety Assurance
- Phase 55: Post-Action Effectiveness Evaluation
- Phase 56: Continuous Improvement Feedback
- Phase 51: Safety Change Governance & Rollback Approval
- Phase 48: Runtime Safety Enforcement Boundary
"""

from datetime import datetime, timezone
from typing import Any, Dict

from app.schemas.safety_rollout import RolloutRoutingRecord, SafetyRolloutRecord


class SafetyRolloutRoutingService:
    """Manages cross-phase downstream routing for Phase 57 rollout events."""

    @staticmethod
    def route_to_phase52_assurance(
        rollout: SafetyRolloutRecord, verification_summary: Dict[str, Any]
    ) -> RolloutRoutingRecord:
        """Route verified rollout data to Phase 52 for clinical safety assurance."""
        record = RolloutRoutingRecord(
            destination_phase="Phase 52",
            signal_type="ROLLOUT_DEPLOYMENT_ASSURANCE_EVIDENCE",
            payload_summary={
                "rollout_id": rollout.rollout_id,
                "change_id": rollout.change_id,
                "version": rollout.target_version,
                "stage": rollout.current_stage.value,
                "scope": rollout.scope.model_dump(),
                "verified_controls_count": len(rollout.safety_controls_verified),
                "verification_summary": verification_summary,
            },
            timestamp=datetime.now(timezone.utc),
            status="SENT",
        )
        rollout.routings.append(record)
        return record

    @staticmethod
    def route_to_phase55_effectiveness(
        rollout: SafetyRolloutRecord, observation_summary: Dict[str, Any]
    ) -> RolloutRoutingRecord:
        """Route post-deployment observation results to Phase 55 for outcome effectiveness."""
        record = RolloutRoutingRecord(
            destination_phase="Phase 55",
            signal_type="POST_DEPLOYMENT_OBSERVATION_EVALUATION",
            payload_summary={
                "rollout_id": rollout.rollout_id,
                "change_id": rollout.change_id,
                "version": rollout.target_version,
                "stage": rollout.current_stage.value,
                "scope": rollout.scope.model_dump(),
                "observation_summary": observation_summary,
            },
            timestamp=datetime.now(timezone.utc),
            status="SENT",
        )
        rollout.routings.append(record)
        return record

    @staticmethod
    def route_to_phase56_feedback(
        rollout: SafetyRolloutRecord, failure_reason: str, is_regression: bool = False
    ) -> RolloutRoutingRecord:
        """Route rollout failures, pauses, rollbacks, or regressions to Phase 56."""
        record = RolloutRoutingRecord(
            destination_phase="Phase 56",
            signal_type="ROLLOUT_FAILURE_OR_REGRESSION_SIGNAL",
            payload_summary={
                "rollout_id": rollout.rollout_id,
                "change_id": rollout.change_id,
                "change_proposal_id": rollout.change_proposal_id,
                "version": rollout.target_version,
                "stage": rollout.current_stage.value,
                "failure_reason": failure_reason,
                "is_regression": is_regression,
                "is_rolled_back": rollout.is_rolled_back,
            },
            timestamp=datetime.now(timezone.utc),
            status="SENT",
        )
        rollout.routings.append(record)
        return record

    @staticmethod
    def route_to_phase51_governance(
        rollout: SafetyRolloutRecord, request_type: str, details: Dict[str, Any]
    ) -> RolloutRoutingRecord:
        """Route to Phase 51 for governed rollback or reapproval decisions."""
        record = RolloutRoutingRecord(
            destination_phase="Phase 51",
            signal_type=f"GOVERNANCE_{request_type.upper()}",
            payload_summary={
                "rollout_id": rollout.rollout_id,
                "change_id": rollout.change_id,
                "version": rollout.target_version,
                "details": details,
            },
            timestamp=datetime.now(timezone.utc),
            status="SENT",
        )
        rollout.routings.append(record)
        return record

    @staticmethod
    def route_to_phase48_runtime_safety(
        rollout: SafetyRolloutRecord, event_type: str
    ) -> RolloutRoutingRecord:
        """Notify Phase 48 of active safety rollout transitions or runtime pauses."""
        record = RolloutRoutingRecord(
            destination_phase="Phase 48",
            signal_type=f"RUNTIME_SAFETY_{event_type.upper()}",
            payload_summary={
                "rollout_id": rollout.rollout_id,
                "target_controls": rollout.scope.target_controls,
                "scope": rollout.scope.model_dump(),
                "is_paused": rollout.is_paused,
            },
            timestamp=datetime.now(timezone.utc),
            status="SENT",
        )
        rollout.routings.append(record)
        return record

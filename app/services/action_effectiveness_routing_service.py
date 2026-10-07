"""Phase 55: Action Effectiveness Closed-Loop Routing Service.

Dispatches validated effectiveness outcomes to authoritative subsystems:
- Phase 52 (Control Assurance): continuous control validation
- Phase 53 (Safety Reporting): governed evidence inclusion
- Phase 50 (Safety Learning): recurrence & pattern learning
- Phase 51 (Safety Governance): residual risk & control redesign
- Phase 49 (Incident Management): incident review flagging
- Phase 54 (Action Orchestration): follow-up / reopening requests
"""

from datetime import datetime, timezone
import uuid

from app.schemas.action_effectiveness import (
    EffectivenessEvaluationRecord,
    EffectivenessState,
    RoutingRecord,
)


class ActionEffectivenessRoutingService:
    """Service for closed-loop downstream routing of effectiveness findings."""

    def route_feedback(
        self,
        evaluation: EffectivenessEvaluationRecord,
    ) -> EffectivenessEvaluationRecord:
        """Route effectiveness results based on state and policy."""
        # 1. Always route to Phase 52 (Assurance) and Phase 53 (Oversight)
        evaluation.routings.append(
            RoutingRecord(
                routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                destination_phase="Phase 52",
                signal_type="CONTROL_ASSURANCE_FEEDBACK",
                payload_summary={
                    "evaluation_id": evaluation.evaluation_id,
                    "action_id": evaluation.action_id,
                    "target_control_id": evaluation.safety_objective.target_control_id,
                    "effectiveness_state": evaluation.effectiveness_state.value,
                    "is_sustained": evaluation.is_sustained,
                },
                timestamp=datetime.now(timezone.utc),
                status="SENT",
            )
        )

        evaluation.routings.append(
            RoutingRecord(
                routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                destination_phase="Phase 53",
                signal_type="OVERSIGHT_EVIDENCE_UPDATE",
                payload_summary={
                    "evaluation_id": evaluation.evaluation_id,
                    "action_id": evaluation.action_id,
                    "effectiveness_state": evaluation.effectiveness_state.value,
                },
                timestamp=datetime.now(timezone.utc),
                status="SENT",
            )
        )

        # 2. If Ineffective, Regressed, or Failed -> Route to Phase 50 (Learning), 51 (Governance), 54 (Actions)
        if evaluation.effectiveness_state in (
            EffectivenessState.FAILED,
            EffectivenessState.REGRESSED,
            EffectivenessState.NO_CLEAR_IMPROVEMENT,
            EffectivenessState.DEGRADED,
            EffectivenessState.PARTIALLY_EFFECTIVE,
        ):
            evaluation.routings.append(
                RoutingRecord(
                    routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                    destination_phase="Phase 50",
                    signal_type="INEFFECTIVE_ACTION_LEARNING_SIGNAL",
                    payload_summary={
                        "evaluation_id": evaluation.evaluation_id,
                        "failure_mode": evaluation.safety_objective.bounded_failure_mode,
                        "effectiveness_state": evaluation.effectiveness_state.value,
                    },
                    timestamp=datetime.now(timezone.utc),
                    status="SENT",
                )
            )

            evaluation.routings.append(
                RoutingRecord(
                    routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                    destination_phase="Phase 51",
                    signal_type="RESIDUAL_RISK_RECONSIDERATION_SIGNAL",
                    payload_summary={
                        "evaluation_id": evaluation.evaluation_id,
                        "action_id": evaluation.action_id,
                        "reason": f"Action achieved state {evaluation.effectiveness_state.value}",
                    },
                    timestamp=datetime.now(timezone.utc),
                    status="SENT",
                )
            )

            evaluation.routings.append(
                RoutingRecord(
                    routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                    destination_phase="Phase 54",
                    signal_type="REQUEST_ACTION_FOLLOW_UP_OR_REOPEN",
                    payload_summary={
                        "action_id": evaluation.action_id,
                        "evaluation_id": evaluation.evaluation_id,
                        "suggested_action": "REOPEN_OR_REASSESS",
                    },
                    timestamp=datetime.now(timezone.utc),
                    status="SENT",
                )
            )

        # 3. If Regressed or Critical Control Failed -> Signal Phase 49 for Incident Review consideration
        if evaluation.effectiveness_state in (EffectivenessState.REGRESSED, EffectivenessState.FAILED):
            evaluation.routings.append(
                RoutingRecord(
                    routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                    destination_phase="Phase 49",
                    signal_type="INCIDENT_REVIEW_CONSIDERATION_SIGNAL",
                    payload_summary={
                        "evaluation_id": evaluation.evaluation_id,
                        "action_id": evaluation.action_id,
                        "note": "Phase 49 independently decides whether an incident exists",
                    },
                    timestamp=datetime.now(timezone.utc),
                    status="SENT",
                )
            )

        return evaluation

"""Phase 56: Safety Improvement Closed-Loop Routing Service.

Dispatches continuous improvement signals, proposals, and feedback to authoritative subsystems:
- Phase 51 (Safety Governance): change proposal routing
- Phase 52 (Safety Assurance): control adaptation feedback
- Phase 53 (Safety Oversight): continuous improvement evidence
- Phase 50 (Safety Learning): recurring patterns & learning signals
- Phase 49 (Safety Incidents): incident review consideration
- Phase 54 (Action Orchestration): follow-up actions and reopening
- Phase 48 (Safety Controls): runtime guardrail notifications
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from app.schemas.safety_improvement import (
    ImprovementRoutingRecord,
    ImprovementSignalType,
    SafetyImprovementRecord,
)


class SafetyImprovementRoutingService:
    """Service for dispatching governed improvement signals across HealthSetu subsystems."""

    def route_to_phase51_governance(
        self,
        improvement: SafetyImprovementRecord,
    ) -> ImprovementRoutingRecord:
        """Dispatch ready change proposal to Phase 51 governance engine."""
        proposal = improvement.change_proposal
        routing = ImprovementRoutingRecord(
            routing_id=f"rt-{uuid.uuid4().hex[:8]}",
            destination_phase="Phase 51",
            signal_type="SAFETY_CHANGE_REQUEST_SUBMISSION",
            payload_summary={
                "improvement_id": improvement.improvement_id,
                "proposal_id": proposal.proposal_id if proposal else None,
                "change_category": proposal.change_category.value if proposal else None,
                "problem_statement": proposal.problem_statement if proposal else None,
                "scope": improvement.scope.model_dump(),
            },
            timestamp=datetime.now(timezone.utc),
            status="SENT",
        )
        improvement.routings.append(routing)
        return routing

    def route_general_feedback(
        self,
        improvement: SafetyImprovementRecord,
    ) -> SafetyImprovementRecord:
        """Route assurance, oversight, learning, and incident feedback based on signals."""
        # 1. Route to Phase 52 (Assurance) and Phase 53 (Oversight)
        improvement.routings.append(
            ImprovementRoutingRecord(
                routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                destination_phase="Phase 52",
                signal_type="CONTROL_ADAPTATION_ASSURANCE_FEEDBACK",
                payload_summary={
                    "improvement_id": improvement.improvement_id,
                    "signal_type": improvement.signal_type.value,
                    "response_type": improvement.response_type.value,
                },
                timestamp=datetime.now(timezone.utc),
                status="SENT",
            )
        )

        improvement.routings.append(
            ImprovementRoutingRecord(
                routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                destination_phase="Phase 53",
                signal_type="OVERSIGHT_CONTINUOUS_IMPROVEMENT_UPDATE",
                payload_summary={
                    "improvement_id": improvement.improvement_id,
                    "priority": improvement.priority.value,
                    "lifecycle_state": improvement.lifecycle_state.value,
                },
                timestamp=datetime.now(timezone.utc),
                status="SENT",
            )
        )

        # 2. If Recurring -> Route to Phase 50 (Learning)
        if improvement.is_recurring:
            improvement.routings.append(
                ImprovementRoutingRecord(
                    routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                    destination_phase="Phase 50",
                    signal_type="RECURRING_FAILURE_PATTERN_SIGNAL",
                    payload_summary={
                        "improvement_id": improvement.improvement_id,
                        "recurrence_count": improvement.recurrence_count,
                        "signal_type": improvement.signal_type.value,
                    },
                    timestamp=datetime.now(timezone.utc),
                    status="SENT",
                )
            )

        # 3. If Regression -> Route to Phase 49 (Incidents) & Phase 54 (Action follow-up)
        if improvement.is_regression or improvement.signal_type == ImprovementSignalType.CONTROL_REGRESSION:
            improvement.routings.append(
                ImprovementRoutingRecord(
                    routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                    destination_phase="Phase 49",
                    signal_type="REGRESSION_INCIDENT_REVIEW_CONSIDERATION",
                    payload_summary={
                        "improvement_id": improvement.improvement_id,
                        "note": "Phase 49 independently governs incident thresholds",
                    },
                    timestamp=datetime.now(timezone.utc),
                    status="SENT",
                )
            )

            improvement.routings.append(
                ImprovementRoutingRecord(
                    routing_id=f"rt-{uuid.uuid4().hex[:8]}",
                    destination_phase="Phase 54",
                    signal_type="REQUEST_ACTION_FOLLOW_UP_REOPEN",
                    payload_summary={
                        "improvement_id": improvement.improvement_id,
                        "source_action_id": improvement.source_action_id,
                    },
                    timestamp=datetime.now(timezone.utc),
                    status="SENT",
                )
            )

        return improvement

"""Phase 50: Corrective Action Effectiveness Service.

Evaluates whether historical corrective actions are correlated with
reduced recurrence within observation windows.
Distinguishes NO_RECURRENCE_OBSERVED from absolute elimination of risk.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Optional

from app.core.exceptions import SafetyLearningNotFoundException
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.repositories.safety_learning_repository import (
    SafetyLearningRepository,
    safety_learning_repository,
)
from app.schemas.corrective_actions import ActionStatus
from app.schemas.safety_effectiveness import (
    CorrectiveActionEffectivenessRecord,
    EffectivenessState,
)

logger = logging.getLogger("app.safety_effectiveness_service")


class SafetyEffectivenessService:
    """Service governing corrective-action post-implementation recurrence evaluation."""

    def __init__(
        self,
        learning_repo: Optional[SafetyLearningRepository] = None,
        incident_repo: Optional[SafetyIncidentRepository] = None,
    ) -> None:
        self.learning_repo = learning_repo or safety_learning_repository
        self.incident_repo = incident_repo or safety_incident_repository

    def evaluate_action_effectiveness(
        self,
        action_id: str,
        observation_days: int = 30,
    ) -> CorrectiveActionEffectivenessRecord:
        """Evaluate if an action is correlated with reduced recurrence of parent incident type."""
        action = self.incident_repo.get_action(action_id)
        if not action:
            raise SafetyLearningNotFoundException(f"Corrective action '{action_id}' not found.")

        incident = self.incident_repo.get_incident(action.incident_id)
        if not incident:
            raise SafetyLearningNotFoundException(f"Parent incident '{action.incident_id}' not found.")

        now = datetime.now(timezone.utc)
        start_time = action.completed_at or action.created_at
        end_time = start_time + timedelta(days=observation_days)

        # Check if still in observation window
        if now < end_time:
            rec = CorrectiveActionEffectivenessRecord(
                action_id=action.id,
                incident_id=incident.id,
                state=EffectivenessState.PENDING_OBSERVATION,
                observation_start=start_time,
                observation_end=end_time,
                pre_implementation_count=1,
                post_implementation_count=0,
                summary="Action completed recently; observation window still in progress.",
                limitations=["Observation window incomplete."],
            )
            return self.learning_repo.save_effectiveness(rec)

        # Query subsequent incidents of same type
        all_incidents = self.incident_repo.list_incidents(incident_type=incident.incident_type)
        subsequent = [
            i for i in all_incidents
            if i.id != incident.id and start_time <= i.occurred_at <= end_time
        ]

        if not subsequent:
            state = EffectivenessState.NO_RECURRENCE_OBSERVED
            summary = (
                f"No recurrence of incident type '{incident.incident_type.value}' observed "
                f"during the {observation_days}-day observation window."
            )
        elif len(subsequent) >= 2:
            state = EffectivenessState.RECURRENCE_OBSERVED
            summary = f"Recurrence observed: {len(subsequent)} subsequent incidents occurred during observation window."
        else:
            state = EffectivenessState.PARTIAL_IMPROVEMENT
            summary = "Single recurrence observed; potential partial risk mitigation."

        record = CorrectiveActionEffectivenessRecord(
            action_id=action.id,
            incident_id=incident.id,
            state=state,
            observation_start=start_time,
            observation_end=end_time,
            pre_implementation_count=1,
            post_implementation_count=len(subsequent),
            subsequent_incident_ids=[i.id for i in subsequent],
            summary=summary,
            limitations=[
                "Correlation does not prove causation.",
                "Absence of recurrence does not guarantee future risk elimination.",
            ],
        )
        return self.learning_repo.save_effectiveness(record)

    def get_effectiveness(self, action_id: str) -> Optional[CorrectiveActionEffectivenessRecord]:
        """Retrieve existing effectiveness evaluation."""
        return self.learning_repo.get_effectiveness(action_id)


# Global singleton
safety_effectiveness_service = SafetyEffectivenessService()

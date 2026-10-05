"""HealthSetu Phase 42 - Patient Action Workflow Service.

Coordinates event dispatch, clinical review tasks (Phase 36),
workflow events (Phase 37), and notifications (Phase 29).

CRITICAL INTEGRATION BOUNDARIES:
- Workflow decides what operational action follows.
- Submission does NOT automatically create a diagnosis or emergency dispatch.
- Review tasks are operational queues for authorized clinical staff.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import settings
from app.schemas.patient_action import PatientActionRecord

logger = logging.getLogger(__name__)


class PatientActionWorkflowService:
    """Dispatches integration events to other HealthSetu domains."""

    def __init__(
        self,
        notification_service: Optional[Any] = None,
        task_service: Optional[Any] = None,
        workflow_service: Optional[Any] = None,
    ) -> None:
        self.notification_service = notification_service
        self.task_service = task_service
        self.workflow_service = workflow_service

    async def on_action_created(self, action: PatientActionRecord) -> None:
        """Trigger notification and workflow initialization upon action creation."""
        logger.info(
            "Patient action created event emitted",
            extra={"action_id": action.id, "patient_id": action.patient_id, "type": action.action_type.value},
        )
        if self.notification_service and getattr(settings, "NOTIFICATIONS_ENABLED", True):
            try:
                # Operational notification to patient
                if hasattr(self.notification_service, "send_notification"):
                    await self.notification_service.send_notification(
                        recipient_id=action.patient_id,
                        title="New Action Required",
                        body=f"You have a pending task: {action.title}",
                        channel="IN_APP",
                        metadata={"action_id": action.id},
                    )
            except Exception as e:
                logger.warning(f"Failed to dispatch action creation notification: {e}")

    async def on_action_submitted(self, action: PatientActionRecord, submission_id: str) -> None:
        """Emit submission events and route to clinical review queue if required."""
        logger.info(
            "Patient action submitted event emitted",
            extra={"action_id": action.id, "patient_id": action.patient_id, "submission_id": submission_id},
        )
        # If action requires clinical or operational review, create task in Phase 36
        if self.task_service and getattr(settings, "TASKS_ENABLED", True):
            try:
                if hasattr(self.task_service, "create_task"):
                    await self.task_service.create_task(
                        title=f"Review Submission: {action.title}",
                        description=f"Patient {action.patient_id} submitted response for action {action.id}.",
                        task_type="PATIENT_ACTION_REVIEW",
                        patient_id=action.patient_id,
                        organization_id=action.organization_id,
                        facility_id=action.facility_id,
                        metadata={"action_id": action.id, "submission_id": submission_id},
                    )
            except Exception as e:
                logger.warning(f"Failed to dispatch clinical review task: {e}")

    async def on_action_reminder(self, action: PatientActionRecord) -> None:
        """Emit reminder notification for pending action."""
        logger.info(
            "Patient action reminder dispatched",
            extra={"action_id": action.id, "patient_id": action.patient_id, "reminder_count": action.reminder_count},
        )
        if self.notification_service and getattr(settings, "NOTIFICATIONS_ENABLED", True):
            try:
                if hasattr(self.notification_service, "send_notification"):
                    await self.notification_service.send_notification(
                        recipient_id=action.patient_id,
                        title="Reminder: Incomplete Action",
                        body=f"Please complete: {action.title}",
                        channel="IN_APP",
                        metadata={"action_id": action.id},
                    )
            except Exception as e:
                logger.warning(f"Failed to dispatch action reminder: {e}")

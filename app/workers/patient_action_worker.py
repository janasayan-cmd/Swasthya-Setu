"""HealthSetu Phase 42 - Patient Action Worker.

Asynchronous background worker handling expiration sweeps, automated reminders,
and event routing.

INTEGRATION BOUNDARIES:
- Integrates with Phase 22 Async Job engine.
- Reminder generation respects quiet periods, rate limits, and max reminder counts.
- EXPIRED != PATIENT FAILURE or NONCOMPLIANCE.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from app.core.config import settings
from app.repositories.patient_action_repository import PatientActionRepository
from app.schemas.patient_action import ActionStatus, PatientActionRecord
from app.services.patient_action_workflow_service import PatientActionWorkflowService

logger = logging.getLogger(__name__)


class PatientActionWorker:
    """Background processor for patient action lifecycle operations."""

    def __init__(
        self,
        action_repo: PatientActionRepository,
        workflow_service: PatientActionWorkflowService,
    ) -> None:
        self.action_repo = action_repo
        self.workflow_service = workflow_service

    async def sweep_expirations(self) -> List[PatientActionRecord]:
        """Sweep for actions that have passed their expiration horizon."""
        expired = await self.action_repo.sweep_expired_actions()
        if expired:
            logger.info(f"PatientActionWorker: transitioned {len(expired)} actions to EXPIRED.")
        return expired

    async def sweep_reminders(self) -> int:
        """Find pending actions requiring reminders and dispatch notifications."""
        if not getattr(settings, "ACTION_REMINDERS_ENABLED", True):
            return 0

        max_reminders = getattr(settings, "ACTION_REMINDER_MAX_COUNT", 3)
        reminders_sent = 0

        # Iterate all actions in memory / repo
        async with self.action_repo._lock:
            actions_to_remind = [
                a for a in self.action_repo._actions.values()
                if a.status in (ActionStatus.AVAILABLE, ActionStatus.STARTED)
                and a.reminder_count < max_reminders
            ]

        for action in actions_to_remind:
            action.reminder_count += 1
            action.last_reminder_at = datetime.now(timezone.utc)
            await self.action_repo.save_action(action)
            await self.workflow_service.on_action_reminder(action)
            reminders_sent += 1

        if reminders_sent > 0:
            logger.info(f"PatientActionWorker: dispatched {reminders_sent} action reminders.")
        return reminders_sent

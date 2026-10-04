"""Task Escalation and Overdue Evaluation Service (Phase 36).

Enforces:
- Overdue detection based on authoritative deadlines
- Multi-tier escalation with stop conditions (completed, verified, cancelled)
- Alert generation reusing Phase 35 AlertService
- Multi-channel notification delivery reusing Phase 29 NotificationService
- Clinical Safety: Overdue task != Automatic emergency dispatch
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from app.repositories.task_repository import TaskRepository
from app.schemas.alert import AlertCreate
from app.schemas.notification import NotificationCreate, NotificationType
from app.schemas.task import TaskFilter, TaskRecord, TaskStatus
from app.schemas.task_history import TaskHistoryAction
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


class TaskEscalationService:
    """Evaluates task deadlines, triggers escalation tiers, and creates alerts/notifications."""

    def __init__(
        self,
        task_repo: TaskRepository,
        alert_service: Optional[AlertService] = None,
        notification_service: Optional[NotificationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.task_repo = task_repo
        self.alert_service = alert_service
        self.notification_service = notification_service
        self.audit_service = audit_service

    async def evaluate_overdue_tasks(self) -> List[TaskRecord]:
        """Scan for active tasks whose due_at has passed and advance escalation."""
        now = datetime.now(timezone.utc)
        terminal = {
            TaskStatus.COMPLETED,
            TaskStatus.VERIFIED,
            TaskStatus.CANCELLED,
            TaskStatus.REJECTED,
            TaskStatus.EXPIRED,
            TaskStatus.FAILED,
        }

        filters = TaskFilter(overdue_only=True, page=1, page_size=100)
        overdue_tasks, _ = self.task_repo.list_tasks(filters)
        escalated: List[TaskRecord] = []

        for task in overdue_tasks:
            if task.status in terminal:
                continue

            res = await self.escalate_task(task.id, reason="Task deadline expired (overdue).")
            if res:
                escalated.append(res)

        return escalated

    async def escalate_task(
        self,
        task_id: str,
        reason: str = "Escalation requested",
        force: bool = False,
    ) -> Optional[TaskRecord]:
        """Escalate an uncompleted task to next tier."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            return None

        terminal = {
            TaskStatus.COMPLETED,
            TaskStatus.VERIFIED,
            TaskStatus.CANCELLED,
            TaskStatus.REJECTED,
            TaskStatus.EXPIRED,
            TaskStatus.FAILED,
        }
        if task.status in terminal:
            # Escalation stops immediately if already completed, verified, or cancelled
            return task

        new_level = task.escalation_level + 1
        updated_task = task.model_copy(
            update={
                "escalation_level": new_level,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        saved = self.task_repo.save(updated_task)

        # Log history
        self.task_repo.add_history(
            task_id=task.id,
            action=TaskHistoryAction.TASK_ESCALATED,
            from_status=task.status.value,
            to_status=task.status.value,
            actor_id="system_escalation_worker",
            actor_role="SYSTEM",
            reason=f"{reason} (Escalation level {new_level})",
            metadata={"escalation_level": new_level},
        )

        # Emit alert if high or urgent priority, or escalated beyond tier 1
        if self.alert_service and (task.priority.value in {"HIGH", "URGENT"} or new_level >= 2):
            try:
                alert_payload = AlertCreate(
                    source_system="task_service",
                    source_event_type="TASK_OVERDUE",
                    source_event_id=f"EVT-TSK-ESC-{task.id}-{new_level}",
                    source_resource_type="task",
                    source_resource_id=task.id,
                    patient_id=task.patient_id,
                    responsible_clinician_id=task.assignee_id,
                    facility_id=task.facility_id,
                    organization_id=task.organization_id,
                    event_payload={
                        "task_id": task.id,
                        "task_title": task.title,
                        "priority": task.priority.value,
                        "escalation_level": new_level,
                        "due_at": task.due_at.isoformat() if task.due_at else None,
                    },
                )
                await self.alert_service.create_alert_from_event(alert_payload)
            except Exception:
                # Alert creation error should not block task escalation state
                pass

        # Send notification to assignee or team
        if self.notification_service and task.assignee_id:
            try:
                notif = NotificationCreate(
                    recipient_id=task.assignee_id,
                    recipient_type="CLINICIAN",
                    notification_type=NotificationType.TASK_OVERDUE,
                    priority=task.priority.value,
                    title=f"Overdue Task: {task.title}",
                    body=f"Task {task.id} ({task.priority.value}) is overdue at escalation level {new_level}.",
                    variables={
                        "task_title": task.title,
                        "task_id": task.id,
                        "priority": task.priority.value,
                    },
                    facility_id=task.facility_id,
                    organization_id=task.organization_id,
                )
                await self.notification_service.send_notification(notif)
            except Exception:
                # Notification delivery error must not invalidate task state
                pass

        return saved

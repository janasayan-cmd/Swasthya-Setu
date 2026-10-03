"""Escalation Engine and Workflow Orchestration for Clinical Alerts (Phase 35).

CORE SAFETY PRINCIPLES:
- ESCALATION != DIAGNOSIS
- ESCALATION != EMERGENCY DISPATCH
- Never escalate an already acknowledged, resolved, or dismissed alert.
- Escalation tiers follow authorized organizational hierarchy (Clinician -> Care Team -> Facility -> Organization).
- External emergency services are NEVER automatically called.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.exceptions import AlertEscalationNotAllowedException, AlertNotFoundException
from app.integrations.alerts.base import AlertProvider
from app.repositories.alert_escalation_repository import AlertEscalationRepository
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertRecipient, AlertRecord, AlertStatus
from app.schemas.alert_escalation import EscalationRecord, EscalationStatus
from app.schemas.alert_history import AlertHistoryEntry
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.notification import NotificationCategory, NotificationCreate, NotificationPriority, NotificationType
from app.services.alert_recipient_service import AlertRecipientService
from app.services.alert_validation_service import AlertValidationService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class AlertEscalationService:
    """Manages evaluation of escalation deadlines and advancement through operational tiers."""

    def __init__(
        self,
        alert_repo: AlertRepository,
        escalation_repo: AlertEscalationRepository,
        recipient_service: AlertRecipientService,
        notification_service: NotificationService,
        audit_service: AuditService,
        alert_provider: Optional[AlertProvider] = None,
    ) -> None:
        self.alert_repo = alert_repo
        self.escalation_repo = escalation_repo
        self.recipient_service = recipient_service
        self.notification_service = notification_service
        self.audit_service = audit_service
        self.alert_provider = alert_provider

    async def check_and_escalate_alert(self, alert_id: str, force: bool = False) -> Optional[EscalationRecord]:
        """Check alert state and escalate to next tier if acknowledgement is overdue.
        
        Idempotent: exits safely if alert was already acknowledged, resolved, or dismissed.
        """
        alert = self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(f"Alert {alert_id} not found for escalation.", alert_id=alert_id)

        # 1. Critical safety gate: Stop if already acknowledged or resolved!
        if alert.status in {AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED, AlertStatus.DISMISSED, AlertStatus.EXPIRED}:
            logger.info(
                "Alert %s is in state '%s'. Escalation safely halted.",
                alert_id,
                alert.status.value,
            )
            # Record stopped escalation attempt for observability
            stop_record = EscalationRecord(
                id="",
                alert_id=alert_id,
                from_level=alert.escalation_level,
                to_level=alert.escalation_level,
                escalated_to_recipient_id="N/A",
                escalated_to_role="N/A",
                status=EscalationStatus.STOPPED,
                stop_reason=f"ALREADY_{alert.status.value}",
            )
            return self.escalation_repo.save(stop_record)

        # 2. Verify escalation eligibility
        if not alert.escalation_enabled:
            logger.info("Alert %s does not have escalation enabled. Skipping.", alert_id)
            return None

        # 3. Check deadline unless force is specified
        now = datetime.now(timezone.utc)
        if not force and alert.escalation_deadline and now < alert.escalation_deadline:
            logger.debug("Alert %s escalation deadline %s not yet reached.", alert_id, alert.escalation_deadline)
            return None

        # 4. Check maximum escalation level
        if alert.escalation_level >= 3:
            logger.warning("Alert %s has reached maximum tier (Level 3). No further escalation possible.", alert_id)
            return None

        # 5. Advance escalation tier
        from_level = alert.escalation_level
        to_level = from_level + 1

        recip_id, recip_type, role_desc = self.recipient_service.resolve_escalation_recipient(
            target_level=to_level,
            facility_id=alert.facility_id,
            organization_id=alert.organization_id,
        )

        # Add new escalation recipient to the alert record
        new_recipient = AlertRecipient(
            recipient_id=recip_id,
            recipient_type=recip_type,
            channel="IN_APP",
        )
        updated_recipients = list(alert.recipients)
        updated_recipients.append(new_recipient)

        # Update alert state
        updated_alert = alert.model_copy(
            update={
                "escalation_level": to_level,
                "status": AlertStatus.ESCALATED,
                "escalated_at": now,
                "recipients": updated_recipients,
                "updated_at": now,
            }
        )
        self.alert_repo.save(updated_alert)

        # Record history
        self.alert_repo.add_history(
            AlertHistoryEntry(
                id="",
                alert_id=alert.id,
                from_status=alert.status,
                to_status=AlertStatus.ESCALATED,
                actor_id="system_escalation_engine",
                action="ALERT_ESCALATED",
                note=f"Escalated from Level {from_level} to Level {to_level} ({role_desc}: {recip_id}).",
                timestamp=now,
            )
        )

        # 6. Save escalation audit record
        record = EscalationRecord(
            id="",
            alert_id=alert.id,
            from_level=from_level,
            to_level=to_level,
            escalated_to_recipient_id=recip_id,
            escalated_to_role=role_desc,
            status=EscalationStatus.COMPLETED,
            metadata={"escalated_at": now.isoformat()},
        )
        saved_record = self.escalation_repo.save(record)

        # 7. Audit log
        await self.audit_service.log_event(
            AuditEventRecord(
                event_type=AuditEventType.ALERT_ESCALATED,
                actor_id="system_escalation_engine",
                action="alert:escalate",
                resource_type="alert",
                resource_id=alert.id,
                patient_id=alert.patient_id,
                outcome="ALLOW",
                metadata={
                    "from_level": from_level,
                    "to_level": to_level,
                    "escalated_to": recip_id,
                },
            )
        )

        # 8. Notify escalation recipient via Phase 29
        try:
            await self.notification_service.create_notification(
                NotificationCreate(
                    recipient_id=recip_id,
                    recipient_role=recip_type.value,
                    notification_type=NotificationType.CLINICAL_ALERT_ESCALATED,
                    category=NotificationCategory.ALERT,
                    priority=NotificationPriority.URGENT,
                    patient_id=alert.patient_id,
                    variables={
                        "alert_title": alert.title,
                        "severity": alert.severity.value,
                        "alert_id": alert.id,
                        "escalation_level": str(to_level),
                    },
                    metadata={"alert_id": alert.id, "escalation_level": to_level},
                )
            )
        except Exception as e:
            logger.error("Failed to dispatch escalation notification for alert %s: %s", alert.id, e)

        # 9. Provider callback if configured
        if self.alert_provider:
            try:
                await self.alert_provider.escalate_alert(updated_alert, recip_id, to_level)
            except Exception as e:
                logger.error("External alert provider escalation call failed for %s: %s", alert.id, e)

        return saved_record

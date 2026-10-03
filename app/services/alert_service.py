"""Core Clinical Alerts and Safety Notifications Orchestration Service (Phase 35).

CORE SAFETY PRINCIPLES:
- ALERT != DIAGNOSIS
- ALERT != TRIAGE DECISION
- ALERT != TREATMENT DECISION
- ALERT != PRESCRIPTION
- ALERT != MEDICATION CHANGE
- ALERT != CLINICAL AUTHORITY
- CRITICAL RESULT != AUTOMATIC TREATMENT
- UNKNOWN STATUS != RESOLVED
- ALERT CREATED != ALERT DELIVERED != ALERT READ != ALERT ACKNOWLEDGED != CLINICAL ACTION COMPLETED
- ESCALATION != EMERGENCY DISPATCH
- External provider failure or timeout NEVER equals RESOLVED or SAFE.
- Alerts are deduplicated idempotently by source event ID to prevent alert fatigue and alert storms.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.exceptions import (
    AlertAccessDeniedException,
    AlertNotFoundException,
    AlertOperationNotAllowedException,
    AlertRecipientUnauthorizedException,
)
from app.integrations.alerts.base import AlertProvider
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertCategory,
    AlertCreate,
    AlertDismissRequest,
    AlertFilter,
    AlertListResponse,
    AlertProvenance,
    AlertRecord,
    AlertResolveRequest,
    AlertSeverity,
    AlertStatus,
)
from app.schemas.alert_history import AlertHistoryEntry
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.notification import NotificationCategory, NotificationCreate, NotificationPriority, NotificationType
from app.schemas.user import AuthenticatedUserContext
from app.services.alert_policy_service import AlertPolicyService
from app.services.alert_recipient_service import AlertRecipientService
from app.services.alert_validation_service import AlertValidationService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class AlertService:
    """Orchestrates alert evaluation, idempotent persistence, acknowledgement, and resolution."""

    def __init__(
        self,
        alert_repo: AlertRepository,
        policy_service: AlertPolicyService,
        recipient_service: AlertRecipientService,
        validation_service: AlertValidationService,
        notification_service: NotificationService,
        audit_service: AuditService,
        alert_provider: Optional[AlertProvider] = None,
    ) -> None:
        self.alert_repo = alert_repo
        self.policy_service = policy_service
        self.recipient_service = recipient_service
        self.validation_service = validation_service
        self.notification_service = notification_service
        self.audit_service = audit_service
        self.alert_provider = alert_provider

    async def create_alert_from_event(self, event_data: AlertCreate) -> Optional[AlertRecord]:
        """Process an authoritative domain event and create an alert idempotently.
        
        If an alert for this source event already exists, returns the existing record.
        """
        # 1. Idempotency Check (Section 6 & 32): Prevent alert storms and duplicate alerts
        existing = self.alert_repo.get_by_source_event(
            source_event_type=event_data.source_event_type,
            source_event_id=event_data.source_event_id,
        )
        if existing:
            logger.info(
                "Idempotency: Reusing existing alert %s for source event %s:%s",
                existing.id,
                event_data.source_event_type,
                event_data.source_event_id,
            )
            return existing

        # 2. Evaluate against configured, versioned policies (Section 13 & 14)
        policy_eval = self.policy_service.evaluate_event(
            event_type=event_data.source_event_type,
            payload=event_data.event_payload,
            override_severity=event_data.override_severity,
        )

        if not policy_eval.requires_alert:
            logger.info(
                "Policy evaluation suppressed alert for event %s:%s. Reason: %s",
                event_data.source_event_type,
                event_data.source_event_id,
                policy_eval.suppression_reason,
            )
            await self.audit_service.log_event(
                AuditEventRecord(
                    event_type=AuditEventType.ALERT_SUPPRESSED,
                    actor_id=event_data.source_system,
                    action="alert:evaluate",
                    resource_type=event_data.source_resource_type,
                    resource_id=event_data.source_resource_id,
                    patient_id=event_data.patient_id,
                    outcome="ALLOW",
                    metadata={
                        "source_event_type": event_data.source_event_type,
                        "suppression_reason": policy_eval.suppression_reason,
                    },
                )
            )
            return None

        # 3. Resolve authorized recipients (Section 8)
        recipients = self.recipient_service.resolve_recipients_for_alert(
            recipient_class=policy_eval.recipient_class or "RESPONSIBLE_CLINICIAN",
            patient_id=event_data.patient_id,
            responsible_clinician_id=event_data.responsible_clinician_id,
            facility_id=event_data.facility_id,
            organization_id=event_data.organization_id,
        )

        # 4. Compute escalation deadline if acknowledgement is required
        now = datetime.now(timezone.utc)
        deadline = None
        if policy_eval.requires_acknowledgement and policy_eval.escalation_enabled:
            timeout_mins = policy_eval.escalation_timeout_minutes or 15
            deadline = now + timedelta(minutes=timeout_mins)

        # 5. Construct immutable provenance (Section 7)
        provenance = AlertProvenance(
            source_system=event_data.source_system,
            source_event_type=event_data.source_event_type,
            source_event_id=event_data.source_event_id,
            source_resource_type=event_data.source_resource_type,
            source_resource_id=event_data.source_resource_id,
            patient_id=event_data.patient_id,
            organization_id=event_data.organization_id,
            facility_id=event_data.facility_id,
            policy_id=policy_eval.policy_id or "UNKNOWN_POLICY",
            policy_version=policy_eval.policy_version or 1,
            severity_source="APPROVED_POLICY",
            rule_identifier=policy_eval.evaluation_metadata.get("condition"),
            created_at=now,
        )

        alert_record = AlertRecord(
            id="",
            title=policy_eval.title or "Clinical Alert",
            summary=policy_eval.summary,
            category=policy_eval.category or AlertCategory.CLINICAL_ALERT,
            severity=policy_eval.severity or AlertSeverity.MEDIUM,
            status=AlertStatus.CREATED,
            patient_id=event_data.patient_id,
            organization_id=event_data.organization_id,
            facility_id=event_data.facility_id,
            provenance=provenance,
            recipients=recipients,
            requires_acknowledgement=policy_eval.requires_acknowledgement,
            acknowledgement_timeout_minutes=policy_eval.escalation_timeout_minutes,
            escalation_enabled=policy_eval.escalation_enabled,
            escalation_level=0,
            escalation_deadline=deadline,
            metadata={
                "event_payload_keys": list(event_data.event_payload.keys()),
                "policy_name": policy_eval.evaluation_metadata.get("policy_name"),
            },
            created_at=now,
            updated_at=now,
        )

        saved = self.alert_repo.save(alert_record)

        # Record history transition
        self.alert_repo.add_history(
            AlertHistoryEntry(
                id="",
                alert_id=saved.id,
                from_status=AlertStatus.CREATED,
                to_status=AlertStatus.CREATED,
                actor_id=event_data.source_system,
                action="ALERT_CREATED",
                note=f"Created via policy {policy_eval.policy_id} (v{policy_eval.policy_version})",
                timestamp=now,
            )
        )

        # Audit event
        await self.audit_service.log_event(
            AuditEventRecord(
                event_type=AuditEventType.ALERT_CREATED,
                actor_id=event_data.source_system,
                action="alert:create",
                resource_type="alert",
                resource_id=saved.id,
                patient_id=saved.patient_id,
                outcome="ALLOW",
                metadata={
                    "category": saved.category.value,
                    "severity": saved.severity.value,
                    "source_event_type": event_data.source_event_type,
                    "policy_id": policy_eval.policy_id,
                },
            )
        )

        # 6. Trigger notification dispatch via Phase 29 (Section 21)
        for recipient in saved.recipients:
            try:
                priority = NotificationPriority.URGENT if saved.severity in {AlertSeverity.CRITICAL, AlertSeverity.HIGH} else NotificationPriority.STANDARD
                await self.notification_service.create_notification(
                    NotificationCreate(
                        recipient_id=recipient.recipient_id,
                        recipient_role=recipient.recipient_type.value,
                        notification_type=NotificationType.CLINICAL_ALERT_DISPATCHED,
                        category=NotificationCategory.ALERT,
                        priority=priority,
                        patient_id=saved.patient_id,
                        variables={
                            "alert_title": saved.title,
                            "severity": saved.severity.value,
                            "alert_id": saved.id,
                            "source_event_type": saved.provenance.source_event_type,
                        },
                        metadata={"alert_id": saved.id, "severity": saved.severity.value},
                    )
                )
            except Exception as e:
                logger.error("Failed to enqueue notification for alert %s to %s: %s", saved.id, recipient.recipient_id, e)

        # 7. Notify provider adapter if configured (Section 41)
        if self.alert_provider:
            try:
                await self.alert_provider.create_alert(saved)
            except Exception as e:
                logger.error("Alert provider create_alert failed for %s: %s", saved.id, e)

        return saved

    async def get_alert(self, alert_id: str, current_user: AuthenticatedUserContext) -> AlertRecord:
        """Fetch alert by ID with strict authorization enforcement."""
        alert = self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(f"Alert {alert_id} not found.", alert_id=alert_id)

        self._check_access(alert, current_user)

        # Patient-facing view filtering (Section 9)
        if current_user.role == "PATIENT":
            safe_title, safe_summary = self.recipient_service.sanitize_for_patient(alert.title, alert.summary)
            alert = alert.model_copy(update={"title": safe_title, "summary": safe_summary, "metadata": {}})

        await self.audit_service.log_event(
            AuditEventRecord(
                event_type=AuditEventType.ALERT_VIEWED,
                actor_id=current_user.user_id,
                action="alert:view",
                resource_type="alert",
                resource_id=alert.id,
                patient_id=alert.patient_id,
                outcome="ALLOW",
            )
        )

        return alert

    async def list_alerts(
        self,
        filters: AlertFilter,
        current_user: AuthenticatedUserContext,
    ) -> AlertListResponse:
        """List alerts according to caller's clinical relationship and tenant scope."""
        allowed_patient_ids: Optional[Set[str]] = None
        recipient_user_id: Optional[str] = None
        org_id: Optional[str] = None
        facility_id: Optional[str] = None

        if current_user.role == "PATIENT":
            # Patient can only view their own alerts
            allowed_patient_ids = {current_user.patient_id or current_user.user_id}

        elif current_user.role in {"DOCTOR", "CLINICIAN", "NURSE"}:
            # Filter to clinician's inbox or assigned patients
            recipient_user_id = current_user.user_id
            facility_id = current_user.facility_id

        elif current_user.role in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            org_id = current_user.organization_id

        else:
            recipient_user_id = current_user.user_id

        items, total = self.alert_repo.list_alerts(
            filters=filters,
            allowed_patient_ids=allowed_patient_ids,
            recipient_user_id=recipient_user_id,
            organization_id=org_id,
            facility_id=facility_id,
        )

        # If patient, sanitize each item
        if current_user.role == "PATIENT":
            sanitized_items = []
            for item in items:
                st, ss = self.recipient_service.sanitize_for_patient(item.title, item.summary)
                sanitized_items.append(item.model_copy(update={"title": st, "summary": ss, "metadata": {}}))
            items = sanitized_items

        return AlertListResponse(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            has_more=(filters.page * filters.page_size) < total,
        )

    async def acknowledge_alert(
        self,
        alert_id: str,
        request: AlertAcknowledgeRequest,
        current_user: AuthenticatedUserContext,
    ) -> AlertRecord:
        """Explicitly acknowledge an alert.
        
        Halts pending escalation and records timestamp and actor.
        """
        alert = self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(f"Alert {alert_id} not found.", alert_id=alert_id)

        self._check_access(alert, current_user, require_manage=True)
        self.validation_service.validate_acknowledgement(alert)

        now = datetime.now(timezone.utc)
        from_status = alert.status
        updated = alert.model_copy(
            update={
                "status": AlertStatus.ACKNOWLEDGED,
                "acknowledged_at": now,
                "acknowledged_by": current_user.user_id,
                "acknowledgement_note": request.note,
                "updated_at": now,
            }
        )
        saved = self.alert_repo.save(updated)

        self.alert_repo.add_history(
            AlertHistoryEntry(
                id="",
                alert_id=saved.id,
                from_status=from_status,
                to_status=AlertStatus.ACKNOWLEDGED,
                actor_id=current_user.user_id,
                action="ALERT_ACKNOWLEDGED",
                note=request.note or "Explicitly acknowledged by authorized user.",
                timestamp=now,
            )
        )

        await self.audit_service.log_event(
            AuditEventRecord(
                event_type=AuditEventType.ALERT_ACKNOWLEDGED,
                actor_id=current_user.user_id,
                action="alert:acknowledge",
                resource_type="alert",
                resource_id=saved.id,
                patient_id=saved.patient_id,
                outcome="ALLOW",
                metadata={"note": request.note},
            )
        )

        if self.alert_provider:
            try:
                await self.alert_provider.acknowledge_alert(saved, current_user.user_id, request.note)
            except Exception as e:
                logger.error("External provider acknowledgement failed for %s: %s", alert_id, e)

        return saved

    async def resolve_alert(
        self,
        alert_id: str,
        request: AlertResolveRequest,
        current_user: AuthenticatedUserContext,
    ) -> AlertRecord:
        """Mark an alert resolved with mandatory resolution reason.
        
        Requires clinician or administrative authority.
        """
        alert = self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(f"Alert {alert_id} not found.", alert_id=alert_id)

        # Resolution requires clinician or admin role
        if current_user.role not in {"DOCTOR", "CLINICIAN", "ADMIN", "SYSTEM_ADMIN"}:
            raise AlertAccessDeniedException("Only authorized clinicians or administrators can resolve clinical alerts.")

        self._check_access(alert, current_user, require_manage=True)
        self.validation_service.validate_resolution(alert, request.reason)

        now = datetime.now(timezone.utc)
        from_status = alert.status
        updated = alert.model_copy(
            update={
                "status": AlertStatus.RESOLVED,
                "resolved_at": now,
                "resolved_by": current_user.user_id,
                "resolution_reason": request.reason,
                "updated_at": now,
            }
        )
        saved = self.alert_repo.save(updated)

        self.alert_repo.add_history(
            AlertHistoryEntry(
                id="",
                alert_id=saved.id,
                from_status=from_status,
                to_status=AlertStatus.RESOLVED,
                actor_id=current_user.user_id,
                action="ALERT_RESOLVED",
                note=f"Reason: {request.reason}",
                timestamp=now,
            )
        )

        await self.audit_service.log_event(
            AuditEventRecord(
                event_type=AuditEventType.ALERT_RESOLVED,
                actor_id=current_user.user_id,
                action="alert:resolve",
                resource_type="alert",
                resource_id=saved.id,
                patient_id=saved.patient_id,
                outcome="ALLOW",
                metadata={"reason": request.reason, "action_taken": request.resolution_action_taken},
            )
        )

        if self.alert_provider:
            try:
                await self.alert_provider.resolve_alert(saved, current_user.user_id, request.reason)
            except Exception as e:
                logger.error("External provider resolution failed for %s: %s", alert_id, e)

        return saved

    async def dismiss_alert(
        self,
        alert_id: str,
        request: AlertDismissRequest,
        current_user: AuthenticatedUserContext,
    ) -> AlertRecord:
        """Dismiss an alert with a mandatory reason."""
        alert = self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(f"Alert {alert_id} not found.", alert_id=alert_id)

        self._check_access(alert, current_user, require_manage=True)
        self.validation_service.validate_dismissal(alert, request.reason)

        now = datetime.now(timezone.utc)
        from_status = alert.status
        updated = alert.model_copy(
            update={
                "status": AlertStatus.DISMISSED,
                "dismissed_at": now,
                "dismissed_by": current_user.user_id,
                "dismissal_reason": request.reason,
                "updated_at": now,
            }
        )
        saved = self.alert_repo.save(updated)

        self.alert_repo.add_history(
            AlertHistoryEntry(
                id="",
                alert_id=saved.id,
                from_status=from_status,
                to_status=AlertStatus.DISMISSED,
                actor_id=current_user.user_id,
                action="ALERT_DISMISSED",
                note=f"Reason: {request.reason}",
                timestamp=now,
            )
        )

        await self.audit_service.log_event(
            AuditEventRecord(
                event_type=AuditEventType.ALERT_DISMISSED,
                actor_id=current_user.user_id,
                action="alert:dismiss",
                resource_type="alert",
                resource_id=saved.id,
                patient_id=saved.patient_id,
                outcome="ALLOW",
                metadata={"reason": request.reason},
            )
        )

        return saved

    async def get_alert_history(
        self,
        alert_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[AlertHistoryEntry]:
        """Fetch transition history for an alert."""
        alert = self.alert_repo.get_by_id(alert_id)
        if not alert:
            raise AlertNotFoundException(f"Alert {alert_id} not found.", alert_id=alert_id)

        self._check_access(alert, current_user)
        return self.alert_repo.get_history(alert_id)

    def _check_access(
        self,
        alert: AlertRecord,
        current_user: AuthenticatedUserContext,
        require_manage: bool = False,
    ) -> None:
        """Validate multi-tenant boundaries and clinical authorization."""
        # 1. System Admin can access across tenants
        if current_user.role == "SYSTEM_ADMIN":
            return

        # 2. Organization boundary
        if current_user.organization_id and alert.organization_id:
            if current_user.organization_id != alert.organization_id:
                raise AlertAccessDeniedException("Cross-tenant access to alert is denied.")

        # 3. Patient boundary
        if current_user.role == "PATIENT":
            patient_id = current_user.patient_id or current_user.user_id
            if alert.patient_id != patient_id:
                raise AlertAccessDeniedException("Patients can only access their own alerts.")
            # Patient cannot manage/resolve clinical alerts
            if require_manage and alert.category in {AlertCategory.CLINICAL_ALERT, AlertCategory.MEDICATION_SAFETY_ALERT, AlertCategory.DIAGNOSTIC_RESULT_ALERT, AlertCategory.TRIAGE_ALERT}:
                # Note: Patient can acknowledge an alert directed specifically to them
                is_recipient = any(r.recipient_id == patient_id and r.recipient_type.value == "PATIENT" for r in alert.recipients)
                if not is_recipient:
                    raise AlertAccessDeniedException("Patient cannot manage this clinical alert.")
            return

        # 4. Clinician check: must be designated recipient, or in same facility/patient scope
        if current_user.role in {"DOCTOR", "CLINICIAN", "NURSE"}:
            is_recipient = any(r.recipient_id == current_user.user_id for r in alert.recipients)
            same_facility = alert.facility_id and alert.facility_id == current_user.facility_id
            if not is_recipient and not same_facility:
                raise AlertAccessDeniedException("Clinician is not an authorized recipient for this alert.")
            return

        # 5. Administrators
        if current_user.role in {"ADMIN", "OPERATIONS_ADMIN"}:
            return

        # Fallback check: is user an explicit recipient?
        is_recipient = any(r.recipient_id == current_user.user_id for r in alert.recipients)
        if not is_recipient:
            raise AlertAccessDeniedException("You are not authorized to access this alert.")

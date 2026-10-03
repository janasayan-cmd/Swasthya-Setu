"""Diagnostic Report Service (Phase 34).

Responsibilities:
- Manage laboratory, radiology, and pathology diagnostic reports.
- Link reports with Phase 5 secure medical documents and Phase 4 patient records.
- Preserve clinician narrative impressions without converting them into autonomous diagnoses.

CRITICAL INVARIANTS:
- DIAGNOSTIC REPORT CONCLUSION TEXT != STRUCTURED DIAGNOSIS
- DOCUMENT EXTRACTION != VERIFIED RESULT
- RADIOLOGY / IMAGING IMPRESSIONS DO NOT AUTONOMOUSLY CONSTITUTE DIAGNOSES
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    DiagnosticReportNotFoundException,
)
from app.repositories.diagnostic_report_repository import DiagnosticReportRepository
from app.schemas.audit import AuditEventType, AuditRecord
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_report import (
    DiagnosticReportCreate,
    DiagnosticReportFilter,
    DiagnosticReportListResponse,
    DiagnosticReportRecord,
    DiagnosticReportStatus,
)
from app.schemas.notification import NotificationPriority, NotificationType
from app.services.audit_service import AuditService
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class DiagnosticReportService:
    """Service managing diagnostic report compilation and access."""

    def __init__(
        self,
        report_repository: Optional[DiagnosticReportRepository] = None,
        authorization_service: Optional[DiagnosticAuthorizationService] = None,
        audit_service: Optional[AuditService] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.report_repository = report_repository or DiagnosticReportRepository()
        self.authorization_service = authorization_service or DiagnosticAuthorizationService()
        self.audit_service = audit_service
        self.notification_service = notification_service

    async def create_report(
        self,
        create_payload: DiagnosticReportCreate,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> DiagnosticReportRecord:
        """Create and publish a diagnostic report."""
        report_id = f"diag-rpt-{uuid.uuid4().hex[:12]}"
        report_number = self.report_repository.generate_report_number()
        now = datetime.now(timezone.utc)

        record = DiagnosticReportRecord(
            report_id=report_id,
            report_number=report_number,
            order_id=create_payload.order_id,
            patient_id=create_payload.patient_id,
            encounter_id=create_payload.encounter_id,
            clinician_id=create_payload.clinician_id,
            organization_id=create_payload.organization_id,
            facility_id=create_payload.facility_id,
            provider_id=create_payload.provider_id,
            provider_report_id=create_payload.provider_report_id,
            status=create_payload.status,
            conclusion_text=create_payload.conclusion_text,
            document_id=create_payload.document_id,
            result_ids=create_payload.result_ids,
            reported_at=create_payload.reported_at or now,
            notes=create_payload.notes,
            metadata=create_payload.metadata,
            created_at=now,
            updated_at=now,
        )

        saved = self.report_repository.save(record)

        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_REPORT_RECEIVED,
                actor=current_user,
                resource_id=saved.report_id,
                patient_id=saved.patient_id,
                outcome="ALLOW",
            )

        if self.notification_service:
            try:
                await self.notification_service.dispatch_notification(
                    notification_type=NotificationType.DIAGNOSTIC_REPORT_AVAILABLE,
                    recipient_id=saved.patient_id,
                    variables={"report_id": saved.report_number},
                    priority=NotificationPriority.NORMAL,
                )
            except Exception as e:
                logger.warning("Failed to dispatch report notification: %s", e)

        return saved

    async def get_report(self, report_id: str, current_user: AuthenticatedUserContext) -> DiagnosticReportRecord:
        """Fetch report with BOLA/IDOR authorization."""
        report = self.report_repository.get_by_id(report_id) or self.report_repository.get_by_report_number(report_id)
        if not report:
            raise DiagnosticReportNotFoundException(f"Diagnostic report '{report_id}' not found")

        self.authorization_service.authorize_result_access(current_user, report.patient_id)

        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_REPORT_VIEWED,
                actor=current_user,
                resource_id=report.report_id,
                patient_id=report.patient_id,
                outcome="ALLOW",
            )
        return report

    async def list_reports(
        self,
        filter_params: DiagnosticReportFilter,
        current_user: AuthenticatedUserContext,
    ) -> DiagnosticReportListResponse:
        """List reports subject to access authorization."""
        user_role = (getattr(current_user, "role", None) or "").upper()
        user_id = str(getattr(current_user, "id", None) or getattr(current_user, "user_id", None) or "")

        if user_role == "PATIENT":
            user_patient_id = str(getattr(current_user, "patient_id", "") or user_id)
            filter_params = filter_params.model_copy(update={"patient_id": user_patient_id})

        return self.report_repository.filter_reports(filter_params)

    async def _audit(
        self,
        event_type: AuditEventType,
        actor: Optional[AuthenticatedUserContext],
        resource_id: str,
        patient_id: Optional[str],
        outcome: str,
    ) -> None:
        if not self.audit_service:
            return
        actor_id = str(getattr(actor, "id", None) or getattr(actor, "user_id", None) or "system")
        record = AuditRecord(
            event_type=event_type,
            actor_id=actor_id,
            patient_id=patient_id,
            action=event_type.value,
            resource_type="diagnostic_report",
            resource_id=resource_id,
            outcome=outcome,
        )
        try:
            await self.audit_service.log_event(record)
        except Exception as e:
            logger.warning("Audit logging failed for report: %s", e)

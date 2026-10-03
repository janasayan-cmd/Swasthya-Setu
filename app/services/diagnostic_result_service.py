"""Diagnostic Result Service (Phase 34).

Core orchestrator for ingesting, validating, normalizing, versioning, and retrieving
diagnostic laboratory results and analyte measurements.

CRITICAL CLINICAL SAFETY INVARIANTS:
- LAB RESULT != DIAGNOSIS
- ABNORMAL RESULT != DIAGNOSIS
- CRITICAL RESULT != AUTONOMOUS TREATMENT DECISION
- MISSING REFERENCE RANGE != NORMAL (PRESERVE SOURCE RANGE EXACTLY)
- MISSING UNIT != ASSUMED UNIT (DO NOT CONVERT UNITS SILENTLY)
- UNKNOWN RESULT != NORMAL RESULT
- CORRECTED RESULT != REPLACED HISTORY (FULL IMMUTABLE VERSION CHAIN PRESERVED)
- IMPORTED RESULT != CLINICALLY VERIFIED RESULT
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import (
    DiagnosticOrderNotFoundException,
    DiagnosticOrderValidationFailedException,
    DiagnosticResultNotFoundException,
    DiagnosticResultProcessingDisabledException,
    PatientIdentityUnresolvedException,
)
from app.repositories.diagnostic_order_repository import DiagnosticOrderRepository
from app.repositories.diagnostic_result_repository import DiagnosticResultRepository
from app.schemas.audit import AuditEventType, AuditRecord
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_order import DiagnosticOrderStatus
from app.schemas.diagnostic_result import (
    AbnormalFlag,
    DiagnosticResultFilter,
    DiagnosticResultIngest,
    DiagnosticResultItem,
    DiagnosticResultListResponse,
    DiagnosticResultRecord,
    ResultStatus,
    VerificationStatus,
)
from app.schemas.notification import NotificationPriority, NotificationType
from app.services.audit_service import AuditService
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService
from app.services.diagnostic_validation_service import DiagnosticValidationService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class DiagnosticResultService:
    """Service managing diagnostic laboratory result ingestion and retrieval."""

    def __init__(
        self,
        result_repository: Optional[DiagnosticResultRepository] = None,
        order_repository: Optional[DiagnosticOrderRepository] = None,
        validation_service: Optional[DiagnosticValidationService] = None,
        authorization_service: Optional[DiagnosticAuthorizationService] = None,
        audit_service: Optional[AuditService] = None,
        notification_service: Optional[NotificationService] = None,
        enabled: bool = True,
        critical_notifications_enabled: bool = True,
    ) -> None:
        self.result_repository = result_repository or DiagnosticResultRepository()
        self.order_repository = order_repository or DiagnosticOrderRepository()
        self.validation_service = validation_service or DiagnosticValidationService()
        self.authorization_service = authorization_service or DiagnosticAuthorizationService()
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.enabled = enabled
        self.critical_notifications_enabled = critical_notifications_enabled

    def _check_enabled(self) -> None:
        if not self.enabled:
            raise DiagnosticResultProcessingDisabledException("Diagnostic result processing is disabled")

    async def ingest_result(
        self,
        ingest_payload: DiagnosticResultIngest,
        actor: Optional[AuthenticatedUserContext] = None,
    ) -> DiagnosticResultRecord:
        """Ingest, validate, normalize, and persist diagnostic result payload."""
        self._check_enabled()

        # 1. Validate result analyte measurements
        self.validation_service.validate_result_items(ingest_payload.items)

        # 2. Resolve Order & Patient references
        order = None
        patient_id = ingest_payload.patient_id

        if ingest_payload.order_id:
            order = self.order_repository.get_by_id(ingest_payload.order_id) or self.order_repository.get_by_order_number(ingest_payload.order_id)
            if not order:
                raise DiagnosticOrderNotFoundException(f"Order '{ingest_payload.order_id}' not found for result ingestion")
            if patient_id and patient_id != order.patient_id:
                raise DiagnosticOrderValidationFailedException(
                    f"Patient ID mismatch: Result patient '{patient_id}' does not match order patient '{order.patient_id}'"
                )
            patient_id = order.patient_id
        elif ingest_payload.external_order_id:
            order = self.order_repository.get_by_provider_order_id(ingest_payload.external_order_id)
            if order:
                patient_id = order.patient_id

        if not patient_id:
            raise PatientIdentityUnresolvedException(
                "Cannot ingest diagnostic result without an identified HealthSetu patient"
            )

        # 3. Check for Versioning / Corrections (Section 26 & 56)
        existing_result = self.result_repository.get_by_provider_result_id(
            provider_id=ingest_payload.provider_id,
            provider_result_id=ingest_payload.provider_result_id,
        )

        version = 1
        supersedes_id: Optional[str] = None
        is_correction = False

        if existing_result:
            version = existing_result.version + 1
            supersedes_id = existing_result.result_id
            is_correction = True
        elif ingest_payload.status in {ResultStatus.CORRECTED, ResultStatus.AMENDED}:
            is_correction = True

        # 4. Check for Critical Flags (Section 24 & 49)
        has_critical = any(item.abnormal_flag == AbnormalFlag.CRITICAL for item in ingest_payload.items)

        result_id = f"diag-res-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Build analyte items
        items: list[DiagnosticResultItem] = []
        for it in ingest_payload.items:
            items.append(
                DiagnosticResultItem(
                    item_id=f"res-it-{uuid.uuid4().hex[:8]}",
                    result_id=result_id,
                    analyte_name=it.analyte_name,
                    analyte_code=it.analyte_code,
                    system=it.system or "LOINC",
                    numeric_value=it.numeric_value,
                    qualitative_value=it.qualitative_value,
                    unit=it.unit,
                    reference_range=it.reference_range,
                    abnormal_flag=it.abnormal_flag,
                    notes=it.notes,
                )
            )

        record = DiagnosticResultRecord(
            result_id=result_id,
            order_id=order.order_id if order else ingest_payload.order_id,
            patient_id=patient_id,
            encounter_id=order.encounter_id if order else None,
            clinician_id=order.clinician_id if order else None,
            organization_id=order.organization_id if order else None,
            facility_id=order.facility_id if order else None,
            provider_id=ingest_payload.provider_id,
            provider_result_id=ingest_payload.provider_result_id,
            status=ingest_payload.status,
            verification_status=VerificationStatus.REVIEW_REQUIRED,
            items=items,
            has_critical_flag=has_critical,
            version=version,
            is_current=True,
            supersedes_result_id=supersedes_id,
            correction_reason=ingest_payload.notes if is_correction else None,
            corrected_at=now if is_correction else None,
            collected_at=ingest_payload.collected_at,
            resulted_at=ingest_payload.resulted_at or now,
            document_id=ingest_payload.document_id,
            provenance={
                "provider_id": ingest_payload.provider_id,
                "provider_result_id": ingest_payload.provider_result_id,
                "ingested_at": now.isoformat(),
                "actor_id": str(getattr(actor, "id", None) or "provider_gateway"),
            },
            created_at=now,
            updated_at=now,
        )

        saved = self.result_repository.save(record)

        # If order exists, update status to COMPLETED if not cancelled
        if order and order.status not in {DiagnosticOrderStatus.CANCELLED, DiagnosticOrderStatus.REJECTED}:
            self.order_repository.update_status(order.order_id, DiagnosticOrderStatus.COMPLETED)

        # 5. Audit Logging
        if self.audit_service:
            event_type = AuditEventType.DIAGNOSTIC_RESULT_CORRECTED if is_correction else AuditEventType.DIAGNOSTIC_RESULT_RECEIVED
            await self._audit(
                event_type=event_type,
                actor=actor,
                resource_id=saved.result_id,
                patient_id=saved.patient_id,
                outcome="ALLOW",
            )
            if has_critical:
                await self._audit(
                    event_type=AuditEventType.CRITICAL_RESULT_REVIEW_REQUIRED,
                    actor=actor,
                    resource_id=saved.result_id,
                    patient_id=saved.patient_id,
                    outcome="ALLOW",
                    reason="CRITICAL_FLAG_DETECTED",
                )

        # 6. Notifications
        if self.notification_service:
            try:
                if has_critical and self.critical_notifications_enabled:
                    # Notify clinician/care team immediately of critical flag
                    recipient = record.clinician_id or record.patient_id
                    await self.notification_service.dispatch_notification(
                        notification_type=NotificationType.CRITICAL_RESULT_REVIEW_REQUIRED,
                        recipient_id=recipient,
                        variables={"result_id": saved.result_id},
                        priority=NotificationPriority.CRITICAL,
                    )
                elif is_correction:
                    await self.notification_service.dispatch_notification(
                        notification_type=NotificationType.DIAGNOSTIC_RESULT_CORRECTED,
                        recipient_id=saved.patient_id,
                        variables={"result_id": saved.result_id},
                    )
                else:
                    await self.notification_service.dispatch_notification(
                        notification_type=NotificationType.DIAGNOSTIC_RESULT_AVAILABLE,
                        recipient_id=saved.patient_id,
                        variables={"order_id": order.order_number if order else saved.result_id},
                    )
            except Exception as e:
                logger.warning("Failed to dispatch result notification: %s", e)

        return saved

    async def get_result(self, result_id: str, current_user: AuthenticatedUserContext) -> DiagnosticResultRecord:
        """Fetch result record with BOLA/IDOR protection."""
        self._check_enabled()
        result = self.result_repository.get_by_id(result_id)
        if not result:
            raise DiagnosticResultNotFoundException(f"Diagnostic result '{result_id}' not found")

        self.authorization_service.authorize_result_access(current_user, result.patient_id)

        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_RESULT_VIEWED,
                actor=current_user,
                resource_id=result.result_id,
                patient_id=result.patient_id,
                outcome="ALLOW",
            )
        return result

    async def get_version_history(self, result_id: str, current_user: AuthenticatedUserContext) -> List[DiagnosticResultRecord]:
        """Retrieve full audit-grade historical chain for a diagnostic result."""
        self._check_enabled()
        result = self.result_repository.get_by_id(result_id)
        if not result:
            raise DiagnosticResultNotFoundException(f"Diagnostic result '{result_id}' not found")

        self.authorization_service.authorize_result_access(current_user, result.patient_id)
        return self.result_repository.get_version_history(result_id)

    async def list_results(
        self,
        filter_params: DiagnosticResultFilter,
        current_user: AuthenticatedUserContext,
        current_only: bool = True,
    ) -> DiagnosticResultListResponse:
        """List results subject to authorization boundaries."""
        self._check_enabled()
        user_role = (getattr(current_user, "role", None) or "").upper()
        user_id = str(getattr(current_user, "id", None) or getattr(current_user, "user_id", None) or "")

        if user_role == "PATIENT":
            user_patient_id = str(getattr(current_user, "patient_id", "") or user_id)
            filter_params = filter_params.model_copy(update={"patient_id": user_patient_id})
        elif user_role in {"DOCTOR", "CLINICIAN"} and not filter_params.patient_id and not filter_params.clinician_id:
            clinician_id = getattr(current_user, "clinician_id", None) or getattr(current_user, "doctor_id", None) or user_id
            filter_params = filter_params.model_copy(update={"clinician_id": str(clinician_id)})

        return self.result_repository.filter_results(filter_params, current_only=current_only)

    async def _audit(
        self,
        event_type: AuditEventType,
        actor: Optional[AuthenticatedUserContext],
        resource_id: str,
        patient_id: Optional[str],
        outcome: str,
        reason: Optional[str] = None,
    ) -> None:
        if not self.audit_service:
            return
        actor_id = str(getattr(actor, "id", None) or getattr(actor, "user_id", None) or "provider_gateway")
        record = AuditRecord(
            event_type=event_type,
            actor_id=actor_id,
            patient_id=patient_id,
            action=event_type.value,
            resource_type="diagnostic_result",
            resource_id=resource_id,
            outcome=outcome,
            reason_code=reason,
        )
        try:
            await self.audit_service.log_event(record)
        except Exception as e:
            logger.warning("Audit logging failed: %s", e)

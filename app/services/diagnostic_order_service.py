"""Diagnostic Order Service (Phase 34).

Core orchestrator for creating, validating, submitting, tracking, and cancelling
diagnostic and laboratory orders.

CRITICAL INVARIANTS:
- DIAGNOSTIC ORDER != DIAGNOSIS
- REPEATED SUBMISSION PROTECTED BY IDEMPOTENCY
- ONLY AUTHORIZED WORKFLOWS CAN CREATE ORDERS
- COMPLETED ORDERS CANNOT BE ARBITRARILY CANCELLED
- PROVIDER FAILURE DOES NOT EQUAL SUCCESS
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    DiagnosticOrderDuplicateException,
    DiagnosticOrderingDisabledException,
    DiagnosticOrderNotFoundException,
    DiagnosticOrderSubmissionFailedException,
    DiagnosticProviderUnavailableException,
)
from app.integrations.diagnostics.base import DiagnosticProvider, ProviderState
from app.repositories.diagnostic_catalog_repository import DiagnosticCatalogRepository
from app.repositories.diagnostic_order_repository import DiagnosticOrderRepository
from app.schemas.audit import AuditEventType, AuditRecord
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_order import (
    DiagnosticOrderCancelRequest,
    DiagnosticOrderCreate,
    DiagnosticOrderFilter,
    DiagnosticOrderItem,
    DiagnosticOrderListResponse,
    DiagnosticOrderRecord,
    DiagnosticOrderStatus,
)
from app.schemas.notification import NotificationPriority, NotificationType
from app.schemas.specimen import SpecimenRecord, SpecimenStatus, SpecimenType
from app.services.audit_service import AuditService
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService
from app.services.diagnostic_validation_service import DiagnosticValidationService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class DiagnosticOrderService:
    """Service managing diagnostic order lifecycles and laboratory dispatch."""

    def __init__(
        self,
        order_repository: Optional[DiagnosticOrderRepository] = None,
        catalog_repository: Optional[DiagnosticCatalogRepository] = None,
        validation_service: Optional[DiagnosticValidationService] = None,
        authorization_service: Optional[DiagnosticAuthorizationService] = None,
        provider: Optional[DiagnosticProvider] = None,
        audit_service: Optional[AuditService] = None,
        notification_service: Optional[NotificationService] = None,
        enabled: bool = True,
    ) -> None:
        self.order_repository = order_repository or DiagnosticOrderRepository()
        self.catalog_repository = catalog_repository or DiagnosticCatalogRepository()
        self.validation_service = validation_service or DiagnosticValidationService()
        self.authorization_service = authorization_service or DiagnosticAuthorizationService()
        self.provider = provider
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.enabled = enabled

    def _check_enabled(self) -> None:
        if not self.enabled:
            raise DiagnosticOrderingDisabledException("Diagnostic ordering capability is disabled")

    async def create_order(
        self,
        order_create: DiagnosticOrderCreate,
        current_user: AuthenticatedUserContext,
    ) -> DiagnosticOrderRecord:
        """Create and validate a new diagnostic order."""
        self._check_enabled()

        # 1. Authorize workflow
        self.authorization_service.authorize_order_creation(current_user, order_create.clinician_id)

        # 2. Idempotency Check
        if order_create.idempotency_key:
            existing = self.order_repository.get_by_idempotency_key(order_create.idempotency_key)
            if existing:
                logger.info("Returning existing order for idempotency key: %s", order_create.idempotency_key)
                return existing

        # 3. Validate order inputs & safety
        self.validation_service.validate_order_creation(order_create)

        # 4. Resolve catalog tests and build sub-items
        items: list[DiagnosticOrderItem] = []
        specimens: list[SpecimenRecord] = []
        order_id = f"diag-ord-{uuid.uuid4().hex[:12]}"
        order_number = self.order_repository.generate_order_number()

        for it in order_create.items:
            test = self.catalog_repository.get_by_id(it.test_id)
            test_code = it.test_code or (test.code if test else "UNKNOWN-CODE")
            test_name = it.test_name or (test.name if test else "Diagnostic Test")
            spec_type_str = it.specimen_type or (test.specimen_type if test else None)

            spec_id = None
            if spec_type_str:
                try:
                    spec_enum = SpecimenType(spec_type_str) if isinstance(spec_type_str, str) else spec_type_str
                    spec_record = SpecimenRecord(
                        specimen_id=f"spec-{uuid.uuid4().hex[:8]}",
                        order_id=order_id,
                        patient_id=order_create.patient_id,
                        specimen_type=spec_enum,
                        status=SpecimenStatus.COLLECTION_PENDING,
                        notes=f"Required for test {test_name}",
                    )
                    specimens.append(spec_record)
                    spec_id = spec_record.specimen_id
                except ValueError:
                    pass

            item_record = DiagnosticOrderItem(
                item_id=f"item-{uuid.uuid4().hex[:8]}",
                order_id=order_id,
                test_id=it.test_id,
                test_code=test_code,
                test_name=test_name,
                specimen_type=spec_record.specimen_type if spec_id else None,
                specimen_id=spec_id,
                status=DiagnosticOrderStatus.REQUESTED,
                notes=it.notes,
            )
            items.append(item_record)

        now = datetime.now(timezone.utc)
        order_record = DiagnosticOrderRecord(
            order_id=order_id,
            order_number=order_number,
            patient_id=order_create.patient_id,
            clinician_id=order_create.clinician_id,
            organization_id=order_create.organization_id,
            facility_id=order_create.facility_id,
            encounter_id=order_create.encounter_id,
            status=DiagnosticOrderStatus.REQUESTED,
            priority=order_create.priority,
            clinical_reason=order_create.clinical_reason,
            items=items,
            specimens=specimens,
            provider_id=order_create.provider_id or (self.provider.provider_id if self.provider else None),
            notes=order_create.notes,
            idempotency_key=order_create.idempotency_key,
            ordered_at=now,
            created_at=now,
            updated_at=now,
        )

        saved = self.order_repository.save(order_record)

        # Audit
        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_ORDER_CREATED,
                actor=current_user,
                resource_id=saved.order_id,
                patient_id=saved.patient_id,
                outcome="ALLOW",
            )

        # Notification
        if self.notification_service:
            try:
                await self.notification_service.dispatch_notification(
                    notification_type=NotificationType.DIAGNOSTIC_ORDER_CREATED,
                    recipient_id=saved.patient_id,
                    variables={"order_id": saved.order_number},
                    priority=NotificationPriority.NORMAL,
                )
            except Exception as e:
                logger.warning("Notification dispatch failed for order %s: %s", saved.order_id, e)

        # Auto-submit if provider is available
        if self.provider:
            saved = await self.submit_order(saved.order_id, current_user)

        return saved

    async def submit_order(self, order_id: str, current_user: AuthenticatedUserContext) -> DiagnosticOrderRecord:
        """Submit recorded order to lab provider."""
        self._check_enabled()
        order = self.order_repository.get_by_id(order_id)
        if not order:
            raise DiagnosticOrderNotFoundException(f"Diagnostic order '{order_id}' not found")

        if not self.provider:
            logger.info("No external provider configured; order %s remains REQUESTED", order_id)
            return order

        # Transition validation
        self.validation_service.validate_order_transition(order.status, DiagnosticOrderStatus.PLACED)

        submission_res = await self.provider.place_order(order)
        if submission_res.success:
            updated = self.order_repository.update_status(
                order_id=order.order_id,
                new_status=submission_res.status,
                provider_order_id=submission_res.provider_order_id,
            )
            if self.audit_service:
                await self._audit(
                    event_type=AuditEventType.DIAGNOSTIC_ORDER_ACCEPTED,
                    actor=current_user,
                    resource_id=order.order_id,
                    patient_id=order.patient_id,
                    outcome="ALLOW",
                )
            if self.notification_service:
                try:
                    await self.notification_service.dispatch_notification(
                        notification_type=NotificationType.DIAGNOSTIC_ORDER_ACCEPTED,
                        recipient_id=order.patient_id,
                        variables={"order_id": order.order_number},
                    )
                except Exception as e:
                    logger.warning("Notification error: %s", e)
            return updated or order
        else:
            updated = self.order_repository.update_status(
                order_id=order.order_id,
                new_status=DiagnosticOrderStatus.FAILED,
            )
            if self.audit_service:
                await self._audit(
                    event_type=AuditEventType.DIAGNOSTIC_ORDER_FAILED,
                    actor=current_user,
                    resource_id=order.order_id,
                    patient_id=order.patient_id,
                    outcome="DENY",
                    reason=submission_res.error_code or "SUBMISSION_FAILED",
                )
            return updated or order

    async def get_order(self, order_id: str, current_user: AuthenticatedUserContext) -> DiagnosticOrderRecord:
        """Retrieve diagnostic order by ID or order_number with BOLA checks."""
        self._check_enabled()
        order = self.order_repository.get_by_id(order_id) or self.order_repository.get_by_order_number(order_id)
        if not order:
            raise DiagnosticOrderNotFoundException(f"Diagnostic order '{order_id}' not found")

        self.authorization_service.authorize_order_access(current_user, order.patient_id, order.clinician_id)

        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_ORDER_VIEWED,
                actor=current_user,
                resource_id=order.order_id,
                patient_id=order.patient_id,
                outcome="ALLOW",
            )
        return order

    async def cancel_order(
        self,
        order_id: str,
        cancel_request: DiagnosticOrderCancelRequest,
        current_user: User,
    ) -> DiagnosticOrderRecord:
        """Cancel an active diagnostic order."""
        self._check_enabled()
        order = self.order_repository.get_by_id(order_id) or self.order_repository.get_by_order_number(order_id)
        if not order:
            raise DiagnosticOrderNotFoundException(f"Diagnostic order '{order_id}' not found")

        self.authorization_service.authorize_order_access(current_user, order.patient_id, order.clinician_id)
        self.validation_service.validate_order_cancellation(order.status)

        # Notify provider if order was already submitted
        if self.provider and order.provider_order_id:
            await self.provider.cancel_order(order.provider_order_id, cancel_request.reason)

        updated = self.order_repository.update_status(
            order_id=order.order_id,
            new_status=DiagnosticOrderStatus.CANCELLED,
            cancellation_reason=cancel_request.reason,
        )

        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_ORDER_CANCELLED,
                actor=current_user,
                resource_id=order.order_id,
                patient_id=order.patient_id,
                outcome="ALLOW",
            )
        return updated or order

    async def update_status(
        self,
        order_id: str,
        new_status: DiagnosticOrderStatus,
        current_user: User,
        reason: Optional[str] = None,
    ) -> DiagnosticOrderRecord:
        """Update order status with lifecycle transition validation."""
        self._check_enabled()
        order = self.order_repository.get_by_id(order_id) or self.order_repository.get_by_order_number(order_id)
        if not order:
            raise DiagnosticOrderNotFoundException(f"Diagnostic order '{order_id}' not found")

        self.validation_service.validate_order_transition(order.status, new_status)
        updated = self.order_repository.update_status(
            order_id=order.order_id,
            new_status=new_status,
            cancellation_reason=reason if new_status == DiagnosticOrderStatus.CANCELLED else None,
        )
        return updated or order

    async def list_orders(
        self,
        filter_params: DiagnosticOrderFilter,
        current_user: User,
    ) -> DiagnosticOrderListResponse:
        """List orders filtered by access authorization."""
        self._check_enabled()
        user_role = (getattr(current_user, "role", None) or "").upper()
        user_id = str(getattr(current_user, "id", None) or getattr(current_user, "user_id", None) or "")

        # Enforce patient restriction
        if user_role == "PATIENT":
            user_patient_id = str(getattr(current_user, "patient_id", "") or user_id)
            filter_params = filter_params.model_copy(update={"patient_id": user_patient_id})
        elif user_role in {"DOCTOR", "CLINICIAN"} and not filter_params.patient_id and not filter_params.clinician_id:
            clinician_id = getattr(current_user, "clinician_id", None) or getattr(current_user, "doctor_id", None) or user_id
            filter_params = filter_params.model_copy(update={"clinician_id": str(clinician_id)})

        return self.order_repository.filter_orders(filter_params)

    async def record_specimen_collection(
        self,
        order_id: str,
        specimen_id: str,
        collected_at: datetime,
        current_user: User,
    ) -> DiagnosticOrderRecord:
        """Record specimen collection event."""
        self._check_enabled()
        order = self.order_repository.get_by_id(order_id)
        if not order:
            raise DiagnosticOrderNotFoundException(f"Order '{order_id}' not found")

        target_spec = None
        for s in order.specimens:
            if s.specimen_id == specimen_id:
                target_spec = s
                break

        if not target_spec:
            # Create if missing
            target_spec = SpecimenRecord(
                specimen_id=specimen_id,
                order_id=order.order_id,
                patient_id=order.patient_id,
                specimen_type=SpecimenType.BLOOD,
                status=SpecimenStatus.COLLECTED,
                collected_at=collected_at,
            )
        else:
            self.validation_service.validate_specimen_transition(target_spec.status, SpecimenStatus.COLLECTED)
            target_spec = target_spec.model_copy(
                update={"status": SpecimenStatus.COLLECTED, "collected_at": collected_at}
            )

        updated_order = self.order_repository.attach_specimen(order.order_id, target_spec)

        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.SPECIMEN_COLLECTED,
                actor=current_user,
                resource_id=specimen_id,
                patient_id=order.patient_id,
                outcome="ALLOW",
            )
        if self.notification_service:
            try:
                await self.notification_service.dispatch_notification(
                    notification_type=NotificationType.SPECIMEN_COLLECTED,
                    recipient_id=order.patient_id,
                    variables={"specimen_id": specimen_id, "order_id": order.order_number},
                )
            except Exception as e:
                logger.warning("Notification error: %s", e)

        return updated_order or order

    async def _audit(
        self,
        event_type: AuditEventType,
        actor: User,
        resource_id: str,
        patient_id: Optional[str],
        outcome: str,
        reason: Optional[str] = None,
    ) -> None:
        if not self.audit_service:
            return
        actor_id = str(getattr(actor, "id", None) or getattr(actor, "user_id", None) or "system")
        record = AuditRecord(
            event_type=event_type,
            actor_id=actor_id,
            patient_id=patient_id,
            action=event_type.value,
            resource_type="diagnostic_order",
            resource_id=resource_id,
            outcome=outcome,
            reason_code=reason,
        )
        try:
            await self.audit_service.log_event(record)
        except Exception as e:
            logger.warning("Audit logging failed: %s", e)

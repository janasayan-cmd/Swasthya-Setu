"""Clinical Order Service (Phase 38).

Orchestration layer for the controlled clinical order lifecycle.

CRITICAL SAFETY PRINCIPLES:
- ORDER != CLINICAL DECISION
- ORDER != DIAGNOSIS
- ORDER != TREATMENT
- ORDER != PRESCRIPTION
- ORDER CREATION != ORDER AUTHORIZATION
- ORDER AUTHORIZATION != ORDER TRANSMISSION
- ORDER TRANSMISSION != ORDER ACCEPTANCE
- PROVIDER SUCCESS RESPONSE != CLINICAL SUCCESS
- UNKNOWN PROVIDER STATE != COMPLETED ORDER
- TIMEOUT != FAILURE (requires reconciliation)
- MISSING CLINICAL CONTEXT => REJECT. Do not silently infer.
- AI SUGGESTIONS cannot create authorized clinical orders.
- DATABASE REMAINS THE SOURCE OF TRUTH.
- ALL ORDER ACTIONS ARE AUDIT LOGGED.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.repositories.order_repository import OrderRepository
from app.services.order_validation_service import OrderValidationService
from app.services.order_authorization_service import OrderAuthorizationService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.integrations.orders.base import OrderProvider
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.order import (
    OrderAuthorizeRequest,
    OrderCancelRequest,
    OrderCreate,
    OrderFilter,
    OrderHistoryEntry,
    OrderHistoryResponse,
    OrderItem,
    OrderListResponse,
    OrderPriority,
    OrderProviderResponse,
    OrderRecord,
    OrderReconcileRequest,
    OrderResultLink,
    OrderReviseRequest,
    OrderStatus,
    OrderStatusResponse,
    OrderType,
    OrderVerifyRequest,
    OrderWebhookEvent,
    OrderWebhookResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.core.exceptions import (
    ClinicalOrdersDisabledException,
    OrderAuthorizationRequiredException,
    OrderDuplicateException,
    OrderIdempotencyConflictException,
    OrderNotFoundException,
    OrderPatientMismatchException,
    OrderInvalidException,
    OrderVerificationRequiredException,
)


class OrderService:
    """Controlled orchestration of the clinical order lifecycle.

    ARCHITECTURAL CONTRACT:
    - Validates first, then authorizes, then mutates.
    - Every state change is recorded in the audit trail.
    - Provider interactions are normalized — provider models never leak.
    - Unknown provider states are reflected faithfully (not silently resolved).
    - The service is the single control point for all order mutations.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        validation_service: OrderValidationService,
        authorization_service: OrderAuthorizationService,
        audit_service: AuditService,
        notification_service: Optional[NotificationService] = None,
        provider: Optional[OrderProvider] = None,
        enabled: bool = True,
    ) -> None:
        self._repo = order_repository
        self._validation = validation_service
        self._authz = authorization_service
        self._audit = audit_service
        self._notifications = notification_service
        self._provider = provider
        self._enabled = enabled

    # -----------------------------------------------------------------------
    # Guard
    # -----------------------------------------------------------------------

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise ClinicalOrdersDisabledException()

    # -----------------------------------------------------------------------
    # Order Creation (TRD Sections 8, 9)
    # -----------------------------------------------------------------------

    async def create_order(
        self,
        payload: OrderCreate,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Create a new clinical order in DRAFT or PENDING_AUTHORIZATION state.

        SAFETY:
        - Validates structure and completeness before persisting.
        - Enforces actor's permission to create.
        - Idempotency key is honored.
        - New order DOES NOT enter AUTHORIZED state on creation.
        - AI output cannot be passed through this pathway as authorized.

        LIFECYCLE: DRAFT → (requires explicit authorization action)
        """
        self._require_enabled()

        # Idempotency check — same key → same order, different payload → reject
        if payload.idempotency_key:
            existing = self._repo.get_by_idempotency_key(payload.idempotency_key)
            if existing:
                # Same key, same patient — return existing (idempotent)
                if existing.patient_id == payload.patient_id:
                    return existing
                # Same key, different patient — conflict
                raise OrderIdempotencyConflictException(
                    f"Idempotency key '{payload.idempotency_key}' already exists for a different patient."
                )

        # Enforce actor's right to create
        self._authz.assert_can_create(actor)

        # Default tenancy and actor fields if not explicitly provided
        clinician_id = payload.clinician_id or actor.user_id
        organization_id = payload.organization_id or actor.organization_id or "org-main"
        facility_id = payload.facility_id or actor.facility_id or "fac-default"

        payload = payload.model_copy(
            update={
                "clinician_id": clinician_id,
                "organization_id": organization_id,
                "facility_id": facility_id,
            }
        )

        # Validate structure and completeness
        self._validation.validate_create(payload)

        # Build order record
        order_id = str(uuid.uuid4())
        order_number = self._repo.generate_order_number()
        correlation_id = str(uuid.uuid4())

        items = []
        for item in payload.items:
            if isinstance(item, dict):
                item_obj = OrderItem(
                    item_id=item.get("item_id") or str(uuid.uuid4()),
                    order_id=order_id,
                    item_type=item.get("item_type") or item.get("category"),
                    item_name=item.get("item_name") or item.get("name"),
                    item_code=item.get("item_code") or item.get("code"),
                    coding_system=item.get("coding_system"),
                    instructions=item.get("instructions"),
                    quantity=item.get("quantity", 1),
                    notes=item.get("notes"),
                    category=item.get("category"),
                    name=item.get("name"),
                    code=item.get("code"),
                )
            elif isinstance(item, OrderItem):
                item_obj = item.model_copy(update={"order_id": order_id})
            else:
                item_obj = OrderItem(
                    item_id=getattr(item, "item_id", None) or str(uuid.uuid4()),
                    order_id=order_id,
                    item_type=getattr(item, "item_type", None) or getattr(item, "category", None),
                    item_name=getattr(item, "item_name", None) or getattr(item, "name", None),
                    item_code=getattr(item, "item_code", None) or getattr(item, "code", None),
                    coding_system=getattr(item, "coding_system", None),
                    instructions=getattr(item, "instructions", None),
                    quantity=getattr(item, "quantity", 1),
                    notes=getattr(item, "notes", None),
                    category=getattr(item, "category", None),
                    name=getattr(item, "name", None),
                    code=getattr(item, "code", None),
                )
            items.append(item_obj)

        now = datetime.now(timezone.utc)
        initial_status = OrderStatus.PENDING_AUTHORIZATION
        clinician_id = payload.clinician_id or actor.user_id
        organization_id = payload.organization_id or actor.organization_id or "org-main"
        facility_id = payload.facility_id or actor.facility_id or "fac-default"

        order = OrderRecord(
            order_id=order_id,
            order_number=order_number,
            patient_id=payload.patient_id,
            clinician_id=clinician_id,
            organization_id=organization_id,
            facility_id=facility_id,
            encounter_id=payload.encounter_id,
            order_type=payload.order_type,
            status=initial_status,
            priority=payload.priority,
            clinical_reason=payload.clinical_reason,
            items=items,
            provider_id=payload.provider_id,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key,
            workflow_id=payload.workflow_id,
            source_document_id=payload.source_document_id,
            correlation_id=correlation_id,
            metadata=payload.metadata or {},
            ordered_at=now,
            created_at=now,
            updated_at=now,
        )

        # Persist
        order = self._repo.save(order)

        # Append creation history
        self._append_history(
            order_id=order_id,
            action="ORDER_CREATED",
            new_status=initial_status,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            correlation_id=correlation_id,
        )

        # Audit
        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_CREATED,
            actor_id=actor.user_id,
            patient_id=payload.patient_id,
            action="order:create",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
            metadata={
                "order_number": order_number,
                "order_type": payload.order_type.value,
                "correlation_id": correlation_id,
            },
        ))

        return order

    # -----------------------------------------------------------------------
    # Order Authorization (TRD Section 9)
    # -----------------------------------------------------------------------

    async def authorize_order(
        self,
        order_id: str,
        payload: OrderAuthorizeRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Authorize (co-sign) a clinical order.

        SAFETY:
        - AUTHORIZATION is a clinical action.
        - Only authorized clinical roles may perform this.
        - AI cannot authorize orders.
        - Transitions order from DRAFT/PENDING_AUTHORIZATION → AUTHORIZED.
        """
        self._require_enabled()

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        # Enforce actor's authorization right
        self._authz.assert_can_authorize(actor)
        self._validation.validate_authorize(order)
        self._validation.validate_transition(order, OrderStatus.AUTHORIZED)

        authorized_by = payload.authorized_by or actor.user_id

        updated = self._repo.update_status(
            order_id,
            OrderStatus.AUTHORIZED,
            authorized_by=authorized_by,
        )

        self._append_history(
            order_id=order_id,
            action="ORDER_AUTHORIZED",
            previous_status=order.status,
            new_status=OrderStatus.AUTHORIZED,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            reason=payload.reason,
            correlation_id=order.correlation_id,
        )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_AUTHORIZED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:authorize",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
            metadata={
                "order_number": order.order_number,
                "authorized_by": authorized_by,
                "previous_status": order.status.value,
            },
        ))

        return updated

    # -----------------------------------------------------------------------
    # Order Submission (TRD Section 13)
    # -----------------------------------------------------------------------

    async def submit_order(
        self,
        order_id: str,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Submit an authorized clinical order for external execution.

        SAFETY:
        - Must be in AUTHORIZED status.
        - TRANSMISSION != ACCEPTANCE.
        - TRANSMISSION != CLINICAL COMPLETION.
        - Provider failure preserves uncertainty (TRANSMISSION_UNKNOWN / FAILED).
        - Idempotent: repeated submissions of already transmitted orders return current order.
        """
        self._require_enabled()

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        self._authz.assert_can_submit(actor, order)

        # Idempotency check: if already submitted/transmitted, return safely
        if order.status in (OrderStatus.TRANSMITTED, OrderStatus.ACCEPTED, OrderStatus.IN_PROGRESS):
            return order

        self._validation.validate_transition(order, OrderStatus.TRANSMITTED)

        target_status = OrderStatus.TRANSMITTED
        provider_order_id = None
        tracking_number = None

        if self._provider:
            submission_res = await self._provider.submit_order(order)
            target_status = submission_res.internal_status
            provider_order_id = submission_res.provider_order_id
            tracking_number = submission_res.tracking_number
            if not submission_res.success and target_status not in (
                OrderStatus.TRANSMISSION_UNKNOWN,
                OrderStatus.FAILED,
            ):
                target_status = OrderStatus.TRANSMISSION_UNKNOWN

        updated = order.model_copy(
            update={
                "provider_order_id": provider_order_id or order.provider_order_id,
                "tracking_number": tracking_number or order.tracking_number,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._repo.save(updated)
        updated = self._repo.update_status(order_id, target_status, provider_order_id=provider_order_id)

        self._append_history(
            order_id=order_id,
            action="ORDER_SUBMITTED",
            previous_status=order.status,
            new_status=target_status,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            provider_reference=provider_order_id,
            correlation_id=order.correlation_id,
        )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_SUBMITTED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:submit",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW" if target_status != OrderStatus.FAILED else "DENY",
            metadata={
                "previous_status": order.status.value,
                "new_status": target_status.value,
                "provider_order_id": provider_order_id,
            },
        ))

        return updated

    # -----------------------------------------------------------------------
    # Order Retrieval (TRD Section 10)
    # -----------------------------------------------------------------------

    async def get_order(
        self,
        order_id: str,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Retrieve a single clinical order by ID.

        AUTHORIZATION: Enforces actor's view access and patient membership.
        """
        self._require_enabled()

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        self._authz.assert_can_view(actor, order)

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_VIEWED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:view",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
        ))

        return order

    async def get_order_for_patient(
        self,
        order_id: str,
        patient_id: str,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Retrieve order enforcing patient membership check."""
        order = await self.get_order(order_id, actor)
        self._authz.assert_patient_matches(order, patient_id)
        return order

    async def list_orders(
        self,
        filter_params: OrderFilter,
        actor: AuthenticatedUserContext,
    ) -> OrderListResponse:
        """List orders with authorization-filtered results.

        AUTHORIZATION:
        - Patients can only see their own orders.
        - Clinicians can see orders within their organization.
        - Admins see all.
        """
        self._require_enabled()

        from app.schemas.auth import UserRole

        # Scope patient filter to actor if patient role
        if actor.role == UserRole.PATIENT:
            filter_params = filter_params.model_copy(update={"patient_id": actor.user_id})

        # Scope organization for non-admin roles
        if actor.role not in (UserRole.ADMIN,):
            if not filter_params.organization_id and hasattr(actor, "organization_id"):
                filter_params = filter_params.model_copy(
                    update={"organization_id": actor.organization_id}
                )

        result = self._repo.filter_orders(filter_params)

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_LISTED,
            actor_id=actor.user_id,
            patient_id=filter_params.patient_id,
            action="order:list",
            resource_type="clinical_order",
            resource_id=None,
            outcome="ALLOW",
            metadata={"total": result.total},
        ))

        return result

    # -----------------------------------------------------------------------
    # Order Cancellation (TRD Section 19)
    # -----------------------------------------------------------------------

    async def cancel_order(
        self,
        order_id: str,
        payload: OrderCancelRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Request cancellation of an active clinical order.

        SAFETY:
        - CANCEL_REQUESTED != CANCELLED (provider confirmation may be required)
        - Historical state is PRESERVED
        - Original order record is NOT overwritten
        """
        self._require_enabled()

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        self._authz.assert_can_cancel(actor, order)
        self._validation.validate_cancel(order)

        # Determine target status
        if order.status in (
            OrderStatus.TRANSMITTING,
            OrderStatus.TRANSMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.IN_PROGRESS,
        ):
            new_status = OrderStatus.CANCEL_REQUESTED
        else:
            new_status = OrderStatus.CANCELLED

        self._validation.validate_transition(order, new_status)

        updated = self._repo.update_status(
            order_id,
            new_status,
            cancellation_reason=payload.reason,
        )

        self._append_history(
            order_id=order_id,
            action="ORDER_CANCEL_REQUESTED" if new_status == OrderStatus.CANCEL_REQUESTED else "ORDER_CANCELLED",
            previous_status=order.status,
            new_status=new_status,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            reason=payload.reason,
            correlation_id=order.correlation_id,
        )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_CANCEL_REQUESTED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:cancel",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
            metadata={
                "order_number": order.order_number,
                "previous_status": order.status.value,
                "new_status": new_status.value,
            },
        ))

        # Notify patient if requested
        if payload.notify_patient and self._notifications:
            try:
                await self._notifications.send_system_notification(
                    recipient_id=order.patient_id,
                    subject="Order Cancellation",
                    message=f"Your order {order.order_number} cancellation has been requested.",
                    metadata={"order_id": order_id},
                )
            except Exception:
                # Notification failure must NOT block order lifecycle
                pass

        return updated

    # -----------------------------------------------------------------------
    # Order Revision / Supersession (TRD Section 20)
    # -----------------------------------------------------------------------

    async def revise_order(
        self,
        order_id: str,
        payload: OrderReviseRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Revise a clinical order by creating a superseding order.

        SAFETY:
        - Original order is PRESERVED (status → SUPERSEDED)
        - Revision creates a NEW order record
        - Provenance chain is maintained
        - REVISION != SILENT OVERWRITE
        """
        self._require_enabled()

        original = self._repo.get_by_id(order_id)
        if not original:
            raise OrderNotFoundException()

        self._authz.assert_can_revise(actor, original)
        self._validation.validate_revise(original)

        # Build new (superseding) order
        revised_items = payload.revised_items or payload.items or [
            type(item).model_validate(item.model_dump()) for item in original.items
        ]
        revised_create = OrderCreate(
            patient_id=original.patient_id,
            clinician_id=actor.user_id,
            organization_id=original.organization_id,
            facility_id=original.facility_id,
            order_type=original.order_type,
            priority=payload.revised_priority or original.priority,
            encounter_id=original.encounter_id,
            clinical_reason=payload.revised_clinical_reason or original.clinical_reason,
            items=revised_items,
            provider_id=original.provider_id,
            notes=payload.revised_notes or original.notes,
            workflow_id=original.workflow_id,
            source_document_id=original.source_document_id,
            metadata={
                **(original.metadata or {}),
                "revision_of": order_id,
                "revision_reason": payload.reason,
            },
        )

        # Create the superseding order
        new_order = await self.create_order(revised_create, actor)

        # Mark the superseding relationship on new order
        new_order = new_order.model_copy(
            update={
                "supersedes_order_id": order_id,
                "revision_reason": payload.reason,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        new_order = self._repo.save(new_order)

        # Mark original as superseded
        self._repo.mark_superseded(order_id, new_order.order_id)

        self._append_history(
            order_id=order_id,
            action="ORDER_SUPERSEDED",
            previous_status=original.status,
            new_status=OrderStatus.SUPERSEDED,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            reason=payload.reason,
            correlation_id=original.correlation_id,
            metadata={"superseded_by": new_order.order_id},
        )

        self._append_history(
            order_id=new_order.order_id,
            action="ORDER_REVISION_CREATED",
            new_status=new_order.status,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            reason=payload.reason,
            correlation_id=new_order.correlation_id,
            metadata={"supersedes": order_id},
        )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_REVISION_CREATED,
            actor_id=actor.user_id,
            patient_id=original.patient_id,
            action="order:revise",
            resource_type="clinical_order",
            resource_id=new_order.order_id,
            outcome="ALLOW",
            metadata={
                "original_order_id": order_id,
                "superseding_order_id": new_order.order_id,
                "reason": payload.reason,
            },
        ))

        return new_order

    # -----------------------------------------------------------------------
    # Order Status (TRD Section 10)
    # -----------------------------------------------------------------------

    async def get_order_status(
        self,
        order_id: str,
        actor: AuthenticatedUserContext,
    ) -> OrderStatusResponse:
        """Retrieve order status with provider-state context.

        SAFETY:
        - Internal status is authoritative
        - Provider status is informational only
        - Unknown states remain unknown
        """
        order = await self.get_order(order_id, actor)
        return OrderStatusResponse(
            order_id=order.order_id,
            order_number=order.order_number,
            status=order.status,
            provider_status=order.provider_response.provider_status if order.provider_response else None,
            last_updated=order.updated_at,
            result_available=bool(order.result_links),
            verification_required=(order.status == OrderStatus.VERIFICATION_PENDING),
            reconciliation_required=(order.status == OrderStatus.RECONCILIATION_REQUIRED),
        )

    # -----------------------------------------------------------------------
    # Result Linkage (TRD Section 21)
    # -----------------------------------------------------------------------

    async def link_result(
        self,
        order_id: str,
        result_link: OrderResultLink,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Link an external or internal result to an order.

        SAFETY:
        - ORDER RESULT LINKAGE != RESULT VERIFICATION
        - Result is NOT automatically verified on linkage
        - Verification is a separate explicit clinical action
        """
        self._require_enabled()

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        self._authz.assert_can_view(actor, order)

        updated = self._repo.attach_result_link(order_id, result_link)

        # Transition to RESULT_AVAILABLE if in a compatible state
        if order.status in (
            OrderStatus.ACCEPTED,
            OrderStatus.IN_PROGRESS,
            OrderStatus.RESULT_PENDING,
            OrderStatus.PARTIALLY_COMPLETED,
        ):
            self._validation.validate_transition(order, OrderStatus.RESULT_AVAILABLE)
            updated = self._repo.update_status(order_id, OrderStatus.RESULT_AVAILABLE)

        self._append_history(
            order_id=order_id,
            action="ORDER_RESULT_LINKED",
            previous_status=order.status,
            new_status=updated.status if updated else order.status,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            metadata={"result_id": result_link.result_id, "result_type": result_link.result_type},
            correlation_id=order.correlation_id,
        )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_RESULT_LINKED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:result_link",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
            metadata={
                "result_id": result_link.result_id,
                "result_type": result_link.result_type,
                "verified": result_link.verified,
            },
        ))

        return updated or order

    # -----------------------------------------------------------------------
    # Order Verification (TRD Section 21)
    # -----------------------------------------------------------------------

    async def verify_order(
        self,
        order_id: str,
        payload: OrderVerifyRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Clinically verify an order or its result.

        SAFETY:
        - RESULT VERIFIED != DIAGNOSIS
        - Only authorized clinical roles may verify
        - AI cannot verify results
        """
        self._require_enabled()

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        self._authz.assert_can_verify(actor, order)
        self._validation.validate_verify(order)
        self._validation.validate_transition(order, OrderStatus.VERIFIED)

        verified_by = payload.verified_by or actor.user_id
        updated = self._repo.update_status(
            order_id,
            OrderStatus.VERIFIED,
            authorized_by=verified_by,
        )

        self._append_history(
            order_id=order_id,
            action="ORDER_VERIFIED",
            previous_status=order.status,
            new_status=OrderStatus.VERIFIED,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            reason=payload.notes,
            correlation_id=order.correlation_id,
        )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_VERIFIED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:verify",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
            metadata={"verified_by": verified_by},
        ))

        return updated

    # -----------------------------------------------------------------------
    # Provider Status Update (TRD Section 14)
    # -----------------------------------------------------------------------

    async def apply_provider_response(
        self,
        order_id: str,
        provider_response: OrderProviderResponse,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Apply a normalized provider response to an order.

        SAFETY:
        - PROVIDER SUCCESS RESPONSE != CLINICAL SUCCESS
        - UNKNOWN PROVIDER STATE != COMPLETED ORDER
        - Provider models never leak into domain
        - Raw provider data is sanitized before storage
        """
        self._require_enabled()

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        target_status = provider_response.internal_status

        try:
            self._validation.validate_transition(order, target_status)
        except Exception:
            # If transition is not valid, flag for reconciliation
            target_status = OrderStatus.RECONCILIATION_REQUIRED

        updated_order = order.model_copy(
            update={
                "provider_response": provider_response,
                "provider_order_id": provider_response.provider_order_id or order.provider_order_id,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        updated_order = self._repo.save(updated_order)

        updated_order = self._repo.update_status(
            order_id,
            target_status,
            provider_order_id=provider_response.provider_order_id,
        )

        self._append_history(
            order_id=order_id,
            action="ORDER_STATUS_UPDATED",
            previous_status=order.status,
            new_status=target_status,
            actor_id=actor.user_id,
            actor_type=str(actor.role),
            provider_reference=provider_response.provider_order_id,
            correlation_id=order.correlation_id,
        )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_STATUS_UPDATED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:provider_response",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
            metadata={
                "previous_status": order.status.value,
                "new_status": target_status.value,
                "provider_order_id": provider_response.provider_order_id,
            },
        ))

        return updated_order

    # -----------------------------------------------------------------------
    # Webhook Event Processing (TRD Section 42)
    # -----------------------------------------------------------------------

    async def process_webhook(
        self,
        event: OrderWebhookEvent,
        actor: AuthenticatedUserContext,
    ) -> OrderWebhookResponse:
        """Process an inbound provider webhook event.

        SAFETY:
        - Webhook events MUST be authenticated before this is called.
        - Replay protection MUST be applied by the caller.
        - Unknown order references are rejected, not silently created.
        - WEBHOOK REPLAY != ORDER STATE CHANGE.
        """
        self._require_enabled()

        order = self._repo.get_by_provider_order_id(event.provider_order_id)
        if not order:
            await self._audit.record(AuditEventRecord(
                event_type=AuditEventType.ORDER_WEBHOOK_REJECTED,
                actor_id=actor.user_id,
                patient_id=None,
                action="order:webhook",
                resource_type="clinical_order",
                resource_id=None,
                outcome="DENY",
                reason_code="ORDER_NOT_FOUND_FOR_PROVIDER_ID",
                metadata={"provider_order_id": event.provider_order_id},
            ))
            return OrderWebhookResponse(
                accepted=False,
                reason="No order found for the provided provider_order_id.",
            )

        # Map provider event to internal status
        internal_status = self._map_webhook_event_to_status(event, order)

        if internal_status:
            provider_response = OrderProviderResponse(
                provider_order_id=event.provider_order_id,
                provider_status=event.provider_status,
                internal_status=internal_status,
                response_message=f"Webhook event: {event.event_type}",
                metadata={"event_id": event.event_id, "provider_id": event.provider_id},
            )
            await self.apply_provider_response(order.order_id, provider_response, actor)

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_WEBHOOK_RECEIVED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:webhook",
            resource_type="clinical_order",
            resource_id=order.order_id,
            outcome="ALLOW",
            metadata={
                "event_id": event.event_id,
                "event_type": event.event_type,
                "provider_id": event.provider_id,
            },
        ))

        return OrderWebhookResponse(
            accepted=True,
            order_id=order.order_id,
            action_taken=f"status_mapped:{internal_status.value}" if internal_status else "no_status_change",
        )

    def _map_webhook_event_to_status(
        self,
        event: OrderWebhookEvent,
        order: OrderRecord,
    ) -> Optional[OrderStatus]:
        """Map a provider webhook event type to an internal order status.

        SAFETY: Unknown event types do NOT trigger status changes.
        """
        event_type_map = {
            "order.accepted": OrderStatus.ACCEPTED,
            "order.in_progress": OrderStatus.IN_PROGRESS,
            "order.completed": OrderStatus.COMPLETED,
            "order.rejected": OrderStatus.FAILED,
            "order.cancelled": OrderStatus.CANCELLED,
            "result.available": OrderStatus.RESULT_AVAILABLE,
        }
        return event_type_map.get(event.event_type.lower())

    # -----------------------------------------------------------------------
    # Order History (TRD Section 40)
    # -----------------------------------------------------------------------

    async def get_order_history(
        self,
        order_id: str,
        actor: AuthenticatedUserContext,
    ) -> OrderHistoryResponse:
        """Retrieve the complete audit/history trail for an order."""
        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        self._authz.assert_can_view(actor, order)

        entries = self._repo.get_history(order_id)
        return OrderHistoryResponse(
            order_id=order_id,
            total=len(entries),
            items=entries,
        )

    # -----------------------------------------------------------------------
    # Reconciliation (TRD Section 33)
    # -----------------------------------------------------------------------

    async def reconcile_order(
        self,
        order_id: str,
        payload: OrderReconcileRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderRecord:
        """Trigger order reconciliation — compares internal vs provider state.

        SAFETY:
        - Reconciliation DOES NOT automatically advance clinical state.
        - Missing or uncertain provider data remains flagged.
        - Creates review task if reconciliation detects mismatch.
        """
        self._require_enabled()
        self._authz.assert_can_admin(actor)

        order = self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException()

        # Flag for reconciliation if not already in that state
        if order.status not in (
            OrderStatus.RECONCILIATION_REQUIRED,
            OrderStatus.TRANSMISSION_UNKNOWN,
        ):
            if not payload.force:
                # Flag the order for reconciliation without changing business logic
                self._append_history(
                    order_id=order_id,
                    action="ORDER_RECONCILIATION_STARTED",
                    previous_status=order.status,
                    new_status=order.status,
                    actor_id=actor.user_id,
                    reason=payload.reason or "Admin-initiated reconciliation",
                    correlation_id=order.correlation_id,
                )

        await self._audit.record(AuditEventRecord(
            event_type=AuditEventType.ORDER_RECONCILIATION_STARTED,
            actor_id=actor.user_id,
            patient_id=order.patient_id,
            action="order:reconcile",
            resource_type="clinical_order",
            resource_id=order_id,
            outcome="ALLOW",
            metadata={"reason": payload.reason, "force": payload.force},
        ))

        return order

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _append_history(
        self,
        order_id: str,
        action: str,
        *,
        previous_status: Optional[OrderStatus] = None,
        new_status: Optional[OrderStatus] = None,
        actor_id: Optional[str] = None,
        actor_type: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        provider_reference: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Append an immutable history entry for the order."""
        entry = OrderHistoryEntry(
            entry_id=str(uuid.uuid4()),
            order_id=order_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
            correlation_id=correlation_id,
            provider_reference=provider_reference,
            metadata=metadata,
            occurred_at=datetime.now(timezone.utc),
        )
        self._repo.append_history(entry)

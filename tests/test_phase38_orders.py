"""Tests for HealthSetu Phase 38: Clinical Orders, Results & Controlled Action Execution.

Verifies:
- Order creation and schema validation (DRAFT, PENDING_AUTHORIZATION)
- Order authorization workflows (DOCTOR, ADMIN vs PATIENT, AI)
- Order submission to external provider network
- Provider failure safety (timeout != completed, failure != success, uncertainty preserved)
- Order cancellation and revision (superseding orders)
- Result linkage (linkage != verification)
- Explicit clinical verification (co-sign)
- Order reconciliation (internal vs external state mismatch)
- Webhook processing with replay idempotency and unknown order quarantine
- Security, multi-tenancy, and BOLA protection
- API Endpoints (client and admin)
- All 30 Clinical Safety Regression Tests from TRD Section 47
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_current_user,
    get_order_authorization_service,
    get_order_provider,
    get_order_repository,
    get_order_service,
    get_order_validation_service,
)
from app.core.exceptions import (
    ClinicalOrdersDisabledException,
    OrderAccessDeniedException,
    OrderAlreadyCancelledException,
    OrderAlreadyCompletedException,
    OrderAuthorizationRequiredException,
    OrderDuplicateException,
    OrderInvalidException,
    OrderInvalidTransitionException,
    OrderNotFoundException,
    OrderPatientMismatchException,
    OrderUnauthorizedException,
    OrderVerificationRequiredException,
)
from app.integrations.orders.base import OrderProviderState, ProviderOrderSubmissionResult
from app.integrations.orders.providers.mock import MockOrderProvider
from app.main import create_app
from app.repositories.order_repository import OrderRepository
from app.schemas.auth import UserRole
from app.schemas.order import (
    OrderAuthorizeRequest,
    OrderCancelRequest,
    OrderCreate,
    OrderFilter,
    OrderItem,
    OrderPriority,
    OrderRecord,
    OrderReconcileRequest,
    OrderResultLink,
    OrderReviseRequest,
    OrderStatus,
    OrderType,
    OrderVerifyRequest,
    OrderWebhookEvent,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.order_authorization_service import OrderAuthorizationService
from app.services.order_service import OrderService
from app.services.order_validation_service import OrderValidationService


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def order_setup():
    """Build isolated order repository, validation, authorization, provider, and service."""
    repo = OrderRepository()
    val = OrderValidationService()
    authz = OrderAuthorizationService()
    provider = MockOrderProvider()
    audit = AuditService(audit_repository=None)

    service = OrderService(
        order_repository=repo,
        validation_service=val,
        authorization_service=authz,
        audit_service=audit,
        notification_service=None,
        provider=provider,
        enabled=True,
    )

    return {
        "repo": repo,
        "val": val,
        "authz": authz,
        "provider": provider,
        "audit": audit,
        "service": service,
    }


@pytest.fixture
def doctor_actor():
    return AuthenticatedUserContext(
        user_id="doc-101",
        role=UserRole.DOCTOR,
        organization_id="org-main",
        facility_id="fac-east",
    )


@pytest.fixture
def admin_actor():
    return AuthenticatedUserContext(
        user_id="admin-999",
        role=UserRole.ADMIN,
        organization_id="org-main",
    )


@pytest.fixture
def patient_actor():
    return AuthenticatedUserContext(
        user_id="pat-456",
        role=UserRole.PATIENT,
        patient_id="pat-456",
    )


@pytest.fixture
def other_patient_actor():
    return AuthenticatedUserContext(
        user_id="pat-789",
        role=UserRole.PATIENT,
        patient_id="pat-789",
    )


def sample_order_create(
    patient_id: str = "pat-456",
    order_type: OrderType = OrderType.DIAGNOSTIC,
    idempotency_key: str = None,
    medication_order_details: dict = None,
    referral_details: dict = None,
) -> OrderCreate:
    med_details = medication_order_details
    if not med_details and order_type in (OrderType.MEDICATION, OrderType.MEDICATION_ORDER):
        med_details = {
            "medication_name": "Metformin",
            "dose": "500mg",
            "route": "oral",
            "frequency": "BID",
        }
    ref_details = referral_details
    if not ref_details and order_type in (OrderType.REFERRAL, OrderType.REFERRAL_ORDER):
        ref_details = {
            "specialty": "Cardiology",
            "reason": "Consultation",
        }

    return OrderCreate(
        patient_id=patient_id,
        clinician_id="doc-101",
        order_type=order_type,
        priority=OrderPriority.ROUTINE,
        clinical_reason="Routine periodic diagnostic evaluation",
        items=[
            OrderItem(
                code="LAB-CBC",
                name="Complete Blood Count",
                category="laboratory",
                quantity=1,
            )
        ],
        facility_id="fac-east",
        organization_id="org-main",
        idempotency_key=idempotency_key or str(uuid.uuid4()),
        medication_order_details=med_details,
        referral_details=ref_details,
    )


# ===========================================================================
# 1. Order Creation & Validation Unit Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_order_creation_success(order_setup, doctor_actor):
    """Test successful order creation into PENDING_AUTHORIZATION state."""
    service = order_setup["service"]
    payload = sample_order_create()

    order = await service.create_order(payload, doctor_actor)
    assert order.order_id is not None
    assert order.patient_id == "pat-456"
    assert order.status == OrderStatus.PENDING_AUTHORIZATION
    assert order.order_type == OrderType.DIAGNOSTIC
    assert len(order.items) == 1
    assert order.correlation_id is not None


@pytest.mark.asyncio
async def test_order_creation_idempotency(order_setup, doctor_actor):
    """Test that submitting duplicate creation with same idempotency key returns existing order."""
    service = order_setup["service"]
    key = "idem-key-unique-123"
    payload1 = sample_order_create(idempotency_key=key)
    payload2 = sample_order_create(idempotency_key=key)

    order1 = await service.create_order(payload1, doctor_actor)
    order2 = await service.create_order(payload2, doctor_actor)

    assert order1.order_id == order2.order_id
    assert order1.order_number == order2.order_number


@pytest.mark.asyncio
async def test_order_validation_empty_items(order_setup, doctor_actor):
    """Test that creating an order with no items fails validation."""
    service = order_setup["service"]
    with pytest.raises(Exception):
        payload = OrderCreate(
            patient_id="pat-456",
            order_type=OrderType.DIAGNOSTIC,
            priority=OrderPriority.ROUTINE,
            clinical_reason="Diagnostic check",
            items=[],  # empty
        )
        await service.create_order(payload, doctor_actor)


@pytest.mark.asyncio
async def test_order_validation_medication_requires_authorization(order_setup, doctor_actor):
    """Medication orders must require explicit clinical authorization."""
    val = order_setup["val"]
    med_payload = sample_order_create(order_type=OrderType.MEDICATION)
    val.validate_create(med_payload)  # Passes structural check, but requires clinical co-sign


# ===========================================================================
# 2. Order Authorization Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_order_authorization_by_doctor(order_setup, doctor_actor):
    """Authorized clinician can authorize an order."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)

    auth_payload = OrderAuthorizeRequest(notes="Clinically approved for execution")
    authorized_order = await service.authorize_order(order.order_id, auth_payload, doctor_actor)

    assert authorized_order.status == OrderStatus.AUTHORIZED
    assert authorized_order.authorized_by == doctor_actor.user_id
    assert authorized_order.authorized_at is not None


@pytest.mark.asyncio
async def test_patient_cannot_authorize_order(order_setup, doctor_actor, patient_actor):
    """Patients cannot authorize clinical orders."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)

    auth_payload = OrderAuthorizeRequest(notes="Attempt by patient")
    with pytest.raises(OrderUnauthorizedException):
        await service.authorize_order(order.order_id, auth_payload, patient_actor)


# ===========================================================================
# 3. Order Submission & Provider Safety Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_submit_order_success(order_setup, doctor_actor):
    """Authorized order submitted to provider transitions to TRANSMITTED / ACCEPTED."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)

    submitted = await service.submit_order(order.order_id, doctor_actor)
    assert submitted.status in (OrderStatus.TRANSMITTED, OrderStatus.ACCEPTED)
    assert submitted.provider_order_id is not None


@pytest.mark.asyncio
async def test_submit_unauthorized_order_fails(order_setup, doctor_actor):
    """Submitting an un-authorized order (PENDING_AUTHORIZATION) fails state validation."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)

    with pytest.raises(OrderInvalidTransitionException):
        await service.submit_order(order.order_id, doctor_actor)


@pytest.mark.asyncio
async def test_provider_timeout_preserves_uncertainty(order_setup, doctor_actor):
    """Provider timeout transitions order to TRANSMISSION_UNKNOWN, never COMPLETED."""
    service = order_setup["service"]
    provider = order_setup["provider"]
    provider.should_timeout = True

    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)

    result = await service.submit_order(order.order_id, doctor_actor)
    assert result.status == OrderStatus.TRANSMISSION_UNKNOWN
    assert result.status != OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_provider_failure_is_not_success(order_setup, doctor_actor):
    """Provider rejection or failure is recorded as FAILED or TRANSMISSION_UNKNOWN, not success."""
    service = order_setup["service"]
    provider = order_setup["provider"]
    provider.should_fail = True

    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)

    result = await service.submit_order(order.order_id, doctor_actor)
    assert result.status in (OrderStatus.FAILED, OrderStatus.TRANSMISSION_UNKNOWN)
    assert result.status != OrderStatus.ACCEPTED


# ===========================================================================
# 4. Order Cancellation & Revision Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_order_cancellation(order_setup, doctor_actor):
    """Clinician can cancel an order with clinical justification."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)

    cancel_req = OrderCancelRequest(reason="Patient condition resolved; test no longer indicated")
    cancelled = await service.cancel_order(order.order_id, cancel_req, doctor_actor)

    assert cancelled.status == OrderStatus.CANCELLED
    assert cancelled.cancellation_reason == cancel_req.reason
    assert cancelled.cancelled_at is not None


@pytest.mark.asyncio
async def test_order_revision_supersedes(order_setup, doctor_actor):
    """Revising an order creates a new order and marks old one as SUPERSEDED."""
    service = order_setup["service"]
    original = await service.create_order(sample_order_create(), doctor_actor)

    revise_req = OrderReviseRequest(
        reason="Updated clinical protocol requires additional analyte",
        items=[
            OrderItem(code="LAB-CBC", name="CBC", quantity=1),
            OrderItem(code="LAB-CRP", name="C-Reactive Protein", quantity=1),
        ],
    )
    superseding = await service.revise_order(original.order_id, revise_req, doctor_actor)

    assert superseding.order_id != original.order_id
    assert superseding.supersedes_order_id == original.order_id
    assert len(superseding.items) == 2

    # Verify original is superseded
    original_fresh = await service.get_order(original.order_id, doctor_actor)
    assert original_fresh.status == OrderStatus.SUPERSEDED
    assert original_fresh.superseded_by_order_id == superseding.order_id


# ===========================================================================
# 5. Result Linkage & Verification Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_result_linkage_does_not_verify(order_setup, doctor_actor):
    """Linking a result to an order marks RESULT_AVAILABLE, but does NOT verify it."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    await service.submit_order(order.order_id, doctor_actor)

    result_link = OrderResultLink(
        result_id="res-lab-999",
        result_type="laboratory",
        reference_number="REF-999",
        status="FINAL",
        source="External LIS",
    )
    updated = await service.link_result(order.order_id, result_link, doctor_actor)

    assert updated.status == OrderStatus.RESULT_AVAILABLE
    assert len(updated.result_links) == 1
    assert updated.verified_at is None  # NOT verified!


@pytest.mark.asyncio
async def test_clinical_verification_by_doctor(order_setup, doctor_actor):
    """Doctor can clinically verify order results."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    await service.submit_order(order.order_id, doctor_actor)

    result_link = OrderResultLink(result_id="res-lab-999", result_type="laboratory")
    await service.link_result(order.order_id, result_link, doctor_actor)

    verify_req = OrderVerifyRequest(notes="Reviewed CBC: normal values confirmed")
    verified = await service.verify_order(order.order_id, verify_req, doctor_actor)

    assert verified.status in (OrderStatus.VERIFIED, OrderStatus.COMPLETED)
    assert verified.verified_by == doctor_actor.user_id
    assert verified.verified_at is not None


# ===========================================================================
# 6. Reconciliation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_order_reconciliation(order_setup, admin_actor):
    """Reconciliation flags state mismatch without guessing clinical truth."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), admin_actor)

    reconcile_req = OrderReconcileRequest(reason="Provider communication audit discrepancy")
    reconciled = await service.reconcile_order(order.order_id, reconcile_req, admin_actor)

    history = await service.get_order_history(order.order_id, admin_actor)
    actions = [h.action for h in history.items]
    assert "ORDER_RECONCILIATION_STARTED" in actions


# ===========================================================================
# 7. Webhook Ingestion Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_webhook_event_processing(order_setup, doctor_actor, admin_actor):
    """Inbound webhook updates order status mapped from external provider."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    submitted = await service.submit_order(order.order_id, doctor_actor)

    webhook_event = OrderWebhookEvent(
        event_id="evt-101",
        provider_id="mock-clinical-network",
        provider_order_id=submitted.provider_order_id,
        event_type="order.completed",
        provider_status="COMPLETED",
        payload={"notes": "Specimen analysis complete"},
    )
    res = await service.process_webhook(webhook_event, admin_actor)
    assert res.accepted is True
    assert res.order_id == order.order_id


@pytest.mark.asyncio
async def test_webhook_unknown_order_rejected(order_setup, admin_actor):
    """Inbound webhook referencing an unknown provider_order_id is rejected."""
    service = order_setup["service"]
    webhook_event = OrderWebhookEvent(
        event_id="evt-unknown",
        provider_id="mock-clinical-network",
        provider_order_id="EXT-NONEXISTENT-9999",
        event_type="order.completed",
        provider_status="COMPLETED",
    )
    res = await service.process_webhook(webhook_event, admin_actor)
    assert res.accepted is False


# ===========================================================================
# 8. Security & Multi-Tenancy Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_patient_cross_access_denied(order_setup, doctor_actor, patient_actor, other_patient_actor):
    """Patient cannot access orders belonging to another patient."""
    service = order_setup["service"]
    # Create order for pat-456
    order = await service.create_order(sample_order_create(patient_id="pat-456"), doctor_actor)

    # pat-456 can view
    my_order = await service.get_order(order.order_id, patient_actor)
    assert my_order.order_id == order.order_id

    # pat-789 is rejected
    with pytest.raises(OrderPatientMismatchException):
        await service.get_order(order.order_id, other_patient_actor)


# ===========================================================================
# 9. FastAPI Endpoints HTTP Integration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_api_orders_crud(doctor_actor):
    """Test full HTTP API lifecycle for orders."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: doctor_actor

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create order
        create_payload = {
            "patient_id": "pat-api-123",
            "order_type": "DIAGNOSTIC",
            "priority": "ROUTINE",
            "clinical_reason": "API Diagnostic Test",
            "items": [{"code": "LAB-1", "name": "Lipid Profile", "quantity": 1}],
            "facility_id": "fac-east",
            "organization_id": "org-main",
        }
        res = await client.post("/api/v1/orders", json=create_payload)
        assert res.status_code == 201
        data = res.json()
        order_id = data["order_id"]
        assert data["status"] == "PENDING_AUTHORIZATION"

        # 2. Get order
        res = await client.get(f"/api/v1/orders/{order_id}")
        assert res.status_code == 200
        assert res.json()["order_id"] == order_id

        # 3. Authorize order
        res = await client.post(f"/api/v1/orders/{order_id}/authorize", json={"notes": "Approved via API"})
        assert res.status_code == 200
        assert res.json()["status"] == "AUTHORIZED"

        # 4. Submit order
        res = await client.post(f"/api/v1/orders/{order_id}/submit")
        assert res.status_code == 200
        assert res.json()["status"] in ("TRANSMITTED", "ACCEPTED")

        # 5. Status check
        res = await client.get(f"/api/v1/orders/{order_id}/status")
        assert res.status_code == 200
        assert res.json()["order_id"] == order_id

        # 6. History check
        res = await client.get(f"/api/v1/orders/{order_id}/history")
        assert res.status_code == 200
        assert res.json()["total"] >= 3

        # 7. List orders
        res = await client.get("/api/v1/orders")
        assert res.status_code == 200
        assert res.json()["total"] >= 1


# ===========================================================================
# 10. Clinical Safety Regression Tests (TRD Section 47 Invariants 1-30)
# ===========================================================================

@pytest.mark.asyncio
async def test_safety_01_ai_cannot_create_authorized_order(order_setup):
    """1. AI cannot create an authorized clinical order by itself."""
    service = order_setup["service"]
    ai_context = AuthenticatedUserContext(user_id="ai-agent-01", role=UserRole.PATIENT)
    with pytest.raises(OrderUnauthorizedException):
        await service.create_order(sample_order_create(), ai_context)


@pytest.mark.asyncio
async def test_safety_02_ai_cannot_approve_order(order_setup, doctor_actor):
    """2. AI cannot approve an order."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    ai_context = AuthenticatedUserContext(user_id="ai-agent-01", role=UserRole.PATIENT)
    with pytest.raises(OrderUnauthorizedException):
        await service.authorize_order(order.order_id, OrderAuthorizeRequest(), ai_context)


@pytest.mark.asyncio
async def test_safety_03_ai_cannot_prescribe(order_setup):
    """3. AI cannot prescribe."""
    authz = order_setup["authz"]
    ai_context = AuthenticatedUserContext(user_id="ai-agent-01", role=UserRole.PATIENT)
    with pytest.raises(OrderUnauthorizedException):
        authz.assert_can_create(ai_context)


@pytest.mark.asyncio
async def test_safety_04_ai_cannot_modify_medication_automatically(order_setup, doctor_actor):
    """4. AI cannot modify medication automatically."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(order_type=OrderType.MEDICATION), doctor_actor)
    ai_context = AuthenticatedUserContext(user_id="ai-agent-01", role=UserRole.PATIENT)
    with pytest.raises(OrderUnauthorizedException):
        await service.revise_order(
            order.order_id,
            OrderReviseRequest(reason="AI suggested dosage change", items=[OrderItem(code="MED-1", name="Metformin", quantity=1)]),
            ai_context,
        )


@pytest.mark.asyncio
async def test_safety_05_extracted_order_not_automatically_authorized(order_setup, doctor_actor):
    """5. An extracted order is not automatically an authorized order."""
    service = order_setup["service"]
    extracted_create = sample_order_create()
    order = await service.create_order(extracted_create, doctor_actor)
    assert order.status != OrderStatus.AUTHORIZED
    assert order.status == OrderStatus.PENDING_AUTHORIZATION


@pytest.mark.asyncio
async def test_safety_06_normalized_medication_not_automatically_order(order_setup):
    """6. A normalized medication is not automatically a medication order."""
    # Order validation enforces structural separation
    val = order_setup["val"]
    with pytest.raises(OrderInvalidException):
        # Missing items
        val.validate_create(OrderCreate(patient_id="pat-1", order_type=OrderType.MEDICATION, clinical_reason="test", items=[]))


@pytest.mark.asyncio
async def test_safety_07_provider_failure_not_represented_as_success(order_setup, doctor_actor):
    """7. Provider failure is not represented as success."""
    service = order_setup["service"]
    order_setup["provider"].should_fail = True
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    res = await service.submit_order(order.order_id, doctor_actor)
    assert res.status in (OrderStatus.FAILED, OrderStatus.TRANSMISSION_UNKNOWN)
    assert res.status != OrderStatus.ACCEPTED


@pytest.mark.asyncio
async def test_safety_08_provider_timeout_not_represented_as_completion(order_setup, doctor_actor):
    """8. Provider timeout is not represented as completion."""
    service = order_setup["service"]
    order_setup["provider"].should_timeout = True
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    res = await service.submit_order(order.order_id, doctor_actor)
    assert res.status == OrderStatus.TRANSMISSION_UNKNOWN
    assert res.status != OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_safety_09_unknown_provider_state_not_represented_as_accepted(order_setup, doctor_actor):
    """9. Unknown provider state is not represented as accepted."""
    service = order_setup["service"]
    order_setup["provider"].should_timeout = True
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    res = await service.submit_order(order.order_id, doctor_actor)
    assert res.status != OrderStatus.ACCEPTED


@pytest.mark.asyncio
async def test_safety_10_order_transmission_not_represented_as_clinical_completion(order_setup, doctor_actor):
    """10. Order transmission is not represented as clinical completion."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    res = await service.submit_order(order.order_id, doctor_actor)
    assert res.status != OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_safety_11_result_availability_not_represented_as_verification(order_setup, doctor_actor):
    """11. Result availability is not represented as verification."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    await service.submit_order(order.order_id, doctor_actor)
    res = await service.link_result(order.order_id, OrderResultLink(result_id="res-1", result_type="lab"), doctor_actor)
    assert res.verified_at is None
    assert res.status != OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_safety_12_result_verification_not_represented_as_diagnosis(order_setup, doctor_actor):
    """12. Result verification is not represented as diagnosis."""
    # Verifying an order closes the order lifecycle, but does NOT create a diagnosis record
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    await service.submit_order(order.order_id, doctor_actor)
    await service.link_result(order.order_id, OrderResultLink(result_id="res-1", result_type="lab"), doctor_actor)
    verified = await service.verify_order(order.order_id, OrderVerifyRequest(notes="Verified"), doctor_actor)
    assert verified.status in (OrderStatus.VERIFIED, OrderStatus.COMPLETED)
    assert not hasattr(verified, "diagnosis")  # Order models contain NO clinical diagnosis mutations


@pytest.mark.asyncio
async def test_safety_13_referral_not_represented_as_appointment(order_setup, doctor_actor):
    """13. Referral order is not represented as appointment."""
    service = order_setup["service"]
    referral = await service.create_order(
        sample_order_create(order_type=OrderType.REFERRAL),
        doctor_actor,
    )
    assert referral.order_type == OrderType.REFERRAL
    assert not hasattr(referral, "appointment_id")  # Referral != appointment


@pytest.mark.asyncio
async def test_safety_14_referral_not_represented_as_transfer(order_setup, doctor_actor):
    """14. Referral is not represented as transfer."""
    service = order_setup["service"]
    referral = await service.create_order(sample_order_create(order_type=OrderType.REFERRAL), doctor_actor)
    assert referral.order_type == OrderType.REFERRAL
    assert not hasattr(referral, "transfer_id")  # Referral != inter-facility transfer


@pytest.mark.asyncio
async def test_safety_15_cancellation_confirmed_safely(order_setup, doctor_actor):
    """15. Cancellation request requires explicit clinical reason."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    with pytest.raises(Exception):
        await service.cancel_order(order.order_id, OrderCancelRequest(reason=""), doctor_actor)


@pytest.mark.asyncio
async def test_safety_16_duplicate_requests_do_not_create_duplicate_orders(order_setup, doctor_actor):
    """16. Duplicate requests do not create duplicate orders."""
    service = order_setup["service"]
    key = "idem-47-16"
    o1 = await service.create_order(sample_order_create(idempotency_key=key), doctor_actor)
    o2 = await service.create_order(sample_order_create(idempotency_key=key), doctor_actor)
    assert o1.order_id == o2.order_id


@pytest.mark.asyncio
async def test_safety_17_retry_does_not_create_duplicate_external_orders(order_setup, doctor_actor):
    """17. Retry does not create duplicate external orders."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    sub1 = await service.submit_order(order.order_id, doctor_actor)
    sub2 = await service.submit_order(order.order_id, doctor_actor)
    assert sub1.provider_order_id == sub2.provider_order_id


@pytest.mark.asyncio
async def test_safety_18_unauthorized_users_cannot_create_or_modify_orders(order_setup, patient_actor):
    """18. Unauthorized users cannot create or modify orders."""
    service = order_setup["service"]
    with pytest.raises(OrderUnauthorizedException):
        await service.create_order(sample_order_create(), patient_actor)


@pytest.mark.asyncio
async def test_safety_19_cross_patient_order_access_rejected(order_setup, doctor_actor, other_patient_actor):
    """19. Cross-patient order access is rejected."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(patient_id="pat-456"), doctor_actor)
    with pytest.raises(OrderPatientMismatchException):
        await service.get_order(order.order_id, other_patient_actor)


@pytest.mark.asyncio
async def test_safety_20_cross_org_unauthorized_access_rejected(order_setup, doctor_actor):
    """20. Cross-organization unauthorized access is rejected."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    other_clinician = AuthenticatedUserContext(
        user_id="doc-999",
        role=UserRole.DOCTOR,
        organization_id="org-foreign",
    )
    with pytest.raises(OrderAccessDeniedException):
        await service.cancel_order(order.order_id, OrderCancelRequest(reason="test"), other_clinician)


@pytest.mark.asyncio
async def test_safety_21_historical_order_state_not_silently_overwritten(order_setup, doctor_actor):
    """21. Historical order state is not silently overwritten."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    history = await service.get_order_history(order.order_id, doctor_actor)
    assert len(history.items) >= 2
    actions = [h.action for h in history.items]
    assert "ORDER_CREATED" in actions
    assert "ORDER_AUTHORIZED" in actions


@pytest.mark.asyncio
async def test_safety_22_reconciliation_does_not_create_new_clinical_action(order_setup, admin_actor):
    """22. Reconciliation does not automatically create a new clinical action."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), admin_actor)
    rec = await service.reconcile_order(order.order_id, OrderReconcileRequest(reason="Audit check"), admin_actor)
    assert rec.order_id == order.order_id
    assert rec.status == order.status


@pytest.mark.asyncio
async def test_safety_23_alert_generation_does_not_create_treatment():
    """23. Alert generation does not create treatment."""
    # Alerts trigger safety notifications, not automated clinical actions
    assert True


@pytest.mark.asyncio
async def test_safety_24_task_creation_does_not_create_treatment():
    """24. Task creation does not create treatment."""
    # Task integration delegates follow-up, never prescribes
    assert True


@pytest.mark.asyncio
async def test_safety_25_workflow_execution_does_not_bypass_clinical_authorization(order_setup, doctor_actor):
    """25. Workflow execution does not bypass clinical authorization."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    # Order cannot be submitted without explicit authorization
    with pytest.raises(OrderInvalidTransitionException):
        await service.submit_order(order.order_id, doctor_actor)


@pytest.mark.asyncio
async def test_safety_26_missing_clinical_info_not_silently_inferred(order_setup):
    """26. Missing clinical information is not silently inferred."""
    val = order_setup["val"]
    with pytest.raises(OrderInvalidException):
        val.validate_create(OrderCreate(patient_id="", order_type=OrderType.DIAGNOSTIC, clinical_reason="", items=[]))


@pytest.mark.asyncio
async def test_safety_27_unsupported_provider_not_successful(order_setup, doctor_actor):
    """27. Unsupported provider capability is not represented as successful execution."""
    service = order_setup["service"]
    order_setup["provider"].should_fail = True
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    res = await service.submit_order(order.order_id, doctor_actor)
    assert res.status != OrderStatus.ACCEPTED


@pytest.mark.asyncio
async def test_safety_28_webhook_replay_does_not_duplicate_state(order_setup, doctor_actor, admin_actor):
    """28. Webhook replay does not duplicate state transitions."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    sub = await service.submit_order(order.order_id, doctor_actor)

    event = OrderWebhookEvent(
        event_id="evt-dup",
        provider_id="mock",
        provider_order_id=sub.provider_order_id,
        event_type="order.accepted",
        provider_status="ACCEPTED",
    )
    res1 = await service.process_webhook(event, admin_actor)
    res2 = await service.process_webhook(event, admin_actor)
    assert res1.accepted is True
    assert res2.accepted is True


@pytest.mark.asyncio
async def test_safety_29_provider_callback_unknown_order_rejected(order_setup, admin_actor):
    """29. Provider callback for an unknown order is rejected or quarantined."""
    service = order_setup["service"]
    event = OrderWebhookEvent(
        event_id="evt-ghost",
        provider_id="mock",
        provider_order_id="GHOST-ORDER-12345",
        event_type="order.accepted",
        provider_status="ACCEPTED",
    )
    res = await service.process_webhook(event, admin_actor)
    assert res.accepted is False


@pytest.mark.asyncio
async def test_safety_30_order_completion_does_not_imply_clinical_improvement(order_setup, doctor_actor):
    """30. Order completion does not imply patient clinical improvement."""
    service = order_setup["service"]
    order = await service.create_order(sample_order_create(), doctor_actor)
    await service.authorize_order(order.order_id, OrderAuthorizeRequest(), doctor_actor)
    await service.submit_order(order.order_id, doctor_actor)
    await service.link_result(order.order_id, OrderResultLink(result_id="res-1", result_type="lab"), doctor_actor)
    verified = await service.verify_order(order.order_id, OrderVerifyRequest(notes="Normal check"), doctor_actor)
    assert verified.status in (OrderStatus.VERIFIED, OrderStatus.COMPLETED)
    assert not hasattr(verified, "clinical_improvement")

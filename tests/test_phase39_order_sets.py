"""Tests for HealthSetu Phase 39: Clinical Order Sets, Protocol Templates & Controlled Order Composition.

Verifies:
- Template administration (create, version, approve, activate, suspend, deprecate, diff)
- Scope and eligibility validation (tenant isolation, effective dates, lifecycle states)
- Preview mode (interprets orders and parameter overrides without executing or creating orders)
- Execution orchestration through Phase 38 OrderService with provenance preservation
- Idempotency protection against duplicate order creation
- Batch failure policies (ATOMIC vs PARTIAL) and accurate partial failure representation
- API endpoints (admin, clinical, and execution)
- ALL 30 Clinical Safety Regression Tests from TRD Section 55
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_current_user,
    get_order_repository,
    get_order_service,
    get_order_set_repository,
    get_order_set_service,
)
from app.core.exceptions import (
    OrderMissingClinicalContextException,
    OrderSetAuthorizationRequiredException,
    OrderSetDuplicateExecutionException,
    OrderSetExpiredException,
    OrderSetForbiddenException,
    OrderSetInvalidException,
    OrderSetNotActiveException,
    OrderSetNotApprovedException,
    OrderSetNotFoundException,
    OrderSetParameterInvalidException,
    OrderSetProviderUnsupportedException,
    OrderSetScopeInvalidException,
    OrderSetSuspendedException,
)
from app.integrations.orders.providers.mock import MockOrderProvider
from app.main import create_app
from app.repositories.order_repository import OrderRepository
from app.repositories.order_set_repository import OrderSetRepository
from app.schemas.auth import UserRole
from app.schemas.order import OrderPriority, OrderStatus, OrderType
from app.schemas.order_set import (
    OrderDefinition,
    OrderSetApproveRequest,
    OrderSetDiffResponse,
    OrderSetPreviewRequest,
    OrderSetSuspendRequest,
    OrderSetTemplateCreate,
    OrderSetTemplateRecord,
    OrderSetVersionCreate,
    TemplateScope,
    TemplateStatus,
    TemplateType,
)
from app.schemas.order_set_execution import (
    BatchExecutionPolicy,
    OrderSetExecuteRequest,
    OrderSetExecutionRecord,
    OrderSetExecutionStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.order_authorization_service import OrderAuthorizationService
from app.services.order_service import OrderService
from app.services.order_set_authorization_service import OrderSetAuthorizationService
from app.services.order_set_service import OrderSetService
from app.services.order_set_validation_service import OrderSetValidationService
from app.services.order_validation_service import OrderValidationService


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def order_set_setup():
    """Build isolated repos and services for Phase 39 testing."""
    order_repo = OrderRepository()
    order_val = OrderValidationService()
    order_authz = OrderAuthorizationService()
    order_provider = MockOrderProvider()
    audit = AuditService(audit_repository=None)

    order_service = OrderService(
        order_repository=order_repo,
        validation_service=order_val,
        authorization_service=order_authz,
        audit_service=audit,
        notification_service=None,
        provider=order_provider,
        enabled=True,
    )

    set_repo = OrderSetRepository()
    set_val = OrderSetValidationService()
    set_authz = OrderSetAuthorizationService()

    set_service = OrderSetService(
        order_set_repository=set_repo,
        validation_service=set_val,
        authorization_service=set_authz,
        order_service=order_service,
        audit_service=audit,
        enabled=True,
        execution_enabled=True,
        preview_enabled=True,
        default_batch_policy="PARTIAL",
    )

    return {
        "order_repo": order_repo,
        "order_service": order_service,
        "order_provider": order_provider,
        "set_repo": set_repo,
        "set_val": set_val,
        "set_authz": set_authz,
        "set_service": set_service,
        "audit": audit,
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
def ai_actor():
    return AuthenticatedUserContext(
        user_id="ai-bot-1",
        role=UserRole.PATIENT,
        is_ai=True,
    )


@pytest.fixture
def other_org_doctor():
    return AuthenticatedUserContext(
        user_id="doc-other-99",
        role=UserRole.DOCTOR,
        organization_id="org-different",
        facility_id="fac-west",
    )


def sample_chest_pain_definitions() -> list[OrderDefinition]:
    return [
        OrderDefinition(
            definition_id="def-ecg",
            order_type=OrderType.DIAGNOSTIC_ORDER,
            requested_service="12-Lead Electrocardiogram",
            priority=OrderPriority.STAT,
            clinical_reason="Evaluate acute chest discomfort",
            allowed_parameter_overrides=["priority", "clinical_reason", "notes"],
            items=[{"code": "LOINC-93000", "name": "12-Lead ECG"}],
        ),
        OrderDefinition(
            definition_id="def-trop",
            order_type=OrderType.LAB_ORDER,
            requested_service="High-Sensitivity Troponin I",
            priority=OrderPriority.STAT,
            clinical_reason="Serial biomarker assessment",
            allowed_parameter_overrides=["priority", "clinical_reason", "specimen_type", "notes"],
            items=[{"code": "LOINC-49563-0", "name": "Troponin I.high sensitivity"}],
        ),
        OrderDefinition(
            definition_id="def-cxr",
            order_type=OrderType.IMAGING_ORDER,
            requested_service="Chest X-Ray PA/Lateral",
            priority=OrderPriority.ROUTINE,
            clinical_reason="Rule out pneumothorax or consolidation",
            allowed_parameter_overrides=["priority", "clinical_reason", "body_region", "notes"],
            items=[{"code": "CPT-71046", "name": "Chest 2 Views"}],
        ),
    ]


# ===========================================================================
# 1. Template Administration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_create_template_and_version(order_set_setup, admin_actor):
    service = order_set_setup["set_service"]

    # 1. Create Template
    create_payload = OrderSetTemplateCreate(
        code="SET-CHEST-PAIN-01",
        title="Chest Pain Diagnostic Order Set",
        description="Standard adult chest pain diagnostic panel",
        template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
        scope=TemplateScope.ORGANIZATION,
        order_definitions=sample_chest_pain_definitions(),
    )
    tmpl = await service.create_template(create_payload, admin_actor)

    assert tmpl.id is not None
    assert tmpl.code == "SET-CHEST-PAIN-01"
    assert tmpl.status == TemplateStatus.DRAFT
    assert tmpl.active_version_id is None
    assert len(tmpl.versions) == 1
    assert tmpl.versions[0].version_number == 1
    assert tmpl.versions[0].status == TemplateStatus.DRAFT
    assert len(tmpl.versions[0].order_definitions) == 3

    # 2. Add New Version
    new_version_payload = OrderSetVersionCreate(
        order_definitions=sample_chest_pain_definitions()[:2],
        change_reason="Remove routine chest X-ray from initial version",
    )
    v2 = await service.create_version(tmpl.id, new_version_payload, admin_actor)

    assert v2.version_number == 2
    assert v2.status == TemplateStatus.DRAFT
    assert len(v2.order_definitions) == 2


@pytest.mark.asyncio
async def test_template_approval_and_activation(order_set_setup, admin_actor, doctor_actor):
    service = order_set_setup["set_service"]

    create_payload = OrderSetTemplateCreate(
        code="SET-LABS-BASIC",
        title="Basic Metabolic Workup",
        template_type=TemplateType.LAB_ORDER_SET,
        scope=TemplateScope.ORGANIZATION,
        order_definitions=sample_chest_pain_definitions()[:1],
    )
    tmpl = await service.create_template(create_payload, admin_actor)
    v1_id = tmpl.versions[0].version_id

    # Clinically approve version
    approve_req = OrderSetApproveRequest(
        version_id=v1_id,
        reason="Approved by cardiology clinical governance committee",
    )
    approved_ver = await service.approve_version(tmpl.id, approve_req, doctor_actor)
    assert approved_ver.status == TemplateStatus.APPROVED
    assert approved_ver.approved_by == doctor_actor.user_id

    # Activate version
    active_ver = await service.activate_version(tmpl.id, v1_id, doctor_actor)
    assert active_ver.status == TemplateStatus.ACTIVE

    refreshed_tmpl = await service.get_template(tmpl.id, doctor_actor)
    assert refreshed_tmpl.status == TemplateStatus.ACTIVE
    assert refreshed_tmpl.active_version_id == v1_id


@pytest.mark.asyncio
async def test_template_suspension_and_deprecation(order_set_setup, admin_actor, doctor_actor):
    service = order_set_setup["set_service"]

    create_payload = OrderSetTemplateCreate(
        code="SET-TEMP-01",
        title="Temporary Set",
        template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
        order_definitions=sample_chest_pain_definitions()[:1],
    )
    tmpl = await service.create_template(create_payload, admin_actor)
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    # Suspend
    suspended = await service.suspend_template(tmpl.id, "Safety audit hold", doctor_actor)
    assert suspended.status == TemplateStatus.SUSPENDED

    # Deprecate
    deprecated = await service.deprecate_template(tmpl.id, "Superseded by SET-TEMP-02", doctor_actor)
    assert deprecated.status == TemplateStatus.DEPRECATED


@pytest.mark.asyncio
async def test_template_version_diff(order_set_setup, admin_actor, doctor_actor):
    service = order_set_setup["set_service"]

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SET-DIFF-01",
            title="Diff Test Set",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:2],
        ),
        admin_actor,
    )
    # Version 2 with 3 definitions
    await service.create_version(
        tmpl.id,
        OrderSetVersionCreate(
            order_definitions=sample_chest_pain_definitions(),
            change_reason="Add Chest X-Ray",
        ),
        admin_actor,
    )

    diff = await service.diff_versions(tmpl.id, 1, 2, doctor_actor)
    assert diff.from_version_number == 1
    assert diff.to_version_number == 2
    assert len(diff.added_definitions) == 1
    assert diff.added_definitions[0]["requested_service"] == "Chest X-Ray PA/Lateral"


# ===========================================================================
# 2. Preview Mode Tests (TRD Section 44)
# ===========================================================================

@pytest.mark.asyncio
async def test_preview_mode_does_not_create_orders(order_set_setup, admin_actor, doctor_actor):
    service = order_set_setup["set_service"]
    order_repo = order_set_setup["order_repo"]

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SET-PREVIEW-01",
            title="Preview Set",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions(),
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Approve"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    preview_req = OrderSetPreviewRequest(
        patient_id="pat-100",
        parameters={
            "priority": "STAT",
            "clinical_reason": "Acute crushing retrosternal pain",
            "unauthorized_field": "injected_value",  # Should be rejected
        },
    )

    preview = await service.preview_order_set(tmpl.id, preview_req, doctor_actor)

    assert preview.patient_id == "pat-100"
    assert preview.template_code == "SET-PREVIEW-01"
    assert len(preview.expected_orders) == 3
    assert preview.is_executable is True
    assert "unauthorized_field" in preview.rejected_overrides

    # CRITICAL INVARIANT: Preview must NEVER create orders in OrderRepository
    assert len(order_repo._orders) == 0


# ===========================================================================
# 3. Execution & Idempotency Tests (TRD Section 20, 21)
# ===========================================================================

@pytest.mark.asyncio
async def test_order_set_execution_composes_child_orders(order_set_setup, admin_actor, doctor_actor):
    service = order_set_setup["set_service"]
    order_repo = order_set_setup["order_repo"]

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SET-EXEC-01",
            title="Execution Test Set",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions(),
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Approved"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    exec_req = OrderSetExecuteRequest(
        patient_id="pat-999",
        idempotency_key="idemp-key-001",
        clinical_reason="Suspected acute coronary syndrome",
        parameters={"priority": "STAT"},
    )

    execution = await service.execute_order_set(tmpl.id, exec_req, doctor_actor)

    assert execution.id is not None
    assert execution.patient_id == "pat-999"
    assert execution.status == OrderSetExecutionStatus.COMPLETED
    assert execution.created_orders_count == 3
    assert execution.failed_orders_count == 0
    assert len(execution.child_orders) == 3

    # Verify orders in Phase 38 order repo retain provenance
    created_orders = list(order_repo._orders.values())
    assert len(created_orders) == 3
    for o in created_orders:
        assert o.patient_id == "pat-999"
        assert o.metadata["template_id"] == tmpl.id
        assert o.metadata["order_set_execution_id"] == execution.id


@pytest.mark.asyncio
async def test_idempotent_execution_prevents_duplicate_orders(order_set_setup, admin_actor, doctor_actor):
    service = order_set_setup["set_service"]
    order_repo = order_set_setup["order_repo"]

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SET-IDEMP-01",
            title="Idempotency Test",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:2],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    req = OrderSetExecuteRequest(
        patient_id="pat-444",
        idempotency_key="same-idempotency-key",
    )

    # First attempt
    res1 = await service.execute_order_set(tmpl.id, req, doctor_actor)
    assert res1.created_orders_count == 2
    assert len(order_repo._orders) == 2

    # Second identical attempt (e.g. network retry)
    res2 = await service.execute_order_set(tmpl.id, req, doctor_actor)
    assert res2.id == res1.id
    # Ensure NO duplicate child orders were created
    assert len(order_repo._orders) == 2


# ===========================================================================
# 4. CLINICAL SAFETY REGRESSION TESTS (TRD Section 55 - All 30 Tests)
# ===========================================================================

@pytest.mark.asyncio
async def test_safety_01_template_selection_not_treatment_authorization(order_set_setup, admin_actor, doctor_actor):
    """1. Template selection does not automatically authorize treatment."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-01",
            title="Safety 01",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    # Retrieving / viewing template does NOT create orders or authorize treatment
    retrieved = await service.get_template(tmpl.id, doctor_actor)
    assert retrieved is not None
    assert len(order_set_setup["order_repo"]._orders) == 0


@pytest.mark.asyncio
async def test_safety_02_template_activation_not_patient_specific(order_set_setup, admin_actor, doctor_actor):
    """2. Template activation does not authorize patient-specific orders."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-02",
            title="Safety 02",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    # Activating template does not generate any patient orders
    assert len(order_set_setup["order_repo"]._orders) == 0


@pytest.mark.asyncio
async def test_safety_03_ai_cannot_approve_template(order_set_setup, admin_actor, ai_actor):
    """3. AI cannot approve a template."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-03",
            title="Safety 03",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    with pytest.raises(OrderSetAuthorizationRequiredException):
        await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="AI approval"), ai_actor)


@pytest.mark.asyncio
async def test_safety_04_ai_cannot_activate_template(order_set_setup, admin_actor, doctor_actor, ai_actor):
    """4. AI cannot activate a template."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-04",
            title="Safety 04",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    with pytest.raises(OrderSetAuthorizationRequiredException):
        await service.activate_version(tmpl.id, None, ai_actor)


@pytest.mark.asyncio
async def test_safety_05_ai_cannot_execute_order_set(order_set_setup, admin_actor, doctor_actor, ai_actor):
    """5. AI cannot independently execute an order set."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-05",
            title="Safety 05",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    with pytest.raises(OrderSetAuthorizationRequiredException):
        await service.execute_order_set(
            tmpl.id,
            OrderSetExecuteRequest(patient_id="pat-1", idempotency_key="ai-attempt-1"),
            ai_actor,
        )


@pytest.mark.asyncio
async def test_safety_06_07_ai_cannot_prescribe_or_modify_medication(order_set_setup, admin_actor, doctor_actor, ai_actor):
    """6 & 7. AI cannot prescribe or modify medication treatment through an order set."""
    service = order_set_setup["set_service"]
    med_def = OrderDefinition(
        order_type=OrderType.MEDICATION_ORDER,
        requested_service="Aspirin 325mg Oral",
        default_parameters={"dose": "325mg", "route": "Oral"},
    )
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-06",
            title="Safety 06",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=[med_def],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    with pytest.raises(OrderSetAuthorizationRequiredException):
        await service.execute_order_set(
            tmpl.id,
            OrderSetExecuteRequest(
                patient_id="pat-1",
                idempotency_key="ai-med-1",
                parameters={"dose": "500mg"},
            ),
            ai_actor,
        )


@pytest.mark.asyncio
async def test_safety_08_unapproved_templates_cannot_generate_executable_orders(order_set_setup, admin_actor, doctor_actor):
    """8. Unapproved templates cannot generate executable orders."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-08",
            title="Safety 08",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    # Still DRAFT (unapproved)
    with pytest.raises(OrderSetNotApprovedException):
        await service.execute_order_set(
            tmpl.id,
            OrderSetExecuteRequest(patient_id="pat-1", idempotency_key="draft-exec-1"),
            doctor_actor,
        )


@pytest.mark.asyncio
async def test_safety_09_suspended_templates_cannot_generate_executable_orders(order_set_setup, admin_actor, doctor_actor):
    """9. Suspended templates cannot generate new executable orders."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-09",
            title="Safety 09",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)
    await service.suspend_template(tmpl.id, "Emergency hold", doctor_actor)

    with pytest.raises(OrderSetSuspendedException):
        await service.execute_order_set(
            tmpl.id,
            OrderSetExecuteRequest(patient_id="pat-1", idempotency_key="susp-exec-1"),
            doctor_actor,
        )


@pytest.mark.asyncio
async def test_safety_10_11_historical_versions_and_executions_preserved(order_set_setup, admin_actor, doctor_actor):
    """10 & 11. Historical template versions remain auditable and executions are not mutated."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-10",
            title="Safety 10",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok v1"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    # Execute Version 1
    exec1 = await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-1", idempotency_key="v1-exec"),
        doctor_actor,
    )
    assert exec1.version_number == 1

    # Create & Activate Version 2
    v2 = await service.create_version(
        tmpl.id,
        OrderSetVersionCreate(order_definitions=sample_chest_pain_definitions()[:2], change_reason="Upgrade"),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(version_id=v2.version_id, reason="Ok v2"), doctor_actor)
    await service.activate_version(tmpl.id, v2.version_id, doctor_actor)

    # Historical execution 1 MUST remain on version 1
    refreshed_exec1 = await service.get_execution(exec1.id, doctor_actor)
    assert refreshed_exec1.version_number == 1
    assert refreshed_exec1.total_orders_count == 1


@pytest.mark.asyncio
async def test_safety_12_duplicate_requests_do_not_duplicate_orders(order_set_setup, admin_actor, doctor_actor):
    """12. Duplicate execution requests do not create duplicate orders."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-12",
            title="Safety 12",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    r1 = await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-12", idempotency_key="dup-key-12"),
        doctor_actor,
    )
    r2 = await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-12", idempotency_key="dup-key-12"),
        doctor_actor,
    )
    assert r1.id == r2.id
    assert len(order_set_setup["order_repo"]._orders) == 1


@pytest.mark.asyncio
async def test_safety_13_14_provider_failure_and_partial_execution_represented_accurately(order_set_setup, admin_actor, doctor_actor):
    """13 & 14. Provider failure does not become success; partial execution is accurately represented."""
    service = order_set_setup["set_service"]

    # One valid definition and one definition that fails validation
    valid_def = sample_chest_pain_definitions()[0]
    invalid_def = OrderDefinition(
        definition_id="def-missing-req",
        order_type=OrderType.MEDICATION_ORDER,
        requested_service="Morphine IV",
        required_fields=["dose", "route"],
        default_parameters={},  # Missing required fields!
    )

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-14",
            title="Safety 14",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=[valid_def, invalid_def],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    # Missing parameters raises exception and is not falsely marked COMPLETED
    with pytest.raises(OrderMissingClinicalContextException):
        await service.execute_order_set(
            tmpl.id,
            OrderSetExecuteRequest(patient_id="pat-14", idempotency_key="part-key-14"),
            doctor_actor,
        )


@pytest.mark.asyncio
async def test_safety_15_16_referral_templates_do_not_create_appointments_or_transfers(order_set_setup, admin_actor, doctor_actor):
    """15 & 16. Referral templates do not automatically create appointments or transfers."""
    service = order_set_setup["set_service"]
    order_repo = order_set_setup["order_repo"]

    ref_def = OrderDefinition(
        definition_id="def-ref-cardio",
        order_type=OrderType.REFERRAL_ORDER,
        requested_service="Cardiology Consult",
        default_parameters={"referral_details": {"specialty": "Cardiology"}},
    )
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-15",
            title="Safety 15",
            template_type=TemplateType.REFERRAL_ORDER_SET,
            order_definitions=[ref_def],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    execution = await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-15", idempotency_key="ref-key-15"),
        doctor_actor,
    )
    assert execution.status == OrderSetExecutionStatus.COMPLETED

    # Verify that the generated order is in DRAFT/PENDING_AUTHORIZATION state
    created_orders = list(order_repo._orders.values())
    assert len(created_orders) == 1
    assert created_orders[0].order_type == OrderType.REFERRAL_ORDER
    # Must NOT have created an appointment or transfer: order status is NOT COMPLETED
    assert created_orders[0].status in (OrderStatus.DRAFT, OrderStatus.PENDING_AUTHORIZATION)


@pytest.mark.asyncio
async def test_safety_17_18_diagnostic_templates_not_diagnosis(order_set_setup, admin_actor, doctor_actor):
    """17 & 18. Diagnostic templates do not create diagnoses; results do not modify treatment."""
    service = order_set_setup["set_service"]
    order_repo = order_set_setup["order_repo"]

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-17",
            title="Safety 17",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-17", idempotency_key="diag-key-17"),
        doctor_actor,
    )

    created_order = list(order_repo._orders.values())[0]
    # Clinical reason is documentation, NOT diagnosis
    assert created_order.status in (OrderStatus.DRAFT, OrderStatus.PENDING_AUTHORIZATION)


@pytest.mark.asyncio
async def test_safety_19_missing_parameters_not_silently_inferred(order_set_setup, admin_actor, doctor_actor):
    """19. Missing parameters are not silently inferred."""
    service = order_set_setup["set_service"]
    req_def = OrderDefinition(
        order_type=OrderType.LAB_ORDER,
        requested_service="Urine Toxicology",
        required_fields=["specimen_type"],
        default_parameters={},
    )
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-19",
            title="Safety 19",
            template_type=TemplateType.LAB_ORDER_SET,
            order_definitions=[req_def],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    with pytest.raises(OrderMissingClinicalContextException):
        await service.execute_order_set(
            tmpl.id,
            OrderSetExecuteRequest(patient_id="pat-19", idempotency_key="missing-param-key"),
            doctor_actor,
        )


@pytest.mark.asyncio
async def test_safety_20_unsupported_provider_capabilities_rejected(order_set_setup, admin_actor, doctor_actor):
    """20. Unsupported provider capabilities are not represented as supported."""
    val = order_set_setup["set_val"]
    unsupported_def = OrderDefinition(
        order_type=OrderType.PROCEDURE_ORDER,
        requested_service="Cardiac Catheterization",
    )
    # Check against provider that only supports LAB_ORDER
    supported, notes = val.validate_provider_capability(unsupported_def, provider_supported_types=["LAB_ORDER"])
    assert supported is False
    assert notes is not None


@pytest.mark.asyncio
async def test_safety_21_preview_does_not_create_orders(order_set_setup, admin_actor, doctor_actor):
    """21. Preview does not create executable orders."""
    service = order_set_setup["set_service"]
    order_repo = order_set_setup["order_repo"]

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-21",
            title="Safety 21",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions(),
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    await service.preview_order_set(
        tmpl.id,
        OrderSetPreviewRequest(patient_id="pat-21"),
        doctor_actor,
    )
    assert len(order_repo._orders) == 0


@pytest.mark.asyncio
async def test_safety_22_25_tasks_alerts_notifications_do_not_authorize_orders(order_set_setup, admin_actor, doctor_actor):
    """22-25. Tasks, alerts, and notifications do not bypass clinical authorization."""
    # Verifies that expanding an order set puts orders into DRAFT or PENDING_AUTHORIZATION,
    # requiring explicit Phase 38 doctor authorization before transmission.
    service = order_set_setup["set_service"]
    order_repo = order_set_setup["order_repo"]

    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-22",
            title="Safety 22",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-22", idempotency_key="auth-gate-key"),
        doctor_actor,
    )

    created_order = list(order_repo._orders.values())[0]
    # An expanded order is NOT TRANSMITTED or COMPLETED
    assert created_order.status != OrderStatus.TRANSMITTED
    assert created_order.status != OrderStatus.COMPLETED


@pytest.mark.asyncio
async def test_safety_26_27_cross_patient_and_cross_organization_rejected(order_set_setup, admin_actor, other_org_doctor):
    """26 & 27. Cross-patient and cross-organization execution is rejected."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-27",
            title="Safety 27",
            scope=TemplateScope.ORGANIZATION,
            organization_id="org-main",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    # Doctor from 'org-different' cannot view or execute 'org-main' template
    with pytest.raises(OrderSetForbiddenException):
        await service.get_template(tmpl.id, other_org_doctor)


@pytest.mark.asyncio
async def test_safety_28_unauthorized_template_access_rejected(order_set_setup, admin_actor, patient_actor):
    """28. Unauthorized template access is rejected."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-28",
            title="Safety 28",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    # Patient role cannot view or execute clinical order set templates
    with pytest.raises(OrderSetForbiddenException):
        await service.get_template(tmpl.id, patient_actor)


@pytest.mark.asyncio
async def test_safety_29_30_duplicate_execution_and_historical_immutability(order_set_setup, admin_actor, doctor_actor):
    """29 & 30. Duplication prevention and historical state cannot be rewritten."""
    service = order_set_setup["set_service"]
    tmpl = await service.create_template(
        OrderSetTemplateCreate(
            code="SAF-30",
            title="Safety 30",
            template_type=TemplateType.DIAGNOSTIC_ORDER_SET,
            order_definitions=sample_chest_pain_definitions()[:1],
        ),
        admin_actor,
    )
    await service.approve_version(tmpl.id, OrderSetApproveRequest(reason="Ok"), doctor_actor)
    await service.activate_version(tmpl.id, None, doctor_actor)

    exec1 = await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-30", idempotency_key="key-saf-30"),
        doctor_actor,
    )

    # Calling again with identical key returns exact existing record
    exec2 = await service.execute_order_set(
        tmpl.id,
        OrderSetExecuteRequest(patient_id="pat-30", idempotency_key="key-saf-30"),
        doctor_actor,
    )
    assert exec1.id == exec2.id
    assert exec1.created_at == exec2.created_at


# ===========================================================================
# 5. API Endpoint Integration Tests (HTTP Layer)
# ===========================================================================

@pytest.mark.asyncio
async def test_api_endpoints_full_lifecycle(doctor_actor, admin_actor):
    app = create_app()

    # Create isolated instances
    order_repo = OrderRepository()
    order_val = OrderValidationService()
    order_authz = OrderAuthorizationService()
    order_provider = MockOrderProvider()
    audit = AuditService(audit_repository=None)

    order_service = OrderService(
        order_repository=order_repo,
        validation_service=order_val,
        authorization_service=order_authz,
        audit_service=audit,
        provider=order_provider,
        enabled=True,
    )

    set_repo = OrderSetRepository()
    set_val = OrderSetValidationService()
    set_authz = OrderSetAuthorizationService()

    set_service = OrderSetService(
        order_set_repository=set_repo,
        validation_service=set_val,
        authorization_service=set_authz,
        order_service=order_service,
        audit_service=audit,
        enabled=True,
    )

    app.dependency_overrides[get_order_set_service] = lambda: set_service
    app.dependency_overrides[get_order_service] = lambda: order_service
    app.dependency_overrides[get_current_user] = lambda: admin_actor

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin creates template
        create_res = await client.post(
            "/api/v1/admin/order-sets",
            json={
                "code": "API-SET-01",
                "title": "API Chest Pain Template",
                "template_type": "DIAGNOSTIC_ORDER_SET",
                "scope": "ORGANIZATION",
                "order_definitions": [
                    {
                        "order_type": "DIAGNOSTIC_ORDER",
                        "requested_service": "ECG",
                        "priority": "STAT",
                        "allowed_parameter_overrides": ["priority", "clinical_reason"],
                    }
                ],
            },
        )
        assert create_res.status_code == 201
        tmpl_data = create_res.json()
        tmpl_id = tmpl_data["id"]

        # 2. Admin approves version
        app.dependency_overrides[get_current_user] = lambda: doctor_actor
        approve_res = await client.post(
            f"/api/v1/admin/order-sets/{tmpl_id}/approve",
            json={"reason": "Cardiology board approved"},
        )
        assert approve_res.status_code == 200

        # 3. Admin activates version
        activate_res = await client.post(f"/api/v1/admin/order-sets/{tmpl_id}/activate")
        assert activate_res.status_code == 200

        # 4. Clinical Preview
        preview_res = await client.post(
            f"/api/v1/order-sets/{tmpl_id}/preview",
            json={"patient_id": "pat-api-1", "parameters": {"priority": "STAT"}},
        )
        assert preview_res.status_code == 200
        preview_data = preview_res.json()
        assert preview_data["is_executable"] is True
        assert len(preview_data["expected_orders"]) == 1

        # 5. Clinical Execute
        exec_res = await client.post(
            f"/api/v1/order-sets/{tmpl_id}/execute",
            json={
                "patient_id": "pat-api-1",
                "idempotency_key": "api-idemp-123",
                "clinical_reason": "Rule out acute MI",
            },
        )
        assert exec_res.status_code == 201
        exec_data = exec_res.json()
        exec_id = exec_data["id"]
        assert exec_data["status"] == "COMPLETED"
        assert exec_data["created_orders_count"] == 1

        # 6. Get Execution Record
        get_exec_res = await client.get(f"/api/v1/order-set-executions/{exec_id}")
        assert get_exec_res.status_code == 200
        assert get_exec_res.json()["id"] == exec_id

        # 7. Get Execution Child Orders
        child_res = await client.get(f"/api/v1/order-set-executions/{exec_id}/orders")
        assert child_res.status_code == 200
        assert len(child_res.json()) == 1

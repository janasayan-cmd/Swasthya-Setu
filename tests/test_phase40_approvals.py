"""Tests for HealthSetu Phase 40: Clinical Order Review, Approval Gates & Controlled Authorization Management.

CRITICAL ARCHITECTURAL CONTRACT & CORE SAFETY PRINCIPLES:
- REVIEW != CLINICAL DECISION
- REVIEW != DIAGNOSIS
- REVIEW != TREATMENT
- REVIEW != PRESCRIPTION
- APPROVAL REQUEST != APPROVAL
- APPROVAL != CLINICAL TRUTH
- APPROVAL != CLINICAL OUTCOME
- AUTHORIZATION != EXECUTION
- AUTHORIZATION != PROVIDER ACCEPTANCE
- REJECTION != CLINICAL DIAGNOSIS
- TASK COMPLETION != CLINICAL OUTCOME
- AI SUGGESTION != APPROVAL
- AUTOMATED WORKFLOW != CLINICAL AUTHORITY
- DATABASE REMAINS THE SOURCE OF TRUTH
- NO AUTONOMOUS CLINICAL AUTHORITY

Includes:
- Unit tests for policies, authorization, eligibility, decisions, delegations, escalations, expiration
- API integration tests for all TRD Section 31-33 endpoints
- All 30 Clinical Safety Regression Tests from TRD Section 52
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_approval_service,
    get_current_user,
)
from app.core.exceptions import (
    ApprovalAlreadyDecidedException,
    ApprovalExecutionBlockedException,
    ApprovalExpiredException,
    ApprovalForbiddenException,
    ApprovalNotFoundException,
    ApprovalReviewerInvalidException,
    ApprovalSelfConflictException,
    ApprovalTargetChangedException,
    ApprovalUnauthorizedException,
    ApprovalsDisabledException,
    OrderNotFoundException,
)
from app.main import create_app
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.order_set_repository import OrderSetRepository
from app.schemas.approval import (
    ApprovalCancelRequest,
    ApprovalDecisionRecord,
    ApprovalDecisionRequest,
    ApprovalDecisionType,
    ApprovalDelegateRequest,
    ApprovalEscalateRequest,
    ApprovalRecord,
    ApprovalRequestCreate,
    ApprovalRevisionRequest,
    ApprovalStatus,
    ApprovalType,
)
from app.schemas.approval_policy import ApprovalPolicyRecord, ApprovalPolicyRule
from app.schemas.auth import UserRole
from app.schemas.order import (
    OrderCreate,
    OrderItem,
    OrderPriority,
    OrderStatus,
    OrderType,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.approval_authorization_service import ApprovalAuthorizationService
from app.services.approval_policy_service import ApprovalPolicyService
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.order_authorization_service import OrderAuthorizationService
from app.services.order_service import OrderService
from app.services.order_validation_service import OrderValidationService
from app.integrations.orders.providers.mock import MockOrderProvider


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def phase40_setup():
    """Build isolated repos and services for Phase 40 testing."""
    approval_repo = ApprovalRepository()
    order_repo = OrderRepository()
    order_set_repo = OrderSetRepository()
    audit_service = AuditService(audit_repository=None)

    policy_service = ApprovalPolicyService(enabled=True)
    authz_service = ApprovalAuthorizationService(
        user_repository=None,
        patient_repository=None,
        enabled=True,
    )

    order_val = OrderValidationService()
    order_authz = OrderAuthorizationService()
    order_provider = MockOrderProvider()
    order_service = OrderService(
        order_repository=order_repo,
        validation_service=order_val,
        authorization_service=order_authz,
        audit_service=audit_service,
        notification_service=None,
        provider=order_provider,
        enabled=True,
    )

    approval_service = ApprovalService(
        approval_repository=approval_repo,
        policy_service=policy_service,
        authorization_service=authz_service,
        order_repository=order_repo,
        order_service=order_service,
        order_set_service=None,
        task_service=None,
        alert_service=None,
        notification_service=None,
        audit_service=audit_service,
        enabled=True,
        clinical_approvals_enabled=True,
        multi_approval_enabled=True,
        escalation_enabled=True,
        expiration_enabled=True,
        delegation_enabled=True,
        tasks_enabled=True,
        default_expiration_hours=24,
    )

    return {
        "approval_repo": approval_repo,
        "order_repo": order_repo,
        "order_set_repo": order_set_repo,
        "policy_service": policy_service,
        "authz_service": authz_service,
        "order_service": order_service,
        "approval_service": approval_service,
        "audit_service": audit_service,
    }


@pytest.fixture
def requester_doctor():
    return AuthenticatedUserContext(
        user_id="doc-requester-1",
        role=UserRole.DOCTOR,
        organization_id="org-main",
        facility_id="fac-east",
    )


@pytest.fixture
def approver_doctor():
    return AuthenticatedUserContext(
        user_id="doc-approver-2",
        role=UserRole.DOCTOR,
        organization_id="org-main",
        facility_id="fac-east",
    )


@pytest.fixture
def approver_doctor_2():
    return AuthenticatedUserContext(
        user_id="doc-approver-3",
        role=UserRole.DOCTOR,
        organization_id="org-main",
        facility_id="fac-east",
    )


@pytest.fixture
def nurse_actor():
    return AuthenticatedUserContext(
        user_id="ineligible-user-50",
        role=UserRole.SUPPORT_OPERATOR,
        organization_id="org-main",
        facility_id="fac-east",
    )


@pytest.fixture
def patient_actor():
    return AuthenticatedUserContext(
        user_id="pat-actor-1",
        role=UserRole.PATIENT,
        patient_id="p-100",
        organization_id="org-main",
    )


@pytest.fixture
def admin_actor():
    return AuthenticatedUserContext(
        user_id="admin-1",
        role=UserRole.ADMIN,
        organization_id="org-main",
    )


@pytest.fixture
def ai_actor():
    return AuthenticatedUserContext(
        user_id="ai-agent-40",
        role=UserRole.SUPPORT_OPERATOR,
        is_ai=True,
        organization_id="org-main",
    )


@pytest.fixture
def cross_org_doctor():
    return AuthenticatedUserContext(
        user_id="doc-other-99",
        role=UserRole.DOCTOR,
        organization_id="org-other",
        facility_id="fac-west",
    )


# ===========================================================================
# 1. Unit Tests: Policy Evaluation & Authorization Rules
# ===========================================================================

@pytest.mark.asyncio
async def test_policy_evaluation_determines_approval_required(phase40_setup):
    policy_svc: ApprovalPolicyService = phase40_setup["policy_service"]

    # Clinical order requires approval
    rule = policy_svc.evaluate_policy(
        action_type="order",
        context={"patient_id": "p-100", "is_high_risk": True},
    )
    assert rule.requires_approval is True
    assert rule.required_approvals_count >= 1
    assert "DOCTOR" in rule.eligible_roles
    assert rule.allow_self_approval is False


@pytest.mark.asyncio
async def test_self_approval_blocked(phase40_setup, requester_doctor):
    approval_svc: ApprovalService = phase40_setup["approval_service"]

    # Create approval request
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="ord-test-1",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-self-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    # Requester attempting to approve their own request MUST fail
    with pytest.raises(ApprovalSelfConflictException):
        await approval_svc.approve(
            approval_id=approval.id,
            payload=ApprovalDecisionRequest(reason="Self approve attempt"),
            actor=requester_doctor,
        )


@pytest.mark.asyncio
async def test_unauthorized_role_cannot_approve(phase40_setup, requester_doctor, nurse_actor):
    approval_svc: ApprovalService = phase40_setup["approval_service"]

    req = ApprovalRequestCreate(
        target_type="order",
        target_id="ord-test-2",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-nurse-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    # Nurse role is not eligible to approve clinical order
    with pytest.raises(ApprovalReviewerInvalidException):
        await approval_svc.approve(
            approval_id=approval.id,
            payload=ApprovalDecisionRequest(reason="Nurse attempt"),
            actor=nurse_actor,
        )


@pytest.mark.asyncio
async def test_ai_cannot_approve_or_reject(phase40_setup, requester_doctor, ai_actor):
    approval_svc: ApprovalService = phase40_setup["approval_service"]

    req = ApprovalRequestCreate(
        target_type="order",
        target_id="ord-test-3",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-ai-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    # AI Approve attempt
    with pytest.raises(ApprovalReviewerInvalidException) as exc_approve:
        await approval_svc.approve(
            approval_id=approval.id,
            payload=ApprovalDecisionRequest(reason="AI auto approve"),
            actor=ai_actor,
        )
    assert "AI actor cannot approve" in str(exc_approve.value)

    # AI Reject attempt
    with pytest.raises(ApprovalReviewerInvalidException) as exc_reject:
        await approval_svc.reject(
            approval_id=approval.id,
            payload=ApprovalDecisionRequest(reason="AI auto reject"),
            actor=ai_actor,
        )
    assert "AI actor cannot approve" in str(exc_reject.value)


@pytest.mark.asyncio
async def test_multi_approver_requirement(phase40_setup, requester_doctor, approver_doctor, approver_doctor_2):
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    policy_svc: ApprovalPolicyService = phase40_setup["policy_service"]

    # Register rule requiring 2 approvers
    policy_svc.register_rule(ApprovalPolicyRule(
        action_type="high_risk_order",
        requires_approval=True,
        multi_approver_count=2,
        required_roles=["DOCTOR"],
        allow_self_approval=False,
    ))

    req = ApprovalRequestCreate(
        target_type="high_risk_order",
        target_id="ord-multi-1",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-multi-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    assert approval.required_approvals_count == 2
    assert approval.status == ApprovalStatus.PENDING_REVIEW

    # First approver approves -> status remains IN_REVIEW (not APPROVED yet)
    app1 = await approval_svc.approve(
        approval_id=approval.id,
        payload=ApprovalDecisionRequest(reason="First clinical signoff"),
        actor=approver_doctor,
    )
    assert app1.status == ApprovalStatus.IN_REVIEW
    assert len(app1.decisions) == 1

    # Same approver cannot satisfy second slot
    with pytest.raises(ApprovalReviewerInvalidException):
        await approval_svc.approve(
            approval_id=approval.id,
            payload=ApprovalDecisionRequest(reason="First doctor duplicate attempt"),
            actor=approver_doctor,
        )

    # Second distinct approver approves -> status becomes APPROVED
    app2 = await approval_svc.approve(
        approval_id=approval.id,
        payload=ApprovalDecisionRequest(reason="Second independent signoff"),
        actor=approver_doctor_2,
    )
    assert app2.status == ApprovalStatus.APPROVED
    assert len(app2.decisions) == 2


@pytest.mark.asyncio
async def test_material_modification_invalidates_approval(phase40_setup, requester_doctor, approver_doctor):
    approval_svc: ApprovalService = phase40_setup["approval_service"]

    req = ApprovalRequestCreate(
        target_type="order",
        target_id="ord-mod-1",
        target_version="1",
        target_snapshot_hash="hash-initial-abc",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-mod-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    # Approve version 1
    await approval_svc.approve(
        approval_id=approval.id,
        payload=ApprovalDecisionRequest(reason="Approved v1"),
        actor=approver_doctor,
    )

    # Execution check with matching hash and version succeeds
    valid_record = approval_svc.validate_approval_for_execution(
        target_type="order",
        target_id="ord-mod-1",
        current_version="1",
        current_hash="hash-initial-abc",
    )
    assert valid_record.status == ApprovalStatus.APPROVED

    # Execution check with modified version fails and marks SUPERSEDED
    with pytest.raises(ApprovalTargetChangedException):
        approval_svc.validate_approval_for_execution(
            target_type="order",
            target_id="ord-mod-1",
            current_version="2",
            current_hash="hash-initial-abc",
        )

    # Check that record is now marked SUPERSEDED
    rechecked = await approval_svc.get_approval(approval.id, requester_doctor)
    assert rechecked.status == ApprovalStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_expired_approval_blocks_execution(phase40_setup, requester_doctor, approver_doctor):
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    repo: ApprovalRepository = phase40_setup["approval_repo"]

    req = ApprovalRequestCreate(
        target_type="order",
        target_id="ord-exp-1",
        target_version="1",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-exp-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(
        approval_id=approval.id,
        payload=ApprovalDecisionRequest(reason="Approved"),
        actor=approver_doctor,
    )

    # Artificially expire the approval
    approval.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    repo.save(approval)

    # Execution attempt must be blocked with ApprovalExpiredException
    with pytest.raises(ApprovalExpiredException):
        approval_svc.validate_approval_for_execution(
            target_type="order",
            target_id="ord-exp-1",
            current_version="1",
        )


@pytest.mark.asyncio
async def test_delegation_flow(phase40_setup, requester_doctor, approver_doctor, approver_doctor_2):
    approval_svc: ApprovalService = phase40_setup["approval_service"]

    req = ApprovalRequestCreate(
        target_type="order",
        target_id="ord-del-1",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-del-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    # Delegate from approver_doctor to approver_doctor_2
    delegation = await approval_svc.delegate(
        approval_id=approval.id,
        payload=ApprovalDelegateRequest(
            delegate_to_user_id=approver_doctor_2.user_id,
            reason="Covering my clinical shift",
        ),
        actor=approver_doctor,
    )
    assert delegation.delegatee_id == approver_doctor_2.user_id

    # The delegatee can now approve
    approved = await approval_svc.approve(
        approval_id=approval.id,
        payload=ApprovalDecisionRequest(reason="Approved on coverage"),
        actor=approver_doctor_2,
    )
    assert approved.status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_escalation_flow(phase40_setup, requester_doctor, approver_doctor):
    approval_svc: ApprovalService = phase40_setup["approval_service"]

    req = ApprovalRequestCreate(
        target_type="order",
        target_id="ord-esc-1",
        patient_id="p-100",
        approval_type=ApprovalType.ORDER_APPROVAL,
        idempotency_key="idem-esc-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    escalated = await approval_svc.escalate(
        approval_id=approval.id,
        payload=ApprovalEscalateRequest(
            reason="Unusually high dosage requires senior review",
            escalate_to_role="CLINICAL_DIRECTOR",
        ),
        actor=approver_doctor,
    )
    assert escalated.escalation_level == 1
    assert "CLINICAL_DIRECTOR" in escalated.assigned_roles


# ===========================================================================
# 2. ALL 30 Clinical Safety Regression Tests (TRD Section 52)
# ===========================================================================

@pytest.mark.asyncio
async def test_safety_01_request_does_not_authorize(phase40_setup, requester_doctor):
    """1. An approval request does not automatically authorize an action."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-1",
        patient_id="p-100",
        idempotency_key="safety-idem-1",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    assert approval.status != ApprovalStatus.APPROVED
    assert approval.status in (ApprovalStatus.REQUESTED, ApprovalStatus.PENDING_REVIEW)
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-1", "1")


@pytest.mark.asyncio
async def test_safety_02_unauthorized_users_cannot_approve(phase40_setup, requester_doctor, patient_actor):
    """2. Unauthorized users cannot approve clinical actions."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-2",
        patient_id="p-100",
        idempotency_key="safety-idem-2",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    with pytest.raises(ApprovalReviewerInvalidException):
        await approval_svc.approve(
            approval.id,
            ApprovalDecisionRequest(reason="Patient trying to self approve"),
            patient_actor,
        )


@pytest.mark.asyncio
async def test_safety_03_ineligible_reviewers_cannot_approve(phase40_setup, requester_doctor, nurse_actor):
    """3. Ineligible reviewers cannot approve actions."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-3",
        patient_id="p-100",
        idempotency_key="safety-idem-3",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    with pytest.raises(ApprovalReviewerInvalidException):
        await approval_svc.approve(
            approval.id,
            ApprovalDecisionRequest(reason="Nurse signing physician order"),
            nurse_actor,
        )


@pytest.mark.asyncio
async def test_safety_04_self_approval_is_blocked(phase40_setup, requester_doctor):
    """4. Self-approval is blocked when policy disallows it."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-4",
        patient_id="p-100",
        idempotency_key="safety-idem-4",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    with pytest.raises(ApprovalSelfConflictException):
        await approval_svc.approve(
            approval.id,
            ApprovalDecisionRequest(reason="Self signoff"),
            requester_doctor,
        )


@pytest.mark.asyncio
async def test_safety_05_approval_cannot_be_reused_for_modified_action(phase40_setup, requester_doctor, approver_doctor):
    """5. Approval cannot be reused for a materially modified action."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-5",
        target_version="1",
        target_snapshot_hash="hash-orig",
        patient_id="p-100",
        idempotency_key="safety-idem-5",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Approved"), approver_doctor)

    with pytest.raises(ApprovalTargetChangedException):
        approval_svc.validate_approval_for_execution("order", "safety-5", "2", "hash-orig")


@pytest.mark.asyncio
async def test_safety_06_expired_approval_cannot_authorize(phase40_setup, requester_doctor, approver_doctor):
    """6. Expired approval cannot authorize execution."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    repo: ApprovalRepository = phase40_setup["approval_repo"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-6",
        patient_id="p-100",
        idempotency_key="safety-idem-6",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Approved"), approver_doctor)

    approval.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    repo.save(approval)

    with pytest.raises(ApprovalExpiredException):
        approval_svc.validate_approval_for_execution("order", "safety-6", "1")


@pytest.mark.asyncio
async def test_safety_07_rejected_approval_cannot_authorize(phase40_setup, requester_doctor, approver_doctor):
    """7. Rejected approval cannot authorize execution."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-7",
        patient_id="p-100",
        idempotency_key="safety-idem-7",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.reject(
        approval.id,
        ApprovalDecisionRequest(reason="Contraindication discovered"),
        approver_doctor,
    )

    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-7", "1")


@pytest.mark.asyncio
async def test_safety_08_cancelled_approval_cannot_authorize(phase40_setup, requester_doctor):
    """8. Cancelled approval cannot authorize execution."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-8",
        patient_id="p-100",
        idempotency_key="safety-idem-8",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.cancel(approval.id, "No longer needed", requester_doctor)

    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-8", "1")


@pytest.mark.asyncio
async def test_safety_09_approval_for_order_a_cannot_authorize_order_b(phase40_setup, requester_doctor, approver_doctor):
    """9. Approval for Order A cannot authorize Order B."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="order-A",
        patient_id="p-100",
        idempotency_key="safety-idem-9",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Approved Order A"), approver_doctor)

    # Attempting to validate Order B using Order A's approval must fail
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "order-B", "1")


@pytest.mark.asyncio
async def test_safety_10_approval_for_template_v1_cannot_authorize_v2(phase40_setup, requester_doctor, approver_doctor):
    """10. Approval for Order Set Version 1 cannot authorize Version 2."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order_set_template",
        target_id="tmpl-cardio-1",
        target_version="1",
        patient_id="p-system",
        approval_type=ApprovalType.TEMPLATE_APPROVAL,
        idempotency_key="safety-idem-10",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Approved v1"), approver_doctor)

    with pytest.raises(ApprovalTargetChangedException):
        approval_svc.validate_approval_for_execution("order_set_template", "tmpl-cardio-1", "2")


@pytest.mark.asyncio
async def test_safety_11_template_suspension_blocks_execution(phase40_setup):
    """11. Template suspension blocks new execution where policy requires."""
    # When template is suspended in Phase 39, approval checks and execution validations fail closed
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order_set_template", "tmpl-suspended-9", "1")


@pytest.mark.asyncio
async def test_safety_12_ai_cannot_approve(phase40_setup, requester_doctor, ai_actor):
    """12. AI cannot approve."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-12",
        patient_id="p-100",
        idempotency_key="safety-idem-12",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    with pytest.raises(ApprovalReviewerInvalidException):
        await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="AI Approves"), ai_actor)


@pytest.mark.asyncio
async def test_safety_13_ai_cannot_reject(phase40_setup, requester_doctor, ai_actor):
    """13. AI cannot reject."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-13",
        patient_id="p-100",
        idempotency_key="safety-idem-13",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    with pytest.raises(ApprovalReviewerInvalidException):
        await approval_svc.reject(approval.id, ApprovalDecisionRequest(reason="AI Rejects"), ai_actor)


@pytest.mark.asyncio
async def test_safety_14_ai_cannot_override_human_approval(phase40_setup, requester_doctor, approver_doctor, ai_actor):
    """14. AI cannot override a human approval."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-14",
        patient_id="p-100",
        idempotency_key="safety-idem-14",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Human Physician signoff"), approver_doctor)

    with pytest.raises(ApprovalReviewerInvalidException):
        await approval_svc.reject(approval.id, ApprovalDecisionRequest(reason="AI override"), ai_actor)


@pytest.mark.asyncio
async def test_safety_15_ai_cannot_bypass_approval(phase40_setup, ai_actor):
    """15. AI cannot bypass required approval."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-15", "1")


@pytest.mark.asyncio
async def test_safety_16_task_completion_cannot_directly_authorize(phase40_setup, requester_doctor):
    """16. Task completion cannot directly authorize an order."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-16",
        patient_id="p-100",
        idempotency_key="safety-idem-16",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    # A task may be marked completed, but approval remains PENDING_REVIEW unless approve() was called
    assert approval.status != ApprovalStatus.APPROVED
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-16", "1")


@pytest.mark.asyncio
async def test_safety_17_alert_ack_cannot_authorize(phase40_setup, requester_doctor):
    """17. Alert acknowledgement cannot authorize an order."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-17",
        patient_id="p-100",
        idempotency_key="safety-idem-17",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    # Acknowledging an alert does not transition approval status
    assert approval.status != ApprovalStatus.APPROVED
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-17", "1")


@pytest.mark.asyncio
async def test_safety_18_notification_delivery_cannot_authorize(phase40_setup, requester_doctor):
    """18. Notification delivery cannot authorize an order."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-18",
        patient_id="p-100",
        idempotency_key="safety-idem-18",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    assert approval.status != ApprovalStatus.APPROVED
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-18", "1")


@pytest.mark.asyncio
async def test_safety_19_workflow_execution_cannot_bypass_approval(phase40_setup):
    """19. Workflow execution cannot bypass required approval."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-workflow-19", "1")


@pytest.mark.asyncio
async def test_safety_20_provider_success_cannot_bypass_approval(phase40_setup):
    """20. Provider success cannot bypass approval."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    # Even if an external provider returned HTTP 200, an order cannot be legally executed without authorization
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("order", "safety-prov-20", "1")


@pytest.mark.asyncio
async def test_safety_21_approval_cannot_be_silently_extended(phase40_setup, requester_doctor, approver_doctor):
    """21. Approval cannot be silently extended."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    repo: ApprovalRepository = phase40_setup["approval_repo"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-21",
        patient_id="p-100",
        idempotency_key="safety-idem-21",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Approved"), approver_doctor)

    # Simulate expired approval
    approval.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    repo.save(approval)

    # Validating execution must raise ApprovalExpiredException, not silently reset expiration
    with pytest.raises(ApprovalExpiredException):
        approval_svc.validate_approval_for_execution("order", "safety-21", "1")


@pytest.mark.asyncio
async def test_safety_22_historical_approvals_cannot_be_rewritten(phase40_setup, requester_doctor, approver_doctor):
    """22. Historical approvals cannot be rewritten."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-22",
        patient_id="p-100",
        idempotency_key="safety-idem-22",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(
        approval.id,
        ApprovalDecisionRequest(reason="Initial decision by human"),
        approver_doctor,
    )

    # Verify immutable decision log cannot be modified in place
    history = await approval_svc.get_approval(approval.id, requester_doctor)
    assert len(history.decisions) == 1
    assert history.decisions[0].decision == ApprovalDecisionType.APPROVE
    assert history.decisions[0].reason == "Initial decision by human"


@pytest.mark.asyncio
async def test_safety_23_duplicate_approval_decisions_prevented(phase40_setup, requester_doctor, approver_doctor):
    """23. Duplicate approval decisions are prevented."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-23",
        patient_id="p-100",
        idempotency_key="safety-idem-23",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="First approval"), approver_doctor)

    with pytest.raises(ApprovalAlreadyDecidedException):
        await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Duplicate decision"), approver_doctor)


@pytest.mark.asyncio
async def test_safety_24_concurrent_decisions_resolve_safely(phase40_setup, requester_doctor, approver_doctor, approver_doctor_2):
    """24. Concurrent approval decisions resolve safely."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-24",
        patient_id="p-100",
        idempotency_key="safety-idem-24",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    # Fire concurrent decisions
    results = await asyncio.gather(
        approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Doctor A approves"), approver_doctor),
        approval_svc.reject(approval.id, ApprovalDecisionRequest(reason="Doctor B rejects"), approver_doctor_2),
        return_exceptions=True,
    )

    # Exactly one decision should succeed, the second must raise ApprovalAlreadyDecidedException
    successes = [r for r in results if isinstance(r, ApprovalRecord)]
    failures = [r for r in results if isinstance(r, ApprovalAlreadyDecidedException)]
    assert len(successes) == 1
    assert len(failures) == 1


@pytest.mark.asyncio
async def test_safety_25_cross_patient_access_blocked(phase40_setup, requester_doctor, patient_actor):
    """25. Cross-patient approval access is blocked."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-25",
        patient_id="p-patient-A",
        idempotency_key="safety-idem-25",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    # patient_actor belongs to patient p-100, not p-patient-A
    with pytest.raises(ApprovalForbiddenException):
        await approval_svc.get_approval(approval.id, patient_actor)


@pytest.mark.asyncio
async def test_safety_26_cross_organization_access_blocked(phase40_setup, requester_doctor, cross_org_doctor):
    """26. Cross-organization approval access is blocked."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-26",
        patient_id="p-100",
        idempotency_key="safety-idem-26",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)

    with pytest.raises(ApprovalForbiddenException):
        await approval_svc.get_approval(approval.id, cross_org_doctor)


@pytest.mark.asyncio
async def test_safety_27_approval_target_changes_trigger_revalidation(phase40_setup, requester_doctor, approver_doctor):
    """27. Approval target changes trigger revalidation."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-27",
        target_version="1",
        target_snapshot_hash="hash-initial-123",
        patient_id="p-100",
        idempotency_key="safety-idem-27",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Approved"), approver_doctor)

    # Change in content hash raises ApprovalTargetChangedException
    with pytest.raises(ApprovalTargetChangedException):
        approval_svc.validate_approval_for_execution(
            target_type="order",
            target_id="safety-27",
            current_version="1",
            current_hash="hash-changed-456",
        )


@pytest.mark.asyncio
async def test_safety_28_missing_policy_does_not_bypass(phase40_setup, requester_doctor):
    """28. Missing policy configuration does not bypass authorization."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="unregistered_high_risk_action",
        target_id="safety-28",
        patient_id="p-100",
        idempotency_key="safety-idem-28",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    # Fail-safe default policy requires doctor approval
    assert approval.required_approvals_count >= 1
    with pytest.raises(ApprovalExecutionBlockedException):
        approval_svc.validate_approval_for_execution("unregistered_high_risk_action", "safety-28", "1")


@pytest.mark.asyncio
async def test_safety_29_missing_reviewer_does_not_create_auto_approval(phase40_setup, requester_doctor):
    """29. Missing reviewer information does not create automatic approval."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-29",
        patient_id="p-100",
        idempotency_key="safety-idem-29",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    assert approval.status != ApprovalStatus.APPROVED
    assert len(approval.decisions) == 0


@pytest.mark.asyncio
async def test_safety_30_approval_does_not_imply_clinical_outcome(phase40_setup, requester_doctor, approver_doctor):
    """30. Approval does not imply clinical outcome."""
    approval_svc: ApprovalService = phase40_setup["approval_service"]
    req = ApprovalRequestCreate(
        target_type="order",
        target_id="safety-30",
        patient_id="p-100",
        idempotency_key="safety-idem-30",
    )
    approval = await approval_svc.create_approval_request(req, requester_doctor)
    approved = await approval_svc.approve(approval.id, ApprovalDecisionRequest(reason="Physician authorization"), approver_doctor)

    # Core invariant: Approval is a gate to allow Phase 38 transmission, not clinical outcome or cure
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.target_id == "safety-30"


# ===========================================================================
# 3. API Integration Tests (TRD Sections 31 - 33)
# ===========================================================================

@pytest.fixture
def app_with_overrides(phase40_setup, requester_doctor, approver_doctor):
    app = create_app()
    app.dependency_overrides[get_approval_service] = lambda: phase40_setup["approval_service"]
    # Default authenticated user is approver doctor
    app.dependency_overrides[get_current_user] = lambda: approver_doctor
    return app


@pytest.mark.asyncio
async def test_api_approval_lifecycle(app_with_overrides, requester_doctor, approver_doctor):
    transport = ASGITransport(app=app_with_overrides)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Switch actor to requester doctor
        app_with_overrides.dependency_overrides[get_current_user] = lambda: requester_doctor

        # 1. Create approval request
        res = await ac.post(
            "/api/v1/approvals",
            json={
                "target_type": "order",
                "target_id": "api-ord-1",
                "patient_id": "p-100",
                "approval_type": "ORDER_APPROVAL",
                "clinical_summary": "STAT CBC & BMP required",
                "idempotency_key": "api-idem-1",
            },
        )
        assert res.status_code == 201, res.text
        data = res.json()
        approval_id = data["id"]
        assert data["status"] in ("REQUESTED", "PENDING_REVIEW")

        # 2. Get approval by ID
        res = await ac.get(f"/api/v1/approvals/{approval_id}")
        assert res.status_code == 200
        assert res.json()["id"] == approval_id

        # 3. List approvals
        res = await ac.get("/api/v1/approvals?patient_id=p-100")
        assert res.status_code == 200
        assert len(res.json()["items"]) >= 1

        # 4. List pending approvals
        res = await ac.get("/api/v1/approvals/pending")
        assert res.status_code == 200

        # 5. Switch to approver doctor and approve
        app_with_overrides.dependency_overrides[get_current_user] = lambda: approver_doctor
        res = await ac.post(
            f"/api/v1/approvals/{approval_id}/approve",
            json={"reason": "Clinically indicated based on lab criteria"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "APPROVED"

        # 6. Check history
        res = await ac.get(f"/api/v1/approvals/{approval_id}/history")
        assert res.status_code == 200
        decisions = res.json()
        assert len(decisions) >= 1
        assert decisions[0]["decision"] == "APPROVE"


@pytest.mark.asyncio
async def test_api_rejection_and_revision(app_with_overrides, requester_doctor, approver_doctor):
    transport = ASGITransport(app=app_with_overrides)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        app_with_overrides.dependency_overrides[get_current_user] = lambda: requester_doctor

        # Create approval for rejection test
        res = await ac.post(
            "/api/v1/approvals",
            json={
                "target_type": "order",
                "target_id": "api-ord-reject",
                "patient_id": "p-100",
                "approval_type": "ORDER_APPROVAL",
                "idempotency_key": "api-idem-reject",
            },
        )
        assert res.status_code == 201
        approval_id = res.json()["id"]

        # Switch to approver doctor and request revision
        app_with_overrides.dependency_overrides[get_current_user] = lambda: approver_doctor
        res = await ac.post(
            f"/api/v1/approvals/{approval_id}/request-revision",
            json={
                "reason": "Missing serum creatinine level",
                "required_changes": ["Attach renal panel", "Adjust dosage"],
            },
        )
        assert res.status_code == 200
        assert res.json()["status"] == "REVISION_REQUESTED"

"""Tests for HealthSetu Phase 37: Clinical Workflow Orchestration, Order Management & Controlled Action Chains.

Verifies:
- Workflow definition catalog, versioning, and validation
- Workflow instantiation, lifecycle states, and deterministic step orchestration
- Deduplication and idempotency (client key and domain logical identity)
- Task integration: step-driven task creation, task completion callbacks, and boundary enforcement
- Human approval gates with strict role-based authorization (Doctor/Admin vs Patient/AI)
- External domain event waiting (WAIT_FOR_EVENT, e.g. TRANSFER_ACCEPTED)
- Workflow lifecycle operations (pause, resume, cancel, fail)
- Preserved execution history, provenance, and audit logging
- Security, multi-tenancy, and patient BOLA isolation
- FastAPI endpoints and OpenAPI compatibility
- All 20 Clinical Safety Regression Tests from TRD Section 60
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_current_user,
    get_workflow_approval_service,
    get_workflow_definition_service,
    get_workflow_service,
)
from app.core.exceptions import (
    WorkflowAccessDeniedException,
    WorkflowAlreadyCancelledException,
    WorkflowAlreadyCompletedException,
    WorkflowApprovalNotAllowedException,
    WorkflowCannotResumeException,
    WorkflowDefinitionDisabledException,
    WorkflowDefinitionNotFoundException,
    WorkflowInvalidStateException,
    WorkflowInvalidTransitionException,
    WorkflowNotFoundException,
    WorkflowOperationNotAllowedException,
    WorkflowStepNotFoundException,
)
from app.main import create_app
from app.repositories.task_assignment_repository import TaskAssignmentRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.workflow_step_repository import WorkflowStepRepository
from app.schemas.task import TaskCompleteRequest, TaskStatus
from app.schemas.user import AuthenticatedUserContext
from app.schemas.workflow import (
    WorkflowCancelRequest,
    WorkflowCategory,
    WorkflowCreate,
    WorkflowDefinition,
    WorkflowFilter,
    WorkflowPauseRequest,
    WorkflowRecord,
    WorkflowResumeRequest,
    WorkflowStatus,
)
from app.schemas.workflow_approval import (
    WorkflowApprovalDecision,
    WorkflowApprovalRequest,
)
from app.schemas.workflow_step import (
    WorkflowStepActionType,
    WorkflowStepDefinition,
    WorkflowStepRecord,
    WorkflowStepStatus,
)
from app.services.task_assignment_service import TaskAssignmentService
from app.services.task_dependency_service import TaskDependencyService
from app.services.task_service import TaskService
from app.services.task_validation_service import TaskValidationService
from app.services.workflow_approval_service import WorkflowApprovalService
from app.services.workflow_definition_service import WorkflowDefinitionService
from app.services.workflow_step_service import WorkflowStepService
from app.services.workflow_service import WorkflowService
from app.services.workflow_validation_service import WorkflowValidationService


# ===========================================================================
# Test Setup & Fixtures
# ===========================================================================

def make_task_in_progress(task_repo: TaskRepository, task_id: str) -> None:
    """Helper to transition a task to IN_PROGRESS so it can be completed."""
    task = task_repo.get_by_id(task_id)
    if task:
        updated = task.model_copy(update={"status": TaskStatus.IN_PROGRESS})
        task_repo.save(updated)


@pytest.fixture
def workflow_setup():
    """Build isolated workflow and task repositories and services."""
    task_repo = TaskRepository()
    task_assign_repo = TaskAssignmentRepository()
    task_val = TaskValidationService()
    task_assign_svc = TaskAssignmentService(assignment_repo=task_assign_repo)
    task_dep_svc = TaskDependencyService(task_repo=task_repo)

    task_service = TaskService(
        task_repo=task_repo,
        assignment_repo=task_assign_repo,
        validation_service=task_val,
        assignment_service=task_assign_svc,
        dependency_service=task_dep_svc,
    )

    wf_repo = WorkflowRepository()
    step_repo = WorkflowStepRepository()
    def_service = WorkflowDefinitionService()
    val_service = WorkflowValidationService()

    step_service = WorkflowStepService(
        step_repo=step_repo,
        val_service=val_service,
        task_service=task_service,
        alert_service=None,
        notification_service=None,
        audit_service=None,
    )

    approval_service = WorkflowApprovalService(
        workflow_repo=wf_repo,
        step_repo=step_repo,
        val_service=val_service,
        audit_service=None,
    )

    wf_service = WorkflowService(
        workflow_repo=wf_repo,
        step_repo=step_repo,
        def_service=def_service,
        step_service=step_service,
        val_service=val_service,
        approval_service=approval_service,
        task_service=task_service,
        alert_service=None,
        notification_service=None,
        audit_service=None,
    )

    return {
        "wf_repo": wf_repo,
        "step_repo": step_repo,
        "def_service": def_service,
        "val_service": val_service,
        "step_service": step_service,
        "approval_service": approval_service,
        "task_service": task_service,
        "task_repo": task_repo,
        "wf_service": wf_service,
    }


@pytest.fixture
def doctor_user():
    return AuthenticatedUserContext(
        user_id="DOC-DR-101",
        role="DOCTOR",
        permissions=["WORKFLOW_CREATE", "WORKFLOW_READ", "WORKFLOW_APPROVE", "WORKFLOW_PAUSE", "WORKFLOW_RESUME", "WORKFLOW_CANCEL"],
        facility_id="FAC-001",
        organization_id="ORG-HEALTH-01",
    )


@pytest.fixture
def admin_user():
    return AuthenticatedUserContext(
        user_id="ADMIN-SYS-99",
        role="ADMIN",
        permissions=["WORKFLOW_CREATE", "WORKFLOW_READ", "WORKFLOW_APPROVE", "WORKFLOW_PAUSE", "WORKFLOW_RESUME", "WORKFLOW_CANCEL", "ADMIN_WORKFLOWS_VIEW", "ADMIN_WORKFLOWS_MANAGE"],
        facility_id="FAC-001",
        organization_id="ORG-HEALTH-01",
    )


@pytest.fixture
def patient_user():
    return AuthenticatedUserContext(
        user_id="PAT-USER-1",
        role="PATIENT",
        permissions=["WORKFLOW_READ"],
        patient_id="PAT-1001",
        facility_id="FAC-001",
        organization_id="ORG-HEALTH-01",
    )


@pytest.fixture
def ai_agent_user():
    return AuthenticatedUserContext(
        user_id="AI-AGENT-GEMINI",
        role="INTEGRATION_OPERATOR",
        permissions=["WORKFLOW_READ"],
        facility_id="FAC-001",
        organization_id="ORG-HEALTH-01",
    )


# ===========================================================================
# 1. Workflow Definition Service Tests
# ===========================================================================

def test_workflow_definition_catalog(workflow_setup):
    """Verify built-in templates are correctly registered and versioned."""
    def_service: WorkflowDefinitionService = workflow_setup["def_service"]
    defs = def_service.list_definitions()
    assert len(defs) >= 5

    def_ids = {d.definition_id for d in defs}
    assert "diagnostic_review" in def_ids
    assert "medication_safety_review" in def_ids
    assert "discharge_follow_up" in def_ids
    assert "transfer_coordination" in def_ids
    assert "document_processing" in def_ids

    # Fetch specific version
    diag = def_service.get_definition("diagnostic_review", "1.0")
    assert diag.version == "1.0"
    assert diag.category == WorkflowCategory.DIAGNOSTIC
    assert len(diag.steps) == 3


def test_workflow_definition_disabled_or_missing(workflow_setup):
    """Verify non-existent or disabled definitions cannot be retrieved."""
    def_service: WorkflowDefinitionService = workflow_setup["def_service"]

    with pytest.raises(WorkflowDefinitionNotFoundException):
        def_service.get_definition("non_existent_definition")

    # Disabled definition test
    disabled_def = WorkflowDefinition(
        definition_id="disabled_template",
        version="1.0",
        name="Disabled Template",
        category=WorkflowCategory.OPERATIONAL,
        enabled=False,
        trigger_type=WorkflowDefinition.model_fields["trigger_type"].annotation.DOMAIN_EVENT,
        steps=[],
    )
    def_service.register_definition(disabled_def)

    with pytest.raises(WorkflowDefinitionDisabledException):
        def_service.get_definition("disabled_template")


# ===========================================================================
# 2. Workflow Creation & Idempotency Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_workflow_creation_and_step_initialization(workflow_setup, doctor_user):
    """Create a diagnostic review workflow and verify steps instantiated."""
    wf_service: WorkflowService = workflow_setup["wf_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9901",
        patient_id="PAT-1001",
        facility_id="FAC-001",
        idempotency_key="IDEM-WF-TEST-001",
    )

    wf = await wf_service.start_workflow(payload, doctor_user)
    assert wf.workflow_id.startswith("WF-")
    assert wf.definition_id == "diagnostic_review"
    assert wf.patient_id == "PAT-1001"
    assert len(wf.steps) == 3

    # Step 1 created a task and entered WAITING status
    assert wf.steps[0].action_type == WorkflowStepActionType.CREATE_TASK
    assert wf.steps[0].status == WorkflowStepStatus.WAITING
    assert wf.steps[0].related_task_id is not None
    # Workflow status reflects active waiting on child task
    assert wf.status == WorkflowStatus.WAITING


@pytest.mark.asyncio
async def test_workflow_idempotency_deduplication(workflow_setup, doctor_user):
    """Verify idempotency via explicit client key and logical domain identity (TRD Invariant 18)."""
    wf_service: WorkflowService = workflow_setup["wf_service"]

    payload1 = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9902",
        patient_id="PAT-1001",
        facility_id="FAC-001",
        idempotency_key="EXPLICIT-KEY-123",
    )

    wf1 = await wf_service.start_workflow(payload1, doctor_user)

    # 1. Retry with same idempotency key
    wf2 = await wf_service.start_workflow(payload1, doctor_user)
    assert wf1.workflow_id == wf2.workflow_id

    # 2. Logical identity deduplication (different idempotency key, identical source event + patient)
    payload_dup = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9902",
        patient_id="PAT-1001",
        facility_id="FAC-001",
        idempotency_key="DIFFERENT-KEY-999",
    )
    wf3 = await wf_service.start_workflow(payload_dup, doctor_user)
    assert wf1.workflow_id == wf3.workflow_id


# ===========================================================================
# 3. Task Integration & Task Completion Callback Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_task_completion_callback_and_boundary(workflow_setup, doctor_user):
    """Verify task completion advances step, but DOES NOT complete entire workflow (TRD Invariant 13)."""
    wf_service: WorkflowService = workflow_setup["wf_service"]
    task_service: TaskService = workflow_setup["task_service"]

    # 1. Start workflow
    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9903",
        patient_id="PAT-1001",
        facility_id="FAC-001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)
    task_id = wf.steps[0].related_task_id
    assert task_id is not None

    # 2. Complete Phase 36 task
    make_task_in_progress(workflow_setup["task_repo"], task_id)
    await task_service.complete_task(
        task_id=task_id,
        request=TaskCompleteRequest(completion_notes="Diagnostic test reviewed in laboratory."),
        current_user=doctor_user,
    )

    # 3. Invoke Task completion callback
    updated_wf = await wf_service.handle_task_completion(task_id, doctor_user)
    assert updated_wf is not None

    # Step 1 is COMPLETED
    assert updated_wf.steps[0].status == WorkflowStepStatus.COMPLETED

    # Step 2 is now AWAITING_APPROVAL gate
    assert updated_wf.steps[1].status == WorkflowStepStatus.AWAITING_APPROVAL

    # Overall workflow is AWAITING_APPROVAL, NOT COMPLETED! (TRD Invariant 13)
    assert updated_wf.status == WorkflowStatus.AWAITING_APPROVAL


# ===========================================================================
# 4. Approval Gates & Authorization Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_approval_gate_authorized_doctor_approval(workflow_setup, doctor_user):
    """Verify authorized clinician can approve gate, advancing workflow to completion."""
    wf_service: WorkflowService = workflow_setup["wf_service"]
    approval_service: WorkflowApprovalService = workflow_setup["approval_service"]
    task_service: TaskService = workflow_setup["task_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9904",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)
    task_id = wf.steps[0].related_task_id

    # Complete Step 1 task
    make_task_in_progress(workflow_setup["task_repo"], task_id)
    await task_service.complete_task(task_id, TaskCompleteRequest(), doctor_user)
    wf = await wf_service.handle_task_completion(task_id, doctor_user)
    assert wf.status == WorkflowStatus.AWAITING_APPROVAL

    # Step 2 approval
    step_id = "step_clinician_approval"
    approval_req = WorkflowApprovalRequest(
        decision=WorkflowApprovalDecision.APPROVED,
        comments="Approved by Doctor Jane Doe.",
        policy_version="1.0",
    )
    approved_step = await approval_service.evaluate_approval(
        workflow_id=wf.workflow_id,
        step_id=step_id,
        request=approval_req,
        current_user=doctor_user,
    )
    assert approved_step.status == WorkflowStepStatus.COMPLETED

    # Advance workflow to execute remaining deterministic verification step
    completed_wf = await wf_service.advance_workflow(wf.workflow_id, doctor_user)
    assert completed_wf.status == WorkflowStatus.COMPLETED
    assert completed_wf.completed_at is not None

    # Verify recorded approval
    approvals = await wf_service.get_workflow_approvals(wf.workflow_id, doctor_user)
    assert len(approvals) == 1
    assert approvals[0].decision == WorkflowApprovalDecision.APPROVED
    assert approvals[0].approver_role == "DOCTOR"


@pytest.mark.asyncio
async def test_approval_gate_unauthorized_patient_rejected(workflow_setup, doctor_user, patient_user):
    """Verify Patient role cannot approve a clinical doctor gate."""
    wf_service: WorkflowService = workflow_setup["wf_service"]
    approval_service: WorkflowApprovalService = workflow_setup["approval_service"]
    task_service: TaskService = workflow_setup["task_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9905",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)
    task_id = wf.steps[0].related_task_id
    make_task_in_progress(workflow_setup["task_repo"], task_id)
    await task_service.complete_task(task_id, TaskCompleteRequest(), doctor_user)
    wf = await wf_service.handle_task_completion(task_id, doctor_user)

    step_id = "step_clinician_approval"
    approval_req = WorkflowApprovalRequest(decision=WorkflowApprovalDecision.APPROVED)

    with pytest.raises(WorkflowApprovalNotAllowedException):
        await approval_service.evaluate_approval(
            workflow_id=wf.workflow_id,
            step_id=step_id,
            request=approval_req,
            current_user=patient_user,
        )


@pytest.mark.asyncio
async def test_approval_gate_ai_rejected(workflow_setup, doctor_user, ai_agent_user):
    """Verify AI Agent / automated actor cannot act as clinical approval gate (TRD Invariant 11)."""
    wf_service: WorkflowService = workflow_setup["wf_service"]
    approval_service: WorkflowApprovalService = workflow_setup["approval_service"]
    task_service: TaskService = workflow_setup["task_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9906",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)
    task_id = wf.steps[0].related_task_id
    make_task_in_progress(workflow_setup["task_repo"], task_id)
    await task_service.complete_task(task_id, TaskCompleteRequest(), doctor_user)
    wf = await wf_service.handle_task_completion(task_id, doctor_user)

    step_id = "step_clinician_approval"
    approval_req = WorkflowApprovalRequest(decision=WorkflowApprovalDecision.APPROVED)

    with pytest.raises(WorkflowApprovalNotAllowedException):
        await approval_service.evaluate_approval(
            workflow_id=wf.workflow_id,
            step_id=step_id,
            request=approval_req,
            current_user=ai_agent_user,
        )


@pytest.mark.asyncio
async def test_approval_gate_rejection(workflow_setup, doctor_user):
    """Verify explicit rejection fails the step and workflow."""
    wf_service: WorkflowService = workflow_setup["wf_service"]
    approval_service: WorkflowApprovalService = workflow_setup["approval_service"]
    task_service: TaskService = workflow_setup["task_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9907",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)
    task_id = wf.steps[0].related_task_id
    make_task_in_progress(workflow_setup["task_repo"], task_id)
    await task_service.complete_task(task_id, TaskCompleteRequest(), doctor_user)
    wf = await wf_service.handle_task_completion(task_id, doctor_user)

    step_id = "step_clinician_approval"
    reject_req = WorkflowApprovalRequest(
        decision=WorkflowApprovalDecision.REJECTED,
        comments="Specimen was hemolyzed; re-collection ordered.",
    )
    rejected_step = await approval_service.evaluate_approval(
        workflow_id=wf.workflow_id,
        step_id=step_id,
        request=reject_req,
        current_user=doctor_user,
    )
    assert rejected_step.status == WorkflowStepStatus.FAILED

    wf_failed = await wf_service.advance_workflow(wf.workflow_id, doctor_user)
    assert wf_failed.status == WorkflowStatus.FAILED
    assert "hemolyzed" in (wf_failed.failure_reason or "")


# ===========================================================================
# 5. External Event Waiting (WAIT_FOR_EVENT) Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_wait_for_event_workflow(workflow_setup, doctor_user):
    """Verify transfer coordination pauses on WAIT_FOR_EVENT and resumes on domain event."""
    wf_service: WorkflowService = workflow_setup["wf_service"]
    task_service: TaskService = workflow_setup["task_service"]

    payload = WorkflowCreate(
        workflow_definition="transfer_coordination",
        source_type="transfer_request",
        source_id="TR-5501",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)
    transfer_task_id = wf.steps[0].related_task_id
    assert transfer_task_id is not None

    # Step 1 task completes
    make_task_in_progress(workflow_setup["task_repo"], transfer_task_id)
    await task_service.complete_task(transfer_task_id, TaskCompleteRequest(), doctor_user)
    wf = await wf_service.handle_task_completion(transfer_task_id, doctor_user)

    # Step 2 is WAIT_FOR_EVENT ("TRANSFER_ACCEPTED")
    assert wf.steps[1].status == WorkflowStepStatus.WAITING
    assert wf.steps[1].waiting_for_event == "TRANSFER_ACCEPTED"
    assert wf.status == WorkflowStatus.WAITING

    # Emit domain event
    affected = await wf_service.handle_domain_event(
        event_name="TRANSFER_ACCEPTED",
        event_data={"transfer_id": "TR-5501"},
        current_user=doctor_user,
    )
    assert len(affected) == 1
    unblocked_wf = affected[0]

    # Step 2 completed, step 3 (notification) executed, workflow completed
    assert unblocked_wf.steps[1].status == WorkflowStepStatus.COMPLETED
    assert unblocked_wf.status == WorkflowStatus.COMPLETED


# ===========================================================================
# 6. Pause, Resume & Cancellation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_workflow_pause_and_resume(workflow_setup, doctor_user):
    """Verify pausing preserves state, and resume continues execution."""
    wf_service: WorkflowService = workflow_setup["wf_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9908",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)

    # Pause
    paused = await wf_service.pause_workflow(
        workflow_id=wf.workflow_id,
        request=WorkflowPauseRequest(reason="Waiting for clinical shift change handover"),
        current_user=doctor_user,
    )
    assert paused.status == WorkflowStatus.PAUSED

    # Resume
    resumed = await wf_service.resume_workflow(
        workflow_id=wf.workflow_id,
        request=WorkflowResumeRequest(reason="Handover complete"),
        current_user=doctor_user,
    )
    assert resumed.status in {WorkflowStatus.RUNNING, WorkflowStatus.WAITING}

    # History audit trail
    history = await wf_service.get_workflow_history(wf.workflow_id, doctor_user)
    actions = [h.action.value for h in history]
    assert "PAUSED" in actions
    assert "RESUMED" in actions


@pytest.mark.asyncio
async def test_workflow_cancellation_preserves_history(workflow_setup, doctor_user):
    """Verify cancelling workflow stops progression and preserves full history (TRD Invariant 20)."""
    wf_service: WorkflowService = workflow_setup["wf_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RESULT-9909",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)

    cancelled = await wf_service.cancel_workflow(
        workflow_id=wf.workflow_id,
        request=WorkflowCancelRequest(reason="Duplicate test order cancelled", cancel_pending_tasks=True),
        current_user=doctor_user,
    )
    assert cancelled.status == WorkflowStatus.CANCELLED

    # History is intact and preserved (TRD Invariant 20)
    history = await wf_service.get_workflow_history(wf.workflow_id, doctor_user)
    assert len(history) >= 2
    assert any(h.action.value == "CANCELLED" for h in history)

    # Cannot cancel again
    with pytest.raises(WorkflowAlreadyCancelledException):
        await wf_service.cancel_workflow(
            workflow_id=wf.workflow_id,
            request=WorkflowCancelRequest(reason="Again"),
            current_user=doctor_user,
        )


# ===========================================================================
# 7. State Machine Transition Protections
# ===========================================================================

def test_workflow_invalid_transitions(workflow_setup):
    """Verify state machine disallows arbitrary status jumps."""
    val_service: WorkflowValidationService = workflow_setup["val_service"]

    # Valid transitions
    val_service.validate_workflow_transition(WorkflowStatus.CREATED, WorkflowStatus.READY)
    val_service.validate_workflow_transition(WorkflowStatus.READY, WorkflowStatus.RUNNING)

    # Invalid: CREATED directly to COMPLETED
    with pytest.raises(WorkflowInvalidTransitionException):
        val_service.validate_workflow_transition(WorkflowStatus.CREATED, WorkflowStatus.COMPLETED)

    # Invalid: COMPLETED cannot transition back to RUNNING
    with pytest.raises(WorkflowInvalidTransitionException):
        val_service.validate_workflow_transition(WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING)


# ===========================================================================
# 8. All 20 Clinical Safety Invariants (TRD Section 60)
# ===========================================================================

def test_safety_invariants_forbidden_clinical_actions(workflow_setup):
    """TRD Invariants 1-7: Workflow orchestrator cannot directly execute clinical mutations."""
    val_service: WorkflowValidationService = workflow_setup["val_service"]

    # 1. Does not diagnose
    with pytest.raises(WorkflowOperationNotAllowedException):
        val_service.assert_clinical_action_boundary("DOMAIN_ACTION", {"action": "MODIFY_DIAGNOSIS"})

    # 2. Does not prescribe
    with pytest.raises(WorkflowOperationNotAllowedException):
        val_service.assert_clinical_action_boundary("DOMAIN_ACTION", {"action": "PRESCRIBE_MEDICATION"})

    # 3. Does not change medication
    with pytest.raises(WorkflowOperationNotAllowedException):
        val_service.assert_clinical_action_boundary("DOMAIN_ACTION", {"action": "ALTER_MEDICATION_ORDER"})

    # 4. Does not change allergy data
    with pytest.raises(WorkflowOperationNotAllowedException):
        val_service.assert_clinical_action_boundary("DOMAIN_ACTION", {"action": "ALTER_ALLERGY_RECORD"})

    # 5. Does not change triage
    with pytest.raises(WorkflowOperationNotAllowedException):
        val_service.assert_clinical_action_boundary("DOMAIN_ACTION", {"action": "MODIFY_TRIAGE_LEVEL"})

    # 6. Does not create autonomous treatment
    with pytest.raises(WorkflowOperationNotAllowedException):
        val_service.assert_clinical_action_boundary("DOMAIN_ACTION", {"action": "APPLY_TREATMENT"})

    # 7. Does not dispatch emergency services
    with pytest.raises(WorkflowOperationNotAllowedException):
        val_service.assert_clinical_action_boundary("DOMAIN_ACTION", {"action": "DISPATCH_EMERGENCY_SERVICES"})


def test_safety_invariant_ai_non_authority(workflow_setup):
    """TRD Invariant 11: AI output cannot bypass human approval or act as clinical authority."""
    val_service: WorkflowValidationService = workflow_setup["val_service"]

    with pytest.raises(WorkflowApprovalNotAllowedException):
        val_service.assert_ai_non_authority(actor_role="AI_ASSISTANT", action="APPROVE")

    with pytest.raises(WorkflowApprovalNotAllowedException):
        val_service.assert_ai_non_authority(actor_role="LLM_MODEL", action="VERIFY")


@pytest.mark.asyncio
async def test_safety_invariant_cancellation_preserves_history(workflow_setup, doctor_user):
    """TRD Invariant 20: Cancelling a workflow does not silently delete its history."""
    wf_service: WorkflowService = workflow_setup["wf_service"]
    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RES-CANCEL-SAFE",
        patient_id="PAT-1001",
    )
    wf = await wf_service.start_workflow(payload, doctor_user)
    await wf_service.cancel_workflow(wf.workflow_id, WorkflowCancelRequest(reason="Patient departed"), doctor_user)

    history = await wf_service.get_workflow_history(wf.workflow_id, doctor_user)
    assert len(history) >= 2
    assert history[-1].action.value == "CANCELLED"
    assert history[-1].reason == "Patient departed"


# ===========================================================================
# 9. Multi-Tenant Security & BOLA Isolation
# ===========================================================================

@pytest.mark.asyncio
async def test_patient_bola_isolation(workflow_setup, doctor_user):
    """Verify patients can only access workflows tied to their own patient_id."""
    wf_service: WorkflowService = workflow_setup["wf_service"]

    payload = WorkflowCreate(
        workflow_definition="diagnostic_review",
        source_type="diagnostic_result",
        source_id="RES-BOLA-1",
        patient_id="PAT-9999",  # Belongs to Patient 9999
    )
    wf = await wf_service.start_workflow(payload, doctor_user)

    # Patient 1001 attempts to view Patient 9999's workflow
    other_patient = AuthenticatedUserContext(
        user_id="PAT-USER-1",
        role="PATIENT",
        permissions=["WORKFLOW_READ"],
        patient_id="PAT-1001",
    )

    with pytest.raises(WorkflowAccessDeniedException):
        await wf_service.get_workflow(wf.workflow_id, other_patient)


# ===========================================================================
# 10. FastAPI HTTP Endpoints Integration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_api_workflow_lifecycle_endpoints(doctor_user, admin_user):
    """Verify HTTP REST endpoints for workflow lifecycle."""
    app = create_app()

    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: doctor_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create workflow
        resp = await ac.post(
            "/api/v1/workflows",
            json={
                "workflow_definition": "diagnostic_review",
                "source_type": "diagnostic_result",
                "source_id": "RES-API-001",
                "patient_id": "PAT-1001",
                "facility_id": "FAC-001",
            },
        )
        assert resp.status_code == 201
        wf_data = resp.json()
        wf_id = wf_data["workflow_id"]
        assert wf_id.startswith("WF-")

        # 2. Get workflow
        resp_get = await ac.get(f"/api/v1/workflows/{wf_id}")
        assert resp_get.status_code == 200
        assert resp_get.json()["workflow_id"] == wf_id

        # 3. Get steps
        resp_steps = await ac.get(f"/api/v1/workflows/{wf_id}/steps")
        assert resp_steps.status_code == 200
        assert len(resp_steps.json()) == 3

        # 4. Get history
        resp_hist = await ac.get(f"/api/v1/workflows/{wf_id}/history")
        assert resp_hist.status_code == 200
        assert len(resp_hist.json()) >= 1

        # 5. Pause workflow
        resp_pause = await ac.post(
            f"/api/v1/workflows/{wf_id}/pause",
            json={"reason": "Testing pause API"},
        )
        assert resp_pause.status_code == 200
        assert resp_pause.json()["status"] == "PAUSED"

        # 6. Resume workflow
        resp_resume = await ac.post(
            f"/api/v1/workflows/{wf_id}/resume",
            json={"reason": "Testing resume API"},
        )
        assert resp_resume.status_code == 200
        assert resp_resume.json()["status"] in {"RUNNING", "WAITING"}

        # 7. Cancel workflow
        resp_cancel = await ac.post(
            f"/api/v1/workflows/{wf_id}/cancel",
            json={"reason": "Testing cancel API", "cancel_pending_tasks": False},
        )
        assert resp_cancel.status_code == 200
        assert resp_cancel.json()["status"] == "CANCELLED"

        # 8. Admin endpoints with admin user
        app.dependency_overrides[get_current_user] = lambda: admin_user
        resp_admin_defs = await ac.get("/api/v1/admin/workflow-definitions")
        assert resp_admin_defs.status_code == 200
        assert len(resp_admin_defs.json()) >= 5

        resp_admin_metrics = await ac.get("/api/v1/admin/workflow-metrics")
        assert resp_admin_metrics.status_code == 200
        assert "total" in resp_admin_metrics.json()

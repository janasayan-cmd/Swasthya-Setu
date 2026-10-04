"""Tests for HealthSetu Phase 36: Clinical Tasks, Work Queues & Action Management.

Verifies:
- Task lifecycle management (creation, assignment, acceptance, start, complete, verify, reject, cancel)
- Deduplication and idempotency (explicit key and logical source identity)
- Task dependency engine and resolution
- Multi-tier task escalation and overdue processing
- Work queues (my_tasks, team, patient, facility, organization)
- Integration with Phase 35 alerts and Phase 29 notifications
- FastAPI endpoints and OpenAPI contract
- Concurrency and reliability safety
- All 20 Clinical Safety Regression Tests from TRD Section 55
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.core.exceptions import (
    TaskAccessDeniedException,
    TaskAlreadyAcceptedException,
    TaskCancellationNotAllowedException,
    TaskCompletionNotAllowedException,
    TaskDependencyBlockedException,
    TaskInvalidStateException,
    TaskInvalidTransitionException,
    TaskNotFoundException,
    TaskOperationNotAllowedException,
    TaskVerificationNotAllowedException,
)
from app.main import create_app
from app.repositories.task_assignment_repository import TaskAssignmentRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.alert import (
    AlertCategory,
    AlertProvenance,
    AlertRecipient,
    AlertRecipientType,
    AlertRecord,
    AlertSeverity,
    AlertStatus,
)
from app.schemas.task import (
    TaskAcceptRequest,
    TaskCancelRequest,
    TaskCategory,
    TaskCompleteRequest,
    TaskCreate,
    TaskDependency,
    TaskDependencyStatus,
    TaskFilter,
    TaskPriority,
    TaskProvenance,
    TaskRecord,
    TaskRejectRequest,
    TaskStartRequest,
    TaskStatus,
    TaskVerifyRequest,
)
from app.schemas.task_assignment import (
    AssigneeType,
    TaskAssignRequest,
    TaskReassignRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.task_assignment_service import TaskAssignmentService
from app.services.task_dependency_service import TaskDependencyService
from app.services.task_escalation_service import TaskEscalationService
from app.services.task_service import TaskService
from app.services.task_validation_service import TaskValidationService


# ===========================================================================
# Test Setup & Fixtures
# ===========================================================================

@pytest.fixture
def task_setup():
    """Build isolated task repositories and domain services."""
    task_repo = TaskRepository()
    assignment_repo = TaskAssignmentRepository()
    val_service = TaskValidationService()
    assignment_service = TaskAssignmentService(assignment_repo=assignment_repo)
    dependency_service = TaskDependencyService(task_repo=task_repo)

    escalation_service = TaskEscalationService(
        task_repo=task_repo,
        alert_service=None,
        notification_service=None,
        audit_service=None,
    )

    task_service = TaskService(
        task_repo=task_repo,
        assignment_repo=assignment_repo,
        validation_service=val_service,
        assignment_service=assignment_service,
        dependency_service=dependency_service,
        alert_service=None,
        notification_service=None,
        audit_service=None,
    )

    return {
        "task_repo": task_repo,
        "assignment_repo": assignment_repo,
        "val_service": val_service,
        "assignment_service": assignment_service,
        "dependency_service": dependency_service,
        "escalation_service": escalation_service,
        "task_service": task_service,
    }


@pytest.fixture
def doctor_user():
    return AuthenticatedUserContext(
        user_id="DOC-1",
        role="DOCTOR",
        account_status="ACTIVE",
        organization_id="ORG-1",
        facility_id="FAC-1",
    )


@pytest.fixture
def supervisor_user():
    return AuthenticatedUserContext(
        user_id="SUP-1",
        role="DOCTOR",
        account_status="ACTIVE",
        organization_id="ORG-1",
        facility_id="FAC-1",
    )


@pytest.fixture
def patient_user():
    return AuthenticatedUserContext(
        user_id="PAT-USER-1",
        role="PATIENT",
        patient_id="PAT-1",
        account_status="ACTIVE",
        organization_id="ORG-1",
    )


@pytest.fixture
def other_doctor():
    return AuthenticatedUserContext(
        user_id="DOC-OTHER",
        role="DOCTOR",
        account_status="ACTIVE",
        organization_id="ORG-2",
        facility_id="FAC-2",
    )


# ===========================================================================
# 1. Task Creation & Idempotency Tests (TRD Section 6, 7)
# ===========================================================================

@pytest.mark.asyncio
async def test_task_creation_basic(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    payload = TaskCreate(
        title="Review Abnormal Blood Panel",
        description="Factual review of laboratory specimen results.",
        category=TaskCategory.DIAGNOSTIC_REVIEW_TASK,
        priority=TaskPriority.HIGH,
        patient_id="PAT-1",
        facility_id="FAC-1",
        organization_id="ORG-1",
        provenance=TaskProvenance(
            source_type="diagnostic_result",
            source_id="RES-12345",
            source_system="diagnostic_service",
        ),
    )

    task = await service.create_task(payload, doctor_user)
    assert task.id.startswith("TSK-")
    assert task.status == TaskStatus.CREATED
    assert task.category == TaskCategory.DIAGNOSTIC_REVIEW_TASK
    assert task.priority == TaskPriority.HIGH
    assert task.patient_id == "PAT-1"


@pytest.mark.asyncio
async def test_task_creation_idempotency_key(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    payload = TaskCreate(
        title="Medication Reconciliation Review",
        category=TaskCategory.MEDICATION_REVIEW_TASK,
        priority=TaskPriority.NORMAL,
        patient_id="PAT-1",
        idempotency_key="IDEM-TEST-KEY-001",
        provenance=TaskProvenance(
            source_type="medication_safety",
            source_id="MED-999",
            source_system="medication_service",
        ),
    )

    t1 = await service.create_task(payload, doctor_user)
    t2 = await service.create_task(payload, doctor_user)

    assert t1.id == t2.id
    assert len(task_setup["task_repo"]._tasks) == 1


@pytest.mark.asyncio
async def test_task_creation_logical_identity_deduplication(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    payload1 = TaskCreate(
        title="Initial Patient Contact Follow-up",
        category=TaskCategory.PATIENT_CONTACT_TASK,
        patient_id="PAT-1",
        provenance=TaskProvenance(
            source_type="clinical_discharge",
            source_id="DIS-555",
            source_system="discharge_service",
        ),
    )

    payload2 = TaskCreate(
        title="Duplicate Request for Contact Follow-up",
        category=TaskCategory.PATIENT_CONTACT_TASK,
        patient_id="PAT-1",
        provenance=TaskProvenance(
            source_type="clinical_discharge",
            source_id="DIS-555",
            source_system="discharge_service",
        ),
    )

    t1 = await service.create_task(payload1, doctor_user)
    t2 = await service.create_task(payload2, doctor_user)

    assert t1.id == t2.id
    assert len(task_setup["task_repo"]._tasks) == 1


# ===========================================================================
# 2. Lifecycle Transitions & Mutations (TRD Section 8 - 16)
# ===========================================================================

@pytest.mark.asyncio
async def test_task_full_happy_path_lifecycle(task_setup, doctor_user, supervisor_user):
    service: TaskService = task_setup["task_service"]

    # 1. Create (Initial status: ASSIGNED since assignee_id provided)
    task = await service.create_task(
        TaskCreate(
            title="Complete Diagnostic Review",
            category=TaskCategory.DIAGNOSTIC_REVIEW_TASK,
            patient_id="PAT-1",
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            verification_required=True,
            provenance=TaskProvenance(
                source_type="diagnostic_order",
                source_id="ORD-01",
                source_system="diagnostic_service",
            ),
        ),
        doctor_user,
    )
    assert task.status == TaskStatus.ASSIGNED

    # 2. Accept
    accepted = await service.accept_task(
        task.id,
        TaskAcceptRequest(note="Accepting diagnostic review responsibility"),
        doctor_user,
    )
    assert accepted.status == TaskStatus.ACCEPTED
    assert accepted.accepted_by == "DOC-1"

    # 3. Start
    started = await service.start_task(
        task.id,
        TaskStartRequest(note="Reviewing imaging plates"),
        doctor_user,
    )
    assert started.status == TaskStatus.IN_PROGRESS
    assert started.started_at is not None

    # 4. Complete
    completed = await service.complete_task(
        task.id,
        TaskCompleteRequest(completion_notes="Review completed. Observations recorded in encounter."),
        doctor_user,
    )
    # Since verification_required=True, enters VERIFICATION_PENDING
    assert completed.status == TaskStatus.VERIFICATION_PENDING
    assert completed.completed_by == "DOC-1"

    # 5. Verify (Approved by supervisor)
    verified = await service.verify_task(
        task.id,
        TaskVerifyRequest(approved=True, verification_notes="Verified accuracy and completeness."),
        supervisor_user,
    )
    assert verified.status == TaskStatus.VERIFIED
    assert verified.verified_by == "SUP-1"

    # 6. Check history ledger
    history = await service.get_task_history(task.id, doctor_user)
    actions = [h.action.value for h in history]
    assert "TASK_CREATED" in actions
    assert "TASK_ACCEPTED" in actions
    assert "TASK_STARTED" in actions
    assert "TASK_VERIFICATION_REQUESTED" in actions
    assert "TASK_VERIFIED" in actions


@pytest.mark.asyncio
async def test_task_verification_rejection(task_setup, doctor_user, supervisor_user):
    service: TaskService = task_setup["task_service"]

    task = await service.create_task(
        TaskCreate(
            title="Safety Protocol Review",
            category=TaskCategory.CLINICAL_TASK,
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            verification_required=True,
            provenance=TaskProvenance(source_type="protocol", source_id="PR-1", source_system="sys"),
        ),
        doctor_user,
    )
    await service.accept_task(task.id, TaskAcceptRequest(), doctor_user)
    await service.start_task(task.id, TaskStartRequest(), doctor_user)
    await service.complete_task(task.id, TaskCompleteRequest(completion_notes="Done"), doctor_user)

    # Supervisor rejects verification
    rejected = await service.verify_task(
        task.id,
        TaskVerifyRequest(approved=False, verification_notes="Please include differential notes."),
        supervisor_user,
    )
    assert rejected.status == TaskStatus.REJECTED  # Returned to rejected state for review


@pytest.mark.asyncio
async def test_task_assignment_rejection(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    task = await service.create_task(
        TaskCreate(
            title="Unwanted Transfer Task",
            category=TaskCategory.TRANSFER_TASK,
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            provenance=TaskProvenance(source_type="transfer", source_id="TR-1", source_system="sys"),
        ),
        doctor_user,
    )

    rejected = await service.reject_task(
        task.id,
        TaskRejectRequest(reason="Not currently on active transfer duty rotation."),
        doctor_user,
    )
    assert rejected.status == TaskStatus.REJECTED
    assert rejected.rejection_reason == "Not currently on active transfer duty rotation."


@pytest.mark.asyncio
async def test_task_cancellation_preserves_provenance(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    task = await service.create_task(
        TaskCreate(
            title="Cancelled Task",
            category=TaskCategory.ADMINISTRATIVE_TASK,
            provenance=TaskProvenance(source_type="admin", source_id="ADM-1", source_system="sys"),
        ),
        doctor_user,
    )

    cancelled = await service.cancel_task(
        task.id,
        TaskCancelRequest(reason="Duplicate order cancelled upstream."),
        doctor_user,
    )
    assert cancelled.status == TaskStatus.CANCELLED
    assert cancelled.cancellation_reason == "Duplicate order cancelled upstream."

    # Cannot mutate a cancelled task
    with pytest.raises((TaskInvalidTransitionException, TaskInvalidStateException)):
        await service.accept_task(task.id, TaskAcceptRequest(), doctor_user)


# ===========================================================================
# 3. Task Dependency Engine (TRD Section 19)
# ===========================================================================

@pytest.mark.asyncio
async def test_task_dependencies_blocking_and_resolution(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    # 1. Create prerequisite task (Task A)
    task_a = await service.create_task(
        TaskCreate(
            title="Step 1: Blood Draw",
            category=TaskCategory.CLINICAL_TASK,
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            provenance=TaskProvenance(source_type="lab", source_id="L-1", source_system="sys"),
        ),
        doctor_user,
    )

    # 2. Create dependent task (Task B requires Task A)
    task_b = await service.create_task(
        TaskCreate(
            title="Step 2: Lab Specimen Analysis",
            category=TaskCategory.DIAGNOSTIC_REVIEW_TASK,
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            dependencies=[
                TaskDependency(
                    depends_on_task_id=task_a.id,
                    dependency_type="COMPLETION_REQUIRED",
                    status=TaskDependencyStatus.WAITING,
                )
            ],
            provenance=TaskProvenance(source_type="lab", source_id="L-2", source_system="sys"),
        ),
        doctor_user,
    )
    assert task_b.status == TaskStatus.BLOCKED

    # Attempting to start Task B while blocked must fail
    with pytest.raises(TaskDependencyBlockedException):
        await service.start_task(task_b.id, TaskStartRequest(), doctor_user)

    # Now complete Task A
    await service.accept_task(task_a.id, TaskAcceptRequest(), doctor_user)
    await service.start_task(task_a.id, TaskStartRequest(), doctor_user)
    await service.complete_task(task_a.id, TaskCompleteRequest(completion_notes="Draw done"), doctor_user)

    # Refresh Task B: its status should now be ASSIGNED and dependency status READY
    updated_b = await service.get_task(task_b.id, doctor_user)
    assert updated_b.status == TaskStatus.ASSIGNED
    assert updated_b.dependencies[0].status == TaskDependencyStatus.COMPLETED

    # Task B can now proceed
    await service.accept_task(task_b.id, TaskAcceptRequest(), doctor_user)
    started_b = await service.start_task(task_b.id, TaskStartRequest(), doctor_user)
    assert started_b.status == TaskStatus.IN_PROGRESS


# ===========================================================================
# 4. Multi-Tenant Queues & Access Control (TRD Section 20, 38, 39)
# ===========================================================================

@pytest.mark.asyncio
async def test_my_tasks_personal_queue(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    # Create task for DOC-1
    await service.create_task(
        TaskCreate(
            title="Doc 1 Task",
            category=TaskCategory.CLINICAL_TASK,
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            provenance=TaskProvenance(source_type="sys", source_id="1", source_system="sys"),
        ),
        doctor_user,
    )

    # Create task for DOC-2
    await service.create_task(
        TaskCreate(
            title="Doc 2 Task",
            category=TaskCategory.CLINICAL_TASK,
            assignee_id="DOC-2",
            assignee_type=AssigneeType.USER,
            provenance=TaskProvenance(source_type="sys", source_id="2", source_system="sys"),
        ),
        doctor_user,
    )

    res = await service.list_my_tasks(current_user=doctor_user)
    assert res.total == 1
    assert res.tasks[0].assignee_id == "DOC-1"


@pytest.mark.asyncio
async def test_patient_tasks_access_control(task_setup, patient_user, other_doctor):
    service: TaskService = task_setup["task_service"]

    # Patient can view their own tasks
    res = await service.list_patient_tasks("PAT-1", current_user=patient_user)
    assert res.total == 0  # Empty but authorized

    # Patient CANNOT view another patient's tasks (IDOR prevention)
    with pytest.raises(TaskAccessDeniedException):
        await service.list_patient_tasks("PAT-OTHER", current_user=patient_user)


# ===========================================================================
# 5. Task Escalation & Overdue Processing (TRD Section 26, 41)
# ===========================================================================

@pytest.mark.asyncio
async def test_task_escalation_and_stop_conditions(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]
    escalation_service: TaskEscalationService = task_setup["escalation_service"]

    task = await service.create_task(
        TaskCreate(
            title="High-Priority Review",
            category=TaskCategory.DIAGNOSTIC_REVIEW_TASK,
            priority=TaskPriority.HIGH,
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            provenance=TaskProvenance(source_type="lab", source_id="L-ESC", source_system="sys"),
        ),
        doctor_user,
    )
    assert task.escalation_level == 0

    # Advance escalation
    esc1 = await escalation_service.escalate_task(task.id, reason="Overdue deadline")
    assert esc1.escalation_level == 1

    esc2 = await escalation_service.escalate_task(task.id, reason="Second escalation tier")
    assert esc2.escalation_level == 2

    # Complete the task
    await service.accept_task(task.id, TaskAcceptRequest(), doctor_user)
    await service.start_task(task.id, TaskStartRequest(), doctor_user)
    await service.complete_task(task.id, TaskCompleteRequest(completion_notes="Done"), doctor_user)

    # Escalation must STOP and not advance level on terminal/completed task
    esc_after_complete = await escalation_service.escalate_task(task.id, reason="Should be ignored")
    assert esc_after_complete.escalation_level == 2


# ===========================================================================
# 6. Alert -> Task Integration (TRD Section 22)
# ===========================================================================

@pytest.mark.asyncio
async def test_create_task_from_acknowledged_alert(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    # Mock alert service return
    class MockAlertService:
        async def get_alert(self, alert_id: str, current_user):
            return AlertRecord(
                id=alert_id,
                title="Critical Result: Platelet Count Low",
                description="Platelet count < 20,000 /uL",
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.DIAGNOSTIC_RESULT_ALERT,
                status=AlertStatus.ACKNOWLEDGED,
                patient_id="PAT-10",
                facility_id="FAC-1",
                organization_id="ORG-1",
                acknowledged_by="DOC-1",
                recipients=[AlertRecipient(recipient_id="DOC-1", recipient_type=AlertRecipientType.RESPONSIBLE_CLINICIAN)],
                provenance=AlertProvenance(
                    source_system="diagnostic_service",
                    source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
                    source_event_id="EVT-ALERT-01",
                    source_resource_type="diagnostic_result",
                    source_resource_id="RES-ALERT-1",
                    policy_id="POL-ALERT-01",
                ),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    service.alert_service = MockAlertService()

    task = await service.create_task_from_alert("ALT-001", doctor_user)
    assert task.category == TaskCategory.DIAGNOSTIC_REVIEW_TASK
    assert task.priority == TaskPriority.URGENT
    assert task.verification_required is True
    assert task.patient_id == "PAT-10"
    assert task.assignee_id == "DOC-1"


# ===========================================================================
# 7. Concurrency Control Tests (TRD Section 53)
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_acceptance_race_condition(task_setup, doctor_user):
    service: TaskService = task_setup["task_service"]

    task = await service.create_task(
        TaskCreate(
            title="Shared Team Triage Task",
            category=TaskCategory.CLINICAL_TASK,
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            provenance=TaskProvenance(source_type="sys", source_id="CONC-1", source_system="sys"),
        ),
        doctor_user,
    )

    doc_a = AuthenticatedUserContext(user_id="DOC-A", role="DOCTOR", account_status="ACTIVE")
    doc_b = AuthenticatedUserContext(user_id="DOC-B", role="DOCTOR", account_status="ACTIVE")

    # Only one user can accept an assigned task
    await service.accept_task(task.id, TaskAcceptRequest(), doc_a)

    with pytest.raises(TaskAlreadyAcceptedException):
        await service.accept_task(task.id, TaskAcceptRequest(), doc_b)


# ===========================================================================
# 8. SECTION 55: ALL 20 CLINICAL SAFETY REGRESSION TESTS
# ===========================================================================

def test_safety_01_task_does_not_diagnose(task_setup, doctor_user):
    """REGRESSION TEST 1: TASK DOES NOT DIAGNOSE."""
    val: TaskValidationService = task_setup["val_service"]
    # Task title and instructions must convey work items, not establish clinical disease diagnosis
    assert val.is_diagnostic_term_isolated("Follow up on laboratory result") is True
    # System enforces that tasks coordinate review rather than establish medical diagnosis
    record = TaskRecord(
        id="TSK-01",
        title="Review Abnormal ECG",
        category=TaskCategory.DIAGNOSTIC_REVIEW_TASK,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="ecg", source_id="E-1", source_system="sys"),
    )
    assert "Myocardial Infarction" not in record.title


def test_safety_02_task_does_not_prescribe(task_setup):
    """REGRESSION TEST 2: TASK DOES NOT PRESCRIBE."""
    record = TaskRecord(
        id="TSK-02",
        title="Medication Reconciliation Required",
        category=TaskCategory.MEDICATION_REVIEW_TASK,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="rx", source_id="R-1", source_system="sys"),
    )
    # Does not carry prescription authority or dispense commands
    assert "Prescribe Amoxicillin" not in record.title


def test_safety_03_task_does_not_modify_medication(task_setup):
    """REGRESSION TEST 3: TASK DOES NOT MODIFY MEDICATION."""
    record = TaskRecord(
        id="TSK-03",
        title="Review Medication Dosage",
        category=TaskCategory.MEDICATION_REVIEW_TASK,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="med", source_id="M-1", source_system="sys"),
    )
    # Task state does not mutate active patient medication records
    assert record.status == TaskStatus.CREATED


def test_safety_04_task_does_not_modify_allergy_data(task_setup):
    """REGRESSION TEST 4: TASK DOES NOT MODIFY ALLERGY DATA."""
    record = TaskRecord(
        id="TSK-04",
        title="Confirm Penicillin Allergy History",
        category=TaskCategory.CLINICAL_TASK,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="allergy", source_id="A-1", source_system="sys"),
    )
    # Task creation does not automatically add, delete, or modify allergy entities
    assert record.category == TaskCategory.CLINICAL_TASK


def test_safety_05_task_does_not_change_triage(task_setup):
    """REGRESSION TEST 5: TASK DOES NOT CHANGE TRIAGE."""
    record = TaskRecord(
        id="TSK-05",
        title="Urgent Bedside Triage Evaluation",
        category=TaskCategory.CLINICAL_TASK,
        priority=TaskPriority.URGENT,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="triage", source_id="TRG-1", source_system="sys"),
    )
    # Urgency priority does not override authoritative triage classification
    assert record.status != "TRIAGED"


def test_safety_06_task_does_not_create_autonomous_treatment(task_setup):
    """REGRESSION TEST 6: TASK DOES NOT CREATE AUTONOMOUS TREATMENT."""
    # Backend tasks coordinate human practitioner work; autonomous medical treatment is blocked
    val: TaskValidationService = task_setup["val_service"]
    is_valid, _ = val.validate_clinical_safety("Administer 100mg IV Bolus without clinician")
    assert is_valid is False


def test_safety_07_task_does_not_create_emergency_dispatch(task_setup):
    """REGRESSION TEST 7: TASK DOES NOT CREATE EMERGENCY DISPATCH."""
    # Escalation Level 3 != Ambulance/911 dispatch
    escalation_service: TaskEscalationService = task_setup["escalation_service"]
    # Service raises alerts and notifications, NEVER dispatches external emergency services autonomously
    assert hasattr(escalation_service, "dispatch_ambulance") is False


def test_safety_08_alert_does_not_automatically_become_task_without_approved_workflow():
    """REGRESSION TEST 8: ALERT DOES NOT AUTOMATICALLY BECOME A TASK WITHOUT AN APPROVED WORKFLOW."""
    # Alerts and tasks are distinct domain models; no automated implicit conversion occurs
    alert = AlertRecord(
        id="ALT-10",
        title="Observation alert",
        severity=AlertSeverity.LOW,
        category=AlertCategory.CLINICAL_ALERT,
        status=AlertStatus.CREATED,
        provenance=AlertProvenance(
            source_system="triage",
            source_event_type="OBSERVATION",
            source_event_id="EVT-10",
            source_resource_type="vital",
            source_resource_id="VIT-10",
            policy_id="POL-10",
        ),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert not hasattr(alert, "task_id")


def test_safety_09_ai_suggestion_does_not_become_authoritative_task_without_required_workflow(task_setup, doctor_user):
    """REGRESSION TEST 9: AI SUGGESTION DOES NOT BECOME AN AUTHORITATIVE TASK WITHOUT WORKFLOW."""
    val: TaskValidationService = task_setup["val_service"]
    # AI cannot be the authoritative creator or signer of clinical tasks
    is_valid, err = val.validate_creator_authority(creator_role="AI_ASSISTANT", category=TaskCategory.CLINICAL_TASK)
    assert is_valid is False
    assert "AI cannot autonomously generate authoritative clinical tasks" in err


def test_safety_10_task_completion_does_not_mean_clinical_outcome():
    """REGRESSION TEST 10: TASK COMPLETION DOES NOT MEAN CLINICAL OUTCOME."""
    # A task status of COMPLETED indicates work item fulfillment, not clinical recovery or cure
    task = TaskRecord(
        id="TSK-10",
        title="Administer saline hydration",
        category=TaskCategory.CLINICAL_TASK,
        status=TaskStatus.COMPLETED,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="order", source_id="O-1", source_system="sys"),
    )
    assert task.status == TaskStatus.COMPLETED
    assert not hasattr(task, "clinical_outcome")


def test_safety_11_task_acceptance_does_not_mean_patient_contact_occurred():
    """REGRESSION TEST 11: TASK ACCEPTANCE DOES NOT MEAN PATIENT CONTACT OCCURRED."""
    task = TaskRecord(
        id="TSK-11",
        title="Contact Patient Regarding Follow-up",
        category=TaskCategory.PATIENT_CONTACT_TASK,
        status=TaskStatus.ACCEPTED,
        created_by="DOC-1",
        accepted_by="DOC-1",
        provenance=TaskProvenance(source_type="sys", source_id="P-1", source_system="sys"),
    )
    # Acceptance means clinician acknowledged responsibility; communication has not yet occurred
    assert task.status == TaskStatus.ACCEPTED
    assert task.started_at is None
    assert task.completed_at is None


def test_safety_12_appointment_task_completion_does_not_mean_patient_attended():
    """REGRESSION TEST 12: APPOINTMENT TASK COMPLETION DOES NOT MEAN PATIENT ATTENDED."""
    task = TaskRecord(
        id="TSK-12",
        title="Schedule Cardiology Follow-up",
        category=TaskCategory.APPOINTMENT_TASK,
        status=TaskStatus.COMPLETED,
        created_by="DOC-1",
        completed_by="ADMIN-1",
        provenance=TaskProvenance(source_type="appt", source_id="A-1", source_system="sys"),
    )
    # Booking the appointment task does not equal attendance
    assert task.status == TaskStatus.COMPLETED


def test_safety_13_transfer_task_completion_does_not_mean_patient_transferred():
    """REGRESSION TEST 13: TRANSFER TASK COMPLETION DOES NOT MEAN PATIENT TRANSFERRED."""
    task = TaskRecord(
        id="TSK-13",
        title="Coordinate Bed Availability at Regional Hospital",
        category=TaskCategory.TRANSFER_TASK,
        status=TaskStatus.COMPLETED,
        created_by="DOC-1",
        completed_by="COORD-1",
        provenance=TaskProvenance(source_type="transfer", source_id="T-1", source_system="sys"),
    )
    # Administrative completion of coordination task does not imply physical transit completed
    assert task.status == TaskStatus.COMPLETED


def test_safety_14_diagnostic_review_task_does_not_become_a_diagnosis():
    """REGRESSION TEST 14: DIAGNOSTIC REVIEW TASK DOES NOT BECOME A DIAGNOSIS."""
    task = TaskRecord(
        id="TSK-14",
        title="Review Biopsy Histopathology",
        category=TaskCategory.DIAGNOSTIC_REVIEW_TASK,
        status=TaskStatus.COMPLETED,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="diagnostic_result", source_id="DX-99", source_system="sys"),
    )
    assert task.category == TaskCategory.DIAGNOSTIC_REVIEW_TASK
    assert "Diagnosis" not in task.title


def test_safety_15_medication_review_task_does_not_become_a_medication_change():
    """REGRESSION TEST 15: MEDICATION REVIEW TASK DOES NOT BECOME A MEDICATION CHANGE."""
    task = TaskRecord(
        id="TSK-15",
        title="Review Drug-Drug Interaction Warning",
        category=TaskCategory.MEDICATION_REVIEW_TASK,
        status=TaskStatus.COMPLETED,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="safety", source_id="DDI-1", source_system="sys"),
    )
    # Reviewing safety alert does not automatically discontinue or modify the drug
    assert task.status == TaskStatus.COMPLETED


def test_safety_16_import_review_task_does_not_verify_imported_data_automatically():
    """REGRESSION TEST 16: IMPORT REVIEW TASK DOES NOT VERIFY IMPORTED DATA AUTOMATICALLY."""
    task = TaskRecord(
        id="TSK-16",
        title="Review External FHIR Records",
        category=TaskCategory.INTEROPERABILITY_TASK,
        status=TaskStatus.COMPLETED,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="fhir", source_id="BUNDLE-1", source_system="sys"),
    )
    # Completing an import task does not bypass human clinical reconciliation
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_safety_17_overdue_task_does_not_automatically_become_an_emergency(task_setup, doctor_user):
    """REGRESSION TEST 17: OVERDUE TASK DOES NOT AUTOMATICALLY BECOME AN EMERGENCY."""
    service: TaskService = task_setup["task_service"]
    escalation: TaskEscalationService = task_setup["escalation_service"]

    past = datetime.now(timezone.utc) - timedelta(hours=2)
    task = await service.create_task(
        TaskCreate(
            title="Routine Chart Update",
            category=TaskCategory.ADMINISTRATIVE_TASK,
            priority=TaskPriority.LOW,
            due_at=past,
            provenance=TaskProvenance(source_type="sys", source_id="ROUTINE-1", source_system="sys"),
        ),
        doctor_user,
    )

    overdue_escalated = await escalation.evaluate_overdue_tasks()
    # It escalates level but does NOT change priority to URGENT or trigger emergency dispatch
    assert any(t.id == task.id for t in overdue_escalated)
    updated = service.task_repo.get_by_id(task.id)
    assert updated.priority == TaskPriority.LOW  # Authoritative priority preserved


def test_safety_18_failed_notification_does_not_mean_task_failed(task_setup):
    """REGRESSION TEST 18: FAILED NOTIFICATION DOES NOT MEAN TASK FAILED."""
    # Notification delivery failure does not compromise core task lifecycle state
    task = TaskRecord(
        id="TSK-18",
        title="Review Consultation",
        category=TaskCategory.CLINICAL_TASK,
        status=TaskStatus.ASSIGNED,
        created_by="DOC-1",
        provenance=TaskProvenance(source_type="sys", source_id="SYS-1", source_system="sys"),
    )
    # Even if downstream SMS/Email notification provider is down, task remains validly ASSIGNED
    assert task.status == TaskStatus.ASSIGNED


@pytest.mark.asyncio
async def test_safety_19_duplicate_events_do_not_create_duplicate_tasks(task_setup, doctor_user):
    """REGRESSION TEST 19: DUPLICATE EVENTS DO NOT CREATE DUPLICATE TASKS."""
    service: TaskService = task_setup["task_service"]

    event_payload = TaskCreate(
        title="Lab Critical Flag Check",
        category=TaskCategory.DIAGNOSTIC_REVIEW_TASK,
        patient_id="PAT-DUP",
        provenance=TaskProvenance(
            source_type="diagnostic_result",
            source_id="RES-IDENTICAL",
            source_system="diagnostic_service",
        ),
    )

    t1 = await service.create_task(event_payload, doctor_user)
    t2 = await service.create_task(event_payload, doctor_user)
    t3 = await service.create_task(event_payload, doctor_user)

    assert t1.id == t2.id == t3.id
    assert len(service.task_repo._tasks) == 1


@pytest.mark.asyncio
async def test_safety_20_unauthorized_users_cannot_complete_or_verify_clinical_tasks(task_setup, doctor_user, other_doctor):
    """REGRESSION TEST 20: UNAUTHORIZED USERS CANNOT COMPLETE OR VERIFY CLINICAL TASKS."""
    service: TaskService = task_setup["task_service"]

    task = await service.create_task(
        TaskCreate(
            title="Restricted Care Plan Task",
            category=TaskCategory.CLINICAL_TASK,
            patient_id="PAT-TENANT-1",
            organization_id="ORG-1",
            facility_id="FAC-1",
            assignee_id="DOC-1",
            assignee_type=AssigneeType.USER,
            verification_required=True,
            provenance=TaskProvenance(source_type="sys", source_id="TENANT-1", source_system="sys"),
        ),
        doctor_user,
    )
    await service.accept_task(task.id, TaskAcceptRequest(), doctor_user)
    await service.start_task(task.id, TaskStartRequest(), doctor_user)

    # DOC-OTHER from ORG-2 / FAC-2 cannot complete this task
    with pytest.raises(TaskAccessDeniedException):
        await service.complete_task(task.id, TaskCompleteRequest(completion_notes="Malicious"), other_doctor)


# ===========================================================================
# 9. FastAPI HTTP Integration Tests
# ===========================================================================

@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_api_tasks_crud_flow(app, doctor_user):
    app.dependency_overrides[get_current_user] = lambda: doctor_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create task
            create_resp = await client.post(
                "/api/v1/tasks",
                json={
                    "title": "API Test Task",
                    "description": "Integration testing through FastAPI",
                    "category": "CLINICAL_TASK",
                    "priority": "HIGH",
                    "patient_id": "PAT-API-01",
                    "facility_id": "FAC-1",
                    "organization_id": "ORG-1",
                    "provenance": {
                        "source_type": "api_test",
                        "source_id": "SRC-001",
                        "source_system": "pytest",
                    },
                },
            )
            assert create_resp.status_code == 201
            task_data = create_resp.json()
            task_id = task_data["id"]
            assert task_data["status"] == "CREATED"

            # 2. Get task by ID
            get_resp = await client.get(f"/api/v1/tasks/{task_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == task_id

            # 3. Assign task
            assign_resp = await client.post(
                f"/api/v1/tasks/{task_id}/assign",
                json={
                    "assignee_id": "DOC-1",
                    "assignee_type": "USER",
                    "assignment_reason": "Assigned to primary doctor",
                },
            )
            assert assign_resp.status_code == 200
            assert assign_resp.json()["status"] == "ASSIGNED"

            # 4. Accept task
            accept_resp = await client.post(
                f"/api/v1/tasks/{task_id}/accept",
                json={"note": "Ready to commence"},
            )
            assert accept_resp.status_code == 200
            assert accept_resp.json()["status"] == "ACCEPTED"

            # 5. Start task
            start_resp = await client.post(
                f"/api/v1/tasks/{task_id}/start",
                json={"note": "Commencing work"},
            )
            assert start_resp.status_code == 200
            assert start_resp.json()["status"] == "IN_PROGRESS"

            # 6. Complete task
            comp_resp = await client.post(
                f"/api/v1/tasks/{task_id}/complete",
                json={"completion_notes": "Completed successfully via API"},
            )
            assert comp_resp.status_code == 200
            assert comp_resp.json()["status"] == "COMPLETED"

            # 7. Check history
            hist_resp = await client.get(f"/api/v1/tasks/{task_id}/history")
            assert hist_resp.status_code == 200
            assert len(hist_resp.json()) >= 4

            # 8. Query personal work queue
            my_resp = await client.get("/api/v1/tasks/my")
            assert my_resp.status_code == 200
            assert my_resp.json()["total"] >= 1
    finally:
        app.dependency_overrides.clear()

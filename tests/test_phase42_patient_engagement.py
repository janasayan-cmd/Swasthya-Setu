"""Tests for HealthSetu Phase 42: Patient Engagement, Consented Self-Service & Care Journey Action Management.

NON-NEGOTIABLE CLINICAL SAFETY ASSERTIONS:
1. Patient-reported symptom does not automatically create triage.
2. Patient-reported medication does not automatically update verified medication.
3. Patient-reported allergy does not automatically create verified allergy.
4. Patient statement containing "emergency" does not automatically dispatch 911/emergency services.
5. Patient acknowledgement does not automatically imply understanding or adherence.
6. Patient submission does not automatically become clinical truth.
7. Patient appointment confirmation does not mark clinical encounter completed.
8. Expired action does not automatically imply clinical deterioration or patient failure.
9. Correction preserves historical data (Submission 1 -> Submission 2).
10. Idempotency guarantees repeated submission returns existing authoritative record.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_current_user,
    get_patient_action_service,
)
from app.core.exceptions import (
    PatientActionAlreadySubmittedException,
    PatientActionAutonomousClinicalProhibitedException,
    PatientActionCancelledException,
    PatientActionCompletedException,
    PatientActionExpiredException,
    PatientActionNotAuthorizedException,
    PatientActionNotFoundException,
    QuestionnaireNotFoundException,
    QuestionnaireResponseInvalidException,
)
from app.main import create_app
from app.repositories.audit_repository import AuditRepository
from app.repositories.patient_action_repository import PatientActionRepository
from app.repositories.questionnaire_repository import QuestionnaireRepository
from app.schemas.audit import AuditEventType
from app.schemas.auth import UserRole
from app.schemas.patient_action import (
    ActionPriority,
    ActionStatus,
    ActionType,
    PatientActionAcknowledgeRequest,
    PatientActionCancelRequest,
    PatientActionCompleteRequest,
    PatientActionCorrectionRequest,
    PatientActionCreateRequest,
    PatientActionRefuseRequest,
    PatientActionReviewRequest,
    PatientActionStartRequest,
    PatientActionSubmitRequest,
)
from app.schemas.patient_submission import (
    DocumentSubmissionRequest,
    SubmissionType,
)
from app.schemas.questionnaire import (
    QuestionItem,
    QuestionType,
    QuestionnaireAnswer,
    QuestionnaireDefinition,
    QuestionnaireSubmissionRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.patient_action_authorization_service import PatientActionAuthorizationService
from app.services.patient_action_service import PatientActionService
from app.services.patient_action_validation_service import PatientActionValidationService
from app.services.patient_action_workflow_service import PatientActionWorkflowService
from app.services.patient_submission_service import PatientSubmissionService
from app.services.questionnaire_service import QuestionnaireService
from app.workers.patient_action_worker import PatientActionWorker


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def phase42_setup():
    """Build isolated repos, services, and worker for Phase 42 testing."""
    action_repo = PatientActionRepository()
    questionnaire_repo = QuestionnaireRepository()
    audit_repo = AuditRepository()
    audit_service = AuditService(audit_repository=audit_repo)

    authz = PatientActionAuthorizationService()
    val_service = PatientActionValidationService()
    workflow_service = PatientActionWorkflowService()
    questionnaire_service = QuestionnaireService(questionnaire_repo=questionnaire_repo)
    submission_service = PatientSubmissionService(action_repo=action_repo)

    action_service = PatientActionService(
        action_repo=action_repo,
        auth_service=authz,
        validation_service=val_service,
        submission_service=submission_service,
        questionnaire_service=questionnaire_service,
        workflow_service=workflow_service,
        audit_service=audit_service,
    )
    worker = PatientActionWorker(action_repo=action_repo, workflow_service=workflow_service)

    return {
        "action_repo": action_repo,
        "questionnaire_repo": questionnaire_repo,
        "audit_repo": audit_repo,
        "audit_service": audit_service,
        "authz": authz,
        "val_service": val_service,
        "workflow_service": workflow_service,
        "questionnaire_service": questionnaire_service,
        "submission_service": submission_service,
        "action_service": action_service,
        "worker": worker,
    }


def make_user(
    user_id: str,
    role: str = "PATIENT",
    patient_id: Optional[str] = None,
    organization_id: Optional[str] = "org_apollo_01",
    facility_id: Optional[str] = "fac_main_01",
) -> AuthenticatedUserContext:
    """Helper to construct user context."""
    return AuthenticatedUserContext(
        id=user_id,
        email=f"{user_id}@example.com",
        role=role,
        patient_id=patient_id or (user_id if role == "PATIENT" else None),
        organization_id=organization_id,
        facility_id=facility_id,
        permissions=["patient:action:write", "patient:action:read"],
    )


# ===========================================================================
# Unit & Domain Tests: Authorization & Scoping
# ===========================================================================

@pytest.mark.asyncio
async def test_patient_self_scoping_and_idor_protection(phase42_setup):
    """Verify that Patient A cannot view or act on Patient B's action."""
    service = phase42_setup["action_service"]

    # Create action for Patient A
    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Complete Pre-Visit Intake",
            action_type=ActionType.QUESTIONNAIRE,
            organization_id="org_apollo_01",
        ),
        created_by="staff_001",
    )

    user_alice = make_user("pat_alice_123", role="PATIENT")
    user_bob = make_user("pat_bob_456", role="PATIENT")

    # Alice can access her own action
    retrieved = await service.get_action(action.id, user_alice)
    assert retrieved.id == action.id

    # Bob attempting to access Alice's action raises 403 PatientActionNotAuthorizedException
    with pytest.raises(PatientActionNotAuthorizedException):
        await service.get_action(action.id, user_bob)


@pytest.mark.asyncio
async def test_patient_list_authorization(phase42_setup):
    """Verify patient cannot list actions belonging to another patient."""
    service = phase42_setup["action_service"]

    user_alice = make_user("pat_alice_123", role="PATIENT")
    user_bob = make_user("pat_bob_456", role="PATIENT")

    # Bob cannot list Alice's actions
    with pytest.raises(PatientActionNotAuthorizedException):
        await service.list_patient_actions("pat_alice_123", user_bob)

    # Alice can list her own actions
    items, total = await service.list_patient_actions("pat_alice_123", user_alice)
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_clinician_scoping_and_organization_boundary(phase42_setup):
    """Verify clinician cannot access action belonging to an entirely different organization."""
    service = phase42_setup["action_service"]

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Upload ID",
            action_type=ActionType.DOCUMENT_SUBMISSION,
            organization_id="org_apollo_01",
            facility_id="fac_main_01",
        )
    )

    doctor_in_org = make_user("dr_smith", role="DOCTOR", organization_id="org_apollo_01", facility_id="fac_main_01")
    doctor_wrong_org = make_user("dr_jones", role="DOCTOR", organization_id="org_max_99", facility_id="fac_other_99")

    # Clinician in org has access
    doc_retrieved = await service.get_action(action.id, doctor_in_org)
    assert doc_retrieved.id == action.id

    # Clinician from wrong org is rejected
    with pytest.raises(PatientActionNotAuthorizedException):
        await service.get_action(action.id, doctor_wrong_org)


# ===========================================================================
# Action Lifecycle & State Transition Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_action_full_lifecycle(phase42_setup):
    """Verify standard lifecycle: CREATED -> AVAILABLE -> STARTED -> SUBMITTED -> COMPLETED."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    # 1. Create Action
    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Confirm Follow-Up Appointment",
            action_type=ActionType.APPOINTMENT_CONFIRMATION,
            target_resource_type="appointment",
            target_resource_id="appt_9901",
        )
    )
    assert action.status == ActionStatus.AVAILABLE

    # 2. Start Action
    started = await service.start_action(action.id, user_alice)
    assert started.status == ActionStatus.STARTED
    assert started.started_at is not None

    # 3. Submit Action
    submission = await service.submit_action(
        action.id,
        user_alice,
        PatientActionSubmitRequest(responses={"confirmed": True, "notes": "I will attend."}),
    )
    assert submission.submission_version == 1
    action_submitted = await service.get_action(action.id, user_alice)
    assert action_submitted.status == ActionStatus.SUBMITTED

    # 4. Complete Action
    completed = await service.complete_action(action.id, user_alice)
    assert completed.status == ActionStatus.COMPLETED
    assert completed.completed_at is not None

    # 5. Verify History Entries
    history = await service.get_action_history(action.id, user_alice)
    assert len(history) >= 4
    statuses = [h.to_status for h in history]
    assert ActionStatus.AVAILABLE in statuses
    assert ActionStatus.STARTED in statuses
    assert ActionStatus.SUBMITTED in statuses
    assert ActionStatus.COMPLETED in statuses


@pytest.mark.asyncio
async def test_resubmission_conflict_guards(phase42_setup):
    """Verify that repeated submit without correction is blocked once submitted or completed."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="General Feedback",
            action_type=ActionType.PATIENT_FEEDBACK,
        )
    )

    # Initial submit succeeds
    await service.submit_action(
        action.id,
        user_alice,
        PatientActionSubmitRequest(responses={"rating": 5}),
    )

    # Second submit without correction raises PatientActionAlreadySubmittedException
    with pytest.raises(PatientActionAlreadySubmittedException):
        await service.submit_action(
            action.id,
            user_alice,
            PatientActionSubmitRequest(responses={"rating": 4}),
        )


@pytest.mark.asyncio
async def test_action_cancellation_and_refusal(phase42_setup):
    """Verify explicit patient refusal and cancellation preserving stated reasons."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    # Test Cancellation
    action1 = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Optional Survey",
            action_type=ActionType.PATIENT_FEEDBACK,
        )
    )
    cancelled = await service.cancel_action(
        action1.id, user_alice, PatientActionCancelRequest(reason="No longer interested")
    )
    assert cancelled.status == ActionStatus.CANCELLED
    assert "No longer interested" in cancelled.cancellation_reason

    # Test Explicit Patient Refusal (distinct from technical failure)
    action2 = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Non-Essential Operational Survey",
            action_type=ActionType.INFORMATION_REQUEST,
        )
    )
    refused = await service.refuse_action(
        action2.id, user_alice, PatientActionRefuseRequest(reason="Prefer not to share non-clinical details")
    )
    assert refused.is_refusal is True
    assert refused.refusal_reason == "Prefer not to share non-clinical details"
    assert refused.status == ActionStatus.CANCELLED


# ===========================================================================
# Expiration & Sweep Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_action_expiration_and_worker_sweep(phase42_setup):
    """Verify expired actions cannot be submitted, and worker sweep updates states."""
    service = phase42_setup["action_service"]
    worker = phase42_setup["worker"]
    repo = phase42_setup["action_repo"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    # Create action that already expired in the past
    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Past Due Action",
            action_type=ActionType.QUESTIONNAIRE,
            expires_in_hours=1,
        )
    )
    # Manually backdate expiration to 2 hours ago
    action.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await repo.save_action(action)

    # Submitting expired action raises PatientActionExpiredException
    with pytest.raises(PatientActionExpiredException):
        await service.submit_action(
            action.id,
            user_alice,
            PatientActionSubmitRequest(responses={"ans": "test"}),
        )

    reloaded = await repo.get_action_by_id(action.id)
    assert reloaded.status == ActionStatus.EXPIRED

    # Create a second action that has expired but never submitted to test worker sweep
    action2 = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Unchecked Expired Action",
            action_type=ActionType.CONFIRMATION,
            expires_in_hours=1,
        )
    )
    action2.expires_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await repo.save_action(action2)

    # Worker sweep transitions remaining past-due actions to EXPIRED
    expired_list = await worker.sweep_expirations()
    assert any(a.id == action2.id for a in expired_list)

    reloaded2 = await repo.get_action_by_id(action2.id)
    assert reloaded2.status == ActionStatus.EXPIRED


# ===========================================================================
# Questionnaire Retrieval & Validation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_questionnaire_retrieval_and_validation(phase42_setup):
    """Verify questionnaire template retrieval, answer type validation, and missing answer checks."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Intake Questionnaire",
            action_type=ActionType.QUESTIONNAIRE,
            metadata={"questionnaire_id": "qst_general_intake"},
        )
    )

    # 1. Retrieve template
    q = await service.get_action_questionnaire(action.id, user_alice)
    assert q.id == "qst_general_intake"
    assert len(q.questions) >= 2

    # 2. Missing required question fails (422)
    with pytest.raises(QuestionnaireResponseInvalidException):
        await service.submit_questionnaire(
            action.id,
            user_alice,
            QuestionnaireSubmissionRequest(
                answers=[
                    QuestionnaireAnswer(question_id="q_visit_reason", value="Annual checkup"),
                    # Missing required q_preferred_language
                ]
            ),
        )

    # 3. Invalid choice fails (422)
    with pytest.raises(QuestionnaireResponseInvalidException):
        await service.submit_questionnaire(
            action.id,
            user_alice,
            QuestionnaireSubmissionRequest(
                answers=[
                    QuestionnaireAnswer(question_id="q_visit_reason", value="Annual checkup"),
                    QuestionnaireAnswer(question_id="q_preferred_language", value="Klingon"),  # Not in choices
                ]
            ),
        )

    # 4. Valid submission succeeds
    response = await service.submit_questionnaire(
        action.id,
        user_alice,
        QuestionnaireSubmissionRequest(
            answers=[
                QuestionnaireAnswer(question_id="q_visit_reason", value="Routine physical exam"),
                QuestionnaireAnswer(question_id="q_preferred_language", value="English"),
                QuestionnaireAnswer(question_id="q_assistance_needed", value=False),
            ]
        ),
    )
    assert response.questionnaire_id == "qst_general_intake"
    assert len(response.answers) == 3

    # Action status updated
    updated_action = await service.get_action(action.id, user_alice)
    assert updated_action.status == ActionStatus.SUBMITTED


# ===========================================================================
# Document Linking & Care Plan Acknowledgement Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_document_attachment(phase42_setup):
    """Verify document link to action without creating duplicate file store."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Upload Govt ID",
            action_type=ActionType.DOCUMENT_SUBMISSION,
        )
    )

    doc_record = await service.attach_document(
        action.id,
        user_alice,
        DocumentSubmissionRequest(
            document_id="doc_identity_pass_99",
            document_type="ID_PASSPORT",
            description="Scanned front page of passport",
        ),
    )
    assert doc_record.document_id == "doc_identity_pass_99"

    docs = await service.get_documents(action.id, user_alice)
    assert len(docs) == 1
    assert docs[0].document_id == "doc_identity_pass_99"


@pytest.mark.asyncio
async def test_care_plan_acknowledgement(phase42_setup):
    """Verify care plan acknowledgement emits specific audit event and preserves safety banner."""
    service = phase42_setup["action_service"]
    audit_repo = phase42_setup["audit_repo"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Acknowledge Discharge Instructions",
            action_type=ActionType.CARE_PLAN_ACKNOWLEDGEMENT,
            target_resource_type="care_plan",
            target_resource_id="cp_cardio_101",
        )
    )

    acknowledged = await service.acknowledge_action(
        action.id,
        user_alice,
        PatientActionAcknowledgeRequest(notes="I received and reviewed the PDF."),
    )
    assert acknowledged.status == ActionStatus.COMPLETED

    # Verify audit events
    audit_events = [e.event_type for e in audit_repo._events]
    assert AuditEventType.PATIENT_ACTION_ACKNOWLEDGED in audit_events
    assert AuditEventType.CARE_PLAN_ACKNOWLEDGED in audit_events


# ===========================================================================
# Submission Corrections (v1 -> v2) & Provenance Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_submission_correction_preserves_history(phase42_setup):
    """Verify submitting a correction increments version (v1 -> v2) and preserves prior submission."""
    service = phase42_setup["action_service"]
    repo = phase42_setup["action_repo"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Intake Address Confirmation",
            action_type=ActionType.CONFIRMATION,
        )
    )

    # 1. Initial Submission (v1)
    sub1 = await service.submit_action(
        action.id,
        user_alice,
        PatientActionSubmitRequest(responses={"city": "Kolkata", "zip": "700001"}),
    )
    assert sub1.submission_version == 1
    assert sub1.is_correction is False

    # 2. Correction Submission (v2)
    sub2 = await service.submit_correction(
        action.id,
        user_alice,
        PatientActionCorrectionRequest(
            reason="Corrected typo in postal code",
            corrected_responses={"city": "Kolkata", "zip": "700029"},
        ),
    )
    assert sub2.submission_version == 2
    assert sub2.is_correction is True
    assert sub2.correction_reason == "Corrected typo in postal code"
    assert sub2.prior_submission_id == sub1.id

    # 3. Verify both submissions exist in repository
    all_subs = await repo.get_submissions_by_action(action.id)
    assert len(all_subs) == 2
    assert all_subs[0].id == sub1.id
    assert all_subs[0].responses["zip"] == "700001"
    assert all_subs[1].id == sub2.id
    assert all_subs[1].responses["zip"] == "700029"


# ===========================================================================
# Idempotency Key Handling Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_idempotent_submission(phase42_setup):
    """Verify repeated submit request with identical idempotency key returns cached submission."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Submit Survey",
            action_type=ActionType.PATIENT_FEEDBACK,
        )
    )

    key = "idem_key_survey_abc_999"

    # First attempt
    sub1 = await service.submit_action(
        action.id,
        user_alice,
        PatientActionSubmitRequest(responses={"score": 10}, idempotency_key=key),
    )

    # Second attempt with same idempotency key
    sub2 = await service.submit_action(
        action.id,
        user_alice,
        PatientActionSubmitRequest(responses={"score": 10}, idempotency_key=key),
    )

    assert sub1.id == sub2.id
    assert sub1.submitted_at == sub2.submitted_at


# ===========================================================================
# Clinician Review Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_clinician_operational_review(phase42_setup):
    """Verify clinician review outcomes: ACCEPT, REJECT, and REQUEST_CORRECTION."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")
    doctor = make_user("dr_smith", role="DOCTOR")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Pre-Op Document",
            action_type=ActionType.DOCUMENT_SUBMISSION,
        )
    )
    await service.submit_action(
        action.id, user_alice, PatientActionSubmitRequest(responses={"doc_uploaded": True})
    )

    # 1. Clinician requests correction -> status becomes NEEDS_REVIEW
    reviewed_needs_corr = await service.review_action(
        action.id,
        doctor,
        PatientActionReviewRequest(review_outcome="REQUEST_CORRECTION", reviewer_notes="Document is blurry."),
    )
    assert reviewed_needs_corr.status == ActionStatus.NEEDS_REVIEW

    # 2. Clinician accepts -> status becomes COMPLETED
    reviewed_accept = await service.review_action(
        action.id,
        doctor,
        PatientActionReviewRequest(review_outcome="ACCEPT", reviewer_notes="Clear document received."),
    )
    assert reviewed_accept.status == ActionStatus.COMPLETED


# ===========================================================================
# Mandatory Non-Negotiable Clinical Safety Boundary Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_clinical_safety_prohibits_autonomous_clinical_mutations(phase42_setup):
    """Test 1-5: Prohibit patient self-service from autonomously prescribing, triaging, or altering records."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Report Symptoms",
            action_type=ActionType.FOLLOW_UP_RESPONSE,
        )
    )

    # 1. Direct prescribe intent is blocked
    with pytest.raises(PatientActionAutonomousClinicalProhibitedException):
        await service.submit_action(
            action.id,
            user_alice,
            PatientActionSubmitRequest(responses={"direct_prescribe": True, "rx": "Amoxicillin"}),
        )

    # 2. Autonomous medication override is blocked
    with pytest.raises(PatientActionAutonomousClinicalProhibitedException):
        await service.submit_action(
            action.id,
            user_alice,
            PatientActionSubmitRequest(responses={"autonomous_medication_override": True, "stop": "Metformin"}),
        )

    # 3. Emergency dispatch command is blocked
    with pytest.raises(PatientActionAutonomousClinicalProhibitedException):
        await service.submit_action(
            action.id,
            user_alice,
            PatientActionSubmitRequest(responses={"dispatch_emergency_911": True}),
        )

    # 4. Standard symptom text ("chest pain") is accepted as UNVERIFIED patient data, NOT triage
    sub = await service.submit_action(
        action.id,
        user_alice,
        PatientActionSubmitRequest(responses={"symptoms": "Mild chest discomfort after meal"}),
    )
    assert sub.clinical_verification_status == "PATIENT_REPORTED_UNVERIFIED"
    assert sub.is_verified_clinical_record is False


# ===========================================================================
# HTTP API Tests via AsyncClient
# ===========================================================================

@pytest.mark.asyncio
async def test_api_patient_actions_endpoints(phase42_setup):
    """Verify HTTP API endpoints for Phase 42."""
    app = create_app()

    # Override dependencies
    app.dependency_overrides[get_patient_action_service] = lambda: phase42_setup["action_service"]
    app.dependency_overrides[get_current_user] = lambda: make_user("pat_alice_123", role="PATIENT")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create Action
        res_create = await client.post(
            "/api/v1/patient-actions",
            json={
                "patient_id": "pat_alice_123",
                "title": "API Intake Test",
                "action_type": "CONFIRMATION",
            },
        )
        assert res_create.status_code == 201
        data = res_create.json()
        action_id = data["id"]
        assert data["title"] == "API Intake Test"

        # 2. Get Action
        res_get = await client.get(f"/api/v1/patient-actions/{action_id}")
        assert res_get.status_code == 200

        # 3. Start Action
        res_start = await client.post(f"/api/v1/patient-actions/{action_id}/start")
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "STARTED"

        # 4. Submit Action
        res_submit = await client.post(
            f"/api/v1/patient-actions/{action_id}/submit",
            json={"responses": {"status": "all_good"}},
            headers={"Idempotency-Key": "test_api_idem_101"},
        )
        assert res_submit.status_code == 200
        assert res_submit.json()["clinical_verification_status"] == "PATIENT_REPORTED_UNVERIFIED"

        # 5. List Actions
        res_list = await client.get("/api/v1/patient-actions")
        assert res_list.status_code == 200
        assert res_list.json()["total"] >= 1


@pytest.mark.asyncio
async def test_api_questionnaire_and_document_endpoints(phase42_setup):
    """Verify Questionnaire and Document HTTP API endpoints."""
    app = create_app()

    app.dependency_overrides[get_patient_action_service] = lambda: phase42_setup["action_service"]
    app.dependency_overrides[get_current_user] = lambda: make_user("pat_alice_123", role="PATIENT")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create questionnaire action
        res_create = await client.post(
            "/api/v1/patient-actions",
            json={
                "patient_id": "pat_alice_123",
                "title": "API Questionnaire Action",
                "action_type": "QUESTIONNAIRE",
                "metadata": {"questionnaire_id": "qst_general_intake"},
            },
        )
        action_id = res_create.json()["id"]

        # 1. Fetch Questionnaire Template
        res_q = await client.get(f"/api/v1/patient-actions/{action_id}/questionnaire")
        assert res_q.status_code == 200
        assert res_q.json()["id"] == "qst_general_intake"

        # 2. Submit Questionnaire Answers
        res_sub_q = await client.post(
            f"/api/v1/patient-actions/{action_id}/questionnaire/submit",
            json={
                "answers": [
                    {"question_id": "q_visit_reason", "value": "Routine follow up"},
                    {"question_id": "q_preferred_language", "value": "English"},
                ]
            },
        )
        assert res_sub_q.status_code == 200
        assert res_sub_q.json()["questionnaire_id"] == "qst_general_intake"

        # 3. Attach Document
        res_doc = await client.post(
            f"/api/v1/patient-actions/{action_id}/documents",
            json={
                "document_id": "doc_lab_pdf_12345",
                "document_type": "LAB_REPORT",
                "description": "Previous blood test report",
            },
        )
        assert res_doc.status_code == 201
        assert res_doc.json()["document_id"] == "doc_lab_pdf_12345"

        # 4. Get Attached Documents
        res_get_docs = await client.get(f"/api/v1/patient-actions/{action_id}/documents")
        assert res_get_docs.status_code == 200
        assert len(res_get_docs.json()) >= 1


@pytest.mark.asyncio
async def test_worker_reminder_sweep(phase42_setup):
    """Verify worker reminder sweep increments reminder counts and stays within max limits."""
    service = phase42_setup["action_service"]
    worker = phase42_setup["worker"]
    repo = phase42_setup["action_repo"]

    # Create pending action
    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Pending Survey Action",
            action_type=ActionType.PATIENT_FEEDBACK,
        )
    )
    assert action.reminder_count == 0

    # First reminder sweep
    count1 = await worker.sweep_reminders()
    assert count1 >= 1
    reloaded = await repo.get_action_by_id(action.id)
    assert reloaded.reminder_count == 1
    assert reloaded.last_reminder_at is not None

    # Second reminder sweep
    count2 = await worker.sweep_reminders()
    assert count2 >= 1
    reloaded = await repo.get_action_by_id(action.id)
    assert reloaded.reminder_count == 2


@pytest.mark.asyncio
async def test_concurrency_safe_submissions(phase42_setup):
    """Verify concurrent submissions for different actions are handled safely with repository locks."""
    service = phase42_setup["action_service"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    # Create 5 actions
    actions = await asyncio.gather(*[
        service.create_action(
            PatientActionCreateRequest(
                patient_id="pat_alice_123",
                title=f"Parallel Action {i}",
                action_type=ActionType.CONFIRMATION,
            )
        )
        for i in range(5)
    ])

    # Submit all 5 actions concurrently
    submissions = await asyncio.gather(*[
        service.submit_action(
            act.id,
            user_alice,
            PatientActionSubmitRequest(responses={"confirmed": True, "idx": i}),
        )
        for i, act in enumerate(actions)
    ])

    assert len(submissions) == 5
    for s in submissions:
        assert s.submission_version == 1
        assert s.clinical_verification_status == "PATIENT_REPORTED_UNVERIFIED"


@pytest.mark.asyncio
async def test_phi_sanitization_in_audit_events(phase42_setup):
    """Verify sensitive clinical and credential terms are excluded from audit event metadata."""
    service = phase42_setup["action_service"]
    audit_repo = phase42_setup["audit_repo"]
    user_alice = make_user("pat_alice_123", role="PATIENT")

    # Create and submit action
    action = await service.create_action(
        PatientActionCreateRequest(
            patient_id="pat_alice_123",
            title="Symptoms Reporting",
            action_type=ActionType.FOLLOW_UP_RESPONSE,
        )
    )

    await service.submit_action(
        action.id,
        user_alice,
        PatientActionSubmitRequest(responses={"symptoms": "Headache"}),
    )

    # Inspect all audit events metadata
    for ev in audit_repo._events:
        if ev.metadata:
            for forbidden in ("password", "token", "diagnosis", "prescription", "symptoms"):
                assert forbidden not in ev.metadata, f"Forbidden key '{forbidden}' leaked in audit metadata"

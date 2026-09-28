"""Comprehensive Test Suite for Phase 24: Advanced Data Privacy, Retention & Governance.

Verifies:
- Data classification and centralized PHI detection
- PHI-safe log sanitization and telemetry label hygiene
- Context-sensitive data minimization (OCR, Medication Safety, AI, Exports)
- Purpose-aware privacy access evaluation and fail-closed boundaries
- Configurable retention management and legal preservation holds
- Controlled deletion safety: uncertainty fail-closed, dependency blocking, hold blocking
- Patient data export assembly across JSON, CSV, and FHIR formats
- Ephemeral download credentials and automated expiration purging
- De-identification transformations (date shifting, text redaction, generalization)
- Cryptographic HMAC pseudonymization with protected mapping
- Background worker task execution for Phase 24 jobs
- REST API endpoint contracts, role-based controls, and IDOR prevention
"""

import pytest
import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import (
    DataExportExpiredException,
    DataExportUnauthorizedException,
    DeletionDependencyConflictException,
    DeletionUncertainPolicyException,
    LegalHoldActiveException,
    PrivacyPolicyDeniedException,
    PrivacyPurposeRequiredException,
)
from app.core.privacy import (
    DataClassification,
    DataProcessingPurpose,
    classify_data,
    format_safe_client_error,
    is_highly_sensitive,
    is_phi,
    is_security_sensitive,
    minimize_for_ai,
    minimize_for_export,
    minimize_for_medication_safety,
    minimize_for_ocr,
    sanitize_for_logging,
    sanitize_for_telemetry,
)
from app.integrations.storage.local_storage import LocalDocumentStorage
from app.main import app
from app.repositories.allergy_repository import AllergyRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.clinical_history_repository import ClinicalHistoryRepository
from app.repositories.consent_repository import ConsentRepository
from app.repositories.document_repository import DocumentRecord, DocumentRepository
from app.repositories.encounter_repository import EncounterRepository
from app.repositories.interoperability_repository import InteroperabilityRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.patient_repository import PatientRecord, PatientRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.triage_repository import TriageRepository
from app.repositories.vitals_repository import VitalsRepository
from app.schemas.auth import UserRole
from app.schemas.data_export import (
    DataExportRequest,
    ExportFormat,
    ExportScope,
    ExportStatus,
)
from app.schemas.document import DocumentLifecycleState, DocumentSource, DocumentType, ProcessingStatus
from app.schemas.job import JobRecord, JobStatus, JobType
from app.schemas.patient import BiologicalSex, PatientStatus
from app.schemas.privacy import (
    HoldType,
    LegalHoldCreateRequest,
    LineageStage,
    RetentionPolicy,
    RetentionStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.data_export_service import DataExportService
from app.services.deidentification_service import DeidentificationService
from app.services.privacy_service import PrivacyService
from app.services.pseudonymization_service import PseudonymizationService
from app.services.retention_service import RetentionService
from app.workers.tasks import get_task_handler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_repo():
    return AuditRepository()


@pytest.fixture
def consent_repo():
    return ConsentRepository()


@pytest.fixture
def patient_repo():
    repo = PatientRepository()
    # Seed patient 1
    p1 = PatientRecord(
        id="pat-test-001",
        user_id="usr-pat-001",
        first_name="Alice",
        last_name="Tester",
        date_of_birth=date(1990, 5, 20),
        sex=BiologicalSex.FEMALE,
        status=PatientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        phone="+15551234567",
        email="alice@example.com",
    )
    repo._patients[p1.id] = p1
    repo._user_to_patient[p1.user_id] = p1.id

    # Seed patient 2
    p2 = PatientRecord(
        id="pat-test-002",
        user_id="usr-pat-002",
        first_name="Bob",
        last_name="Tester",
        date_of_birth=date(1982, 11, 14),
        sex=BiologicalSex.MALE,
        status=PatientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        phone="+15559876543",
        email="bob@example.com",
    )
    repo._patients[p2.id] = p2
    repo._user_to_patient[p2.user_id] = p2.id
    return repo


@pytest.fixture
def doc_repo():
    return DocumentRepository()


@pytest.fixture
def storage():
    return LocalDocumentStorage(use_memory=True)


@pytest.fixture
def privacy_service(audit_repo, consent_repo, patient_repo):
    return PrivacyService(
        audit_repository=audit_repo,
        consent_repository=consent_repo,
        patient_repository=patient_repo,
    )


@pytest.fixture
def retention_service(audit_repo, doc_repo, patient_repo, storage):
    return RetentionService(
        audit_repository=audit_repo,
        document_repository=doc_repo,
        patient_repository=patient_repo,
        storage_adapter=storage,
    )


@pytest.fixture
def export_service(audit_repo, patient_repo, doc_repo, consent_repo, storage):
    return DataExportService(
        audit_repository=audit_repo,
        patient_repository=patient_repo,
        document_repository=doc_repo,
        allergy_repository=AllergyRepository(),
        clinical_history_repository=ClinicalHistoryRepository(),
        encounter_repository=EncounterRepository(),
        vitals_repository=VitalsRepository(),
        medication_repository=MedicationRepository(),
        prescription_repository=PrescriptionRepository(),
        triage_repository=TriageRepository(),
        care_plan_repository=CarePlanRepository(),
        interoperability_repository=InteroperabilityRepository(),
        consent_repository=consent_repo,
        storage_adapter=storage,
    )


@pytest.fixture
def deid_service(audit_repo):
    return DeidentificationService(audit_repository=audit_repo)


@pytest.fixture
def pseudo_service(audit_repo):
    return PseudonymizationService(audit_repository=audit_repo)


# ---------------------------------------------------------------------------
# 1. Data Classification & PHI Detection Unit Tests
# ---------------------------------------------------------------------------

def test_data_classification_hierarchy():
    assert classify_data("system_health") == DataClassification.PUBLIC
    assert classify_data("system_metrics") == DataClassification.INTERNAL
    assert classify_data("clinician_profile") == DataClassification.CONFIDENTIAL
    assert classify_data("patient_profile") == DataClassification.PHI
    assert classify_data("medical_document") == DataClassification.PHI
    assert classify_data("clinical_notes") == DataClassification.HIGHLY_SENSITIVE_PHI
    assert classify_data("password_hash") == DataClassification.SECURITY_SENSITIVE
    # Unknown unmapped resource fails closed to HIGHLY_SENSITIVE_PHI
    assert classify_data("completely_unknown_lab_payload") == DataClassification.HIGHLY_SENSITIVE_PHI


def test_classification_predicates():
    assert is_phi(DataClassification.PHI) is True
    assert is_phi(DataClassification.HIGHLY_SENSITIVE_PHI) is True
    assert is_phi(DataClassification.PUBLIC) is False
    assert is_phi("unrecognized_class") is True  # Fail-closed

    assert is_highly_sensitive(DataClassification.HIGHLY_SENSITIVE_PHI) is True
    assert is_highly_sensitive(DataClassification.PHI) is False

    assert is_security_sensitive(DataClassification.SECURITY_SENSITIVE) is True
    assert is_security_sensitive(DataClassification.PHI) is False


def test_log_sanitization():
    payload = {
        "user_id": "usr-123",
        "first_name": "Alice",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.signature",
        "clinical_notes": "Patient diagnosed with acute pharyngitis.",
        "nested": {
            "phone": "+1-555-555-5555",
            "email": "test@domain.com",
            "safe_counter": 42,
        },
    }
    sanitized = sanitize_for_logging(payload)
    assert sanitized["password"] == "[REDACTED_PHI_OR_SECRET]"
    assert sanitized["first_name"] == "[REDACTED_PHI_OR_SECRET]"
    assert sanitized["clinical_notes"] == "[REDACTED_PHI_OR_SECRET]"
    assert sanitized["nested"]["phone"] == "[REDACTED_PHI_OR_SECRET]"
    assert sanitized["nested"]["email"] == "[REDACTED_PHI_OR_SECRET]"
    assert sanitized["nested"]["safe_counter"] == 42


def test_telemetry_sanitization():
    unsafe_labels = {
        "resource_type": "patient",
        "patient_id": "pat-99999",  # Forbidden label
        "mrn": "MRN-12345",          # Forbidden label
        "operation": "export_bundle",
        "status": "success",
    }
    safe_labels = sanitize_for_telemetry(unsafe_labels)
    assert "patient_id" not in safe_labels
    assert "mrn" not in safe_labels
    assert safe_labels["resource_type"] == "patient"
    assert safe_labels["operation"] == "export_bundle"
    assert safe_labels["status"] == "success"


def test_data_minimization_helpers():
    ocr_min = minimize_for_ocr(document_id="doc-1", storage_key="keys/doc1", job_id="job-1")
    assert ocr_min == {"document_id": "doc-1", "storage_key": "keys/doc1", "job_id": "job-1"}
    assert "patient_id" not in ocr_min

    med_safety_min = minimize_for_medication_safety(
        medications=[{"code": "Rx123", "name": "Aspirin", "dosage": "81mg", "patient_id": "pat-1"}],
        allergies=["penicillin"],
    )
    assert med_safety_min["allergies"] == ["penicillin"]
    assert "patient_id" not in med_safety_min["medications"][0]

    ai_min = minimize_for_ai("Patient contact: alice@example.com, phone 555-123-4567, SSN 123-45-6789.")
    assert "alice@example.com" not in ai_min
    assert "555-123-4567" not in ai_min
    assert "123-45-6789" not in ai_min

    full_bundle = {
        "patient_profile": {"name": "Alice"},
        "allergies": [{"substance": "Penicillin"}],
        "vitals": [{"type": "BP"}],
        "prescriptions": [{"rx": "Amoxicillin"}],
    }
    scoped = minimize_for_export(full_bundle, ["ALLERGIES"])
    assert "allergies" in scoped
    assert "prescriptions" not in scoped
    assert "patient_profile" not in scoped


def test_format_safe_client_error():
    err = format_safe_client_error("PROCESSING_FAILED", "Patient John Doe with HIV status failed.", "req-123")
    assert err["success"] is False
    assert err["error"]["code"] == "PROCESSING_FAILED"
    assert err["error"]["request_id"] == "req-123"


# ---------------------------------------------------------------------------
# 2. Privacy Policy & Access Decision Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patient_self_access_permitted(privacy_service):
    actor = AuthenticatedUserContext(
        id="usr-pat-001",
        email="alice@example.com",
        role=UserRole.PATIENT,
        is_active=True,
    )
    resp = await privacy_service.evaluate_access(
        actor=actor,
        resource_type="patient_profile",
        resource_id="pat-test-001",
        purpose=DataProcessingPurpose.CLINICAL_CARE,
        patient_id="pat-test-001",
    )
    assert resp.allowed is True
    assert resp.classification == DataClassification.PHI


@pytest.mark.asyncio
async def test_patient_cross_access_denied(privacy_service):
    actor = AuthenticatedUserContext(
        id="usr-pat-001",  # Alice
        email="alice@example.com",
        role=UserRole.PATIENT,
        is_active=True,
    )
    with pytest.raises(PrivacyPolicyDeniedException):
        await privacy_service.evaluate_access(
            actor=actor,
            resource_type="patient_profile",
            resource_id="pat-test-002",  # Bob's ID
            purpose=DataProcessingPurpose.CLINICAL_CARE,
            patient_id="pat-test-002",
        )


@pytest.mark.asyncio
async def test_missing_purpose_fails_closed(privacy_service):
    actor = AuthenticatedUserContext(
        id="usr-pat-001",
        email="alice@example.com",
        role=UserRole.PATIENT,
        is_active=True,
    )
    with pytest.raises(PrivacyPurposeRequiredException):
        await privacy_service.evaluate_access(
            actor=actor,
            resource_type="patient_profile",
            resource_id="pat-test-001",
            purpose=None,  # Missing purpose!
            patient_id="pat-test-001",
        )


@pytest.mark.asyncio
async def test_admin_direct_clinical_care_access_denied(privacy_service):
    admin = AuthenticatedUserContext(
        id="usr-admin-001",
        email="admin@healthsetu.internal",
        role=UserRole.ADMIN,
        is_active=True,
    )
    with pytest.raises(PrivacyPolicyDeniedException):
        await privacy_service.evaluate_access(
            actor=admin,
            resource_type="clinical_notes",
            resource_id="note-123",
            purpose=DataProcessingPurpose.CLINICAL_CARE,  # Admin cannot do clinical care
            patient_id="pat-test-001",
        )


@pytest.mark.asyncio
async def test_lineage_tracking(privacy_service):
    rec = await privacy_service.record_lineage(
        patient_id="pat-test-001",
        resource_type="document",
        resource_id="doc-123",
        source_type="patient_upload",
        stage=LineageStage.SOURCE,
        metadata={"filename": "scan.pdf"},
    )
    assert rec.lineage_id is not None
    assert rec.stage == LineageStage.SOURCE

    lineage = privacy_service.get_lineage("doc-123")
    assert len(lineage) == 1
    assert lineage[0].resource_id == "doc-123"


# ---------------------------------------------------------------------------
# 3. Retention Management & Controlled Deletion Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retention_policy_defaults_and_lookup(retention_service):
    policy = await retention_service.get_policy("medical_document")
    assert policy is not None
    assert policy.retention_period_days == 3650
    assert policy.archive_behavior.value == "ARCHIVE"


@pytest.mark.asyncio
async def test_legal_hold_blocks_deletion(retention_service):
    # Place a hold on document
    hold = await retention_service.place_hold(
        LegalHoldCreateRequest(
            resource_type="medical_document",
            resource_id="doc-held-001",
            patient_id="pat-test-001",
            hold_type=HoldType.LEGAL_HOLD,
            reason="Litigation discovery hold",
        ),
        actor_id="admin-1",
    )
    assert hold.is_active is True

    # Check eligibility
    eligibility = await retention_service.check_deletion_eligibility(
        resource_type="medical_document",
        resource_id="doc-held-001",
    )
    assert eligibility.eligible_for_deletion is False
    assert hold.hold_id in eligibility.active_holds

    # Attempt execution must raise LegalHoldActiveException
    with pytest.raises(LegalHoldActiveException):
        await retention_service.execute_deletion(
            resource_type="medical_document",
            resource_id="doc-held-001",
            actor_id="admin-1",
            reason="Attempted deletion",
            force=True,  # Even force cannot bypass legal hold!
        )

    # Release hold
    released = await retention_service.release_hold(hold.hold_id, "admin-1")
    assert released is True

    # Now eligibility check passes hold
    eligibility_after = await retention_service.check_deletion_eligibility(
        resource_type="medical_document",
        resource_id="doc-held-001",
    )
    assert eligibility_after.eligible_for_deletion is True


@pytest.mark.asyncio
async def test_missing_policy_fails_closed(retention_service):
    with pytest.raises(DeletionUncertainPolicyException):
        await retention_service.execute_deletion(
            resource_type="unregistered_custom_resource_type",
            resource_id="custom-001",
            actor_id="admin-1",
            reason="Delete unregistered",
        )


@pytest.mark.asyncio
async def test_dependency_conflict_blocks_patient_deletion(retention_service, doc_repo):
    # Attach a document to patient
    doc = DocumentRecord(
        id="doc-dep-001",
        patient_id="pat-test-001",
        uploader_id="usr-pat-001",
        document_type=DocumentType.LAB_REPORT,
        source=DocumentSource.PATIENT_UPLOAD,
        filename="test.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        checksum_sha256="abc123hash",
        storage_key="docs/test.pdf",
        lifecycle_state=DocumentLifecycleState.UPLOADED,
        processing_status=ProcessingStatus.COMPLETED,
        is_archived=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await doc_repo.create(doc)

    # Check eligibility for patient
    eligibility = await retention_service.check_deletion_eligibility("patient", "pat-test-001")
    assert eligibility.eligible_for_deletion is False
    assert "medical_documents" in eligibility.dependent_records

    # Attempt execution raises DeletionDependencyConflictException
    with pytest.raises(DeletionDependencyConflictException):
        await retention_service.execute_deletion(
            resource_type="patient",
            resource_id="pat-test-001",
            actor_id="admin-1",
            reason="Delete patient",
            force=False,
        )


@pytest.mark.asyncio
async def test_archival_workflow(retention_service, doc_repo):
    doc = DocumentRecord(
        id="doc-archive-001",
        patient_id="pat-test-001",
        uploader_id="usr-pat-001",
        document_type=DocumentType.PRESCRIPTION,
        source=DocumentSource.PATIENT_UPLOAD,
        filename="rx.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        checksum_sha256="rxsha256",
        storage_key="docs/rx.pdf",
        lifecycle_state=DocumentLifecycleState.UPLOADED,
        processing_status=ProcessingStatus.COMPLETED,
        is_archived=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await doc_repo.create(doc)

    success = await retention_service.archive_resource(
        resource_type="medical_document",
        resource_id="doc-archive-001",
        actor_id="admin-1",
    )
    assert success is True
    assert retention_service.get_resource_status("doc-archive-001") == RetentionStatus.ARCHIVED
    persisted_doc = await doc_repo.get_by_id("doc-archive-001")
    assert persisted_doc.is_archived is True


# ---------------------------------------------------------------------------
# 4. Patient Data Export Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_data_export_json_lifecycle(export_service):
    actor = AuthenticatedUserContext(
        id="usr-pat-001",
        email="alice@example.com",
        role=UserRole.PATIENT,
        is_active=True,
    )
    # 1. Request export
    req = DataExportRequest(
        scopes=[ExportScope.FULL_AUTHORIZED_RECORD],
        format=ExportFormat.JSON,
        purpose=DataProcessingPurpose.PATIENT_DATA_EXPORT,
    )
    resp = await export_service.initiate_export(actor=actor, patient_id="pat-test-001", request=req)
    assert resp.status == ExportStatus.READY
    assert resp.download_ready is True
    assert resp.file_size_bytes is not None and resp.file_size_bytes > 0

    # 2. Status query
    status_resp = await export_service.get_export_status(actor=actor, patient_id="pat-test-001", export_id=resp.export_id)
    assert status_resp.export_id == resp.export_id
    assert status_resp.status == ExportStatus.READY

    # 3. Generate download credential
    dl_resp = await export_service.generate_download_token(actor=actor, patient_id="pat-test-001", export_id=resp.export_id)
    assert dl_resp.token is not None
    assert "/api/v1/documents/download" in dl_resp.download_url
    assert dl_resp.expires_in_seconds == 300


@pytest.mark.asyncio
async def test_data_export_csv_and_fhir(export_service):
    actor = AuthenticatedUserContext(
        id="usr-pat-001",
        email="alice@example.com",
        role=UserRole.PATIENT,
        is_active=True,
    )
    # CSV format
    csv_req = DataExportRequest(scopes=[ExportScope.ALLERGIES], format=ExportFormat.CSV)
    csv_resp = await export_service.initiate_export(actor=actor, patient_id="pat-test-001", request=csv_req)
    assert csv_resp.format == "CSV"
    assert csv_resp.status == ExportStatus.READY

    # FHIR format
    fhir_req = DataExportRequest(scopes=[ExportScope.FULL_AUTHORIZED_RECORD], format=ExportFormat.FHIR)
    fhir_resp = await export_service.initiate_export(actor=actor, patient_id="pat-test-001", request=fhir_req)
    assert fhir_resp.format == "FHIR"
    assert fhir_resp.status == ExportStatus.READY


@pytest.mark.asyncio
async def test_data_export_idor_prevention(export_service):
    alice = AuthenticatedUserContext(
        id="usr-pat-001",
        email="alice@example.com",
        role=UserRole.PATIENT,
        is_active=True,
    )
    req = DataExportRequest(scopes=[ExportScope.FULL_AUTHORIZED_RECORD], format=ExportFormat.JSON)
    # Alice attempts to export Bob's data (IDOR)
    with pytest.raises(DataExportUnauthorizedException):
        await export_service.initiate_export(actor=alice, patient_id="pat-test-002", request=req)


@pytest.mark.asyncio
async def test_export_expiration_and_purging(export_service):
    actor = AuthenticatedUserContext(
        id="usr-pat-001",
        email="alice@example.com",
        role=UserRole.PATIENT,
        is_active=True,
    )
    req = DataExportRequest(scopes=[ExportScope.FULL_AUTHORIZED_RECORD], format=ExportFormat.JSON)
    resp = await export_service.initiate_export(actor=actor, patient_id="pat-test-001", request=req)

    # Force expiration
    record = export_service._exports[resp.export_id]
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    # Download attempt on expired export raises DataExportExpiredException
    with pytest.raises(DataExportExpiredException):
        await export_service.generate_download_token(actor=actor, patient_id="pat-test-001", export_id=resp.export_id)

    # Purge
    purged_count = await export_service.purge_expired_exports()
    assert purged_count == 1
    assert record.status == ExportStatus.PURGED


# ---------------------------------------------------------------------------
# 5. De-identification & Pseudonymization Unit Tests
# ---------------------------------------------------------------------------

def test_deidentification_redaction_and_shifting(deid_service):
    record = {
        "patient_name": "Johnathan Doe",
        "email": "johndoe@example.com",
        "phone": "+1 (555) 123-4567",
        "ssn": "123-45-6789",
        "zip_code": "90210",
        "date_of_birth": "1980-05-15",
        "clinical_note": "Consultation on 2026-04-10 with Dr. Smith. Patient email jsmith@hospital.org.",
    }
    deidentified = deid_service.deidentify_record(record, date_shift_days=-10)

    assert deidentified["patient_name"] == "[REDACTED_NAME]"
    assert deidentified["email"] == "[REDACTED_EMAIL]"
    assert deidentified["phone"] == "[REDACTED_PHONE]"
    assert deidentified["ssn"] == "[REDACTED_NATIONAL_ID]"
    assert deidentified["zip_code"] == "902**"
    assert deidentified["date_of_birth"] == "1980-05-05"  # Shifted 10 days earlier
    assert "2026-04-10" not in deidentified["clinical_note"]
    assert "jsmith@hospital.org" not in deidentified["clinical_note"]

    # Mandatory legal disclaimer metadata
    meta = deidentified["_deidentification_metadata"]
    assert meta["deidentified"] is True
    assert meta["legal_certification"] is False


def test_pseudonymization_deterministic_and_reversible(pseudo_service):
    id1 = "pat-12345"
    id2 = "pat-67890"

    pseudo1_a = pseudo_service.pseudonymize(id1)
    pseudo1_b = pseudo_service.pseudonymize(id1)
    pseudo2 = pseudo_service.pseudonymize(id2)

    # Determinism
    assert pseudo1_a == pseudo1_b
    assert pseudo1_a.startswith("pseudo_")
    # Collision-free distinction
    assert pseudo1_a != pseudo2

    # Custodian Re-identification
    original = pseudo_service.reidentify(pseudo1_a, actor_id="admin-auditor", reason="Regulatory Audit")
    assert original == id1


# ---------------------------------------------------------------------------
# 6. Async Worker Tasks Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_task_handlers_registered(export_service, retention_service, deid_service, pseudo_service):
    # Verify task handler registration
    data_exp_handler = get_task_handler(JobType.DATA_EXPORT)
    assert data_exp_handler is not None

    retention_handler = get_task_handler(JobType.RETENTION_EVALUATION)
    assert retention_handler is not None

    deid_handler = get_task_handler(JobType.DEIDENTIFICATION)
    assert deid_handler is not None

    pseudo_handler = get_task_handler(JobType.PSEUDONYMIZATION)
    assert pseudo_handler is not None

    # Execute dummy data export task
    job = JobRecord(
        id="job-exp-001",
        job_type=JobType.DATA_EXPORT,
        status=JobStatus.PROCESSING,
        patient_id="pat-test-001",
        resource_type="patient_data_export",
        resource_id="exp-dummy-1",
        operation_type="export_patient",
        created_at=datetime.now(timezone.utc),
    )
    res = await data_exp_handler(job, {"data_export_service": export_service})
    assert res["status"] in ("READY", "COMPLETED")


# ---------------------------------------------------------------------------
# 7. FastAPI REST API Endpoint Tests
# ---------------------------------------------------------------------------

client = TestClient(app)


def test_api_public_privacy_policy():
    response = client.get("/api/v1/privacy/data-access-policy")
    assert response.status_code == 200
    data = response.json()
    assert data["privacy_controls_enabled"] is True
    assert "CLINICAL_CARE" in data["supported_purposes"]
    assert "PHI" in data["classifications"]
    assert "HealthSetu Data Governance" in data["governance_framework"]


def test_api_unauthorized_data_export():
    # Without authentication token
    response = client.post(
        "/api/v1/patients/pat-test-001/data-export",
        json={"scopes": ["FULL_AUTHORIZED_RECORD"], "format": "JSON"},
    )
    assert response.status_code in (401, 403)


def test_api_metrics_includes_phase24():
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    metrics_text = response.text
    assert "privacy_policy_evaluations_total" in metrics_text
    assert "data_export_requests_total" in metrics_text
    assert "retention_evaluations_total" in metrics_text
    # Assert ZERO patient identifiers or clinical names in metrics lines
    assert "pat-test-001" not in metrics_text
    assert "pat-test-002" not in metrics_text
    assert "Alice" not in metrics_text
    assert "Tester" not in metrics_text

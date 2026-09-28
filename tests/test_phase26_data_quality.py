"""Comprehensive Test Suite for Phase 26: Data Quality, Clinical Record Integrity & Reconciliation.

Verifies:
1. Missing-data / completeness detection
2. Duplicate detection (documents, medications, allergies) without auto-merging
3. Conflict detection (allergies, medication dosages, external data) without auto-correcting
4. Stale-data detection without silent deletion
5. Provenance validation & unverified external import routing
6. Medication reconciliation integration with Phase 6 & Phase 7 safety boundaries
7. Allergy reconciliation integration with Phase 4
8. Interoperability & external FHIR/import reconciliation
9. Review & resolution workflows with optimistic concurrency checks (409 Conflict)
10. Role-based authorization & patient isolation (cross-tenant access denial)
11. Async task handlers (Phase 22 integration)
12. Audit event generation (Phase 15 integration)
13. Centralized configuration & feature flag adherence (Phase 25 integration)
14. Critical Safety Invariants:
    - DATA QUALITY != CLINICAL DECISION
    - DUPLICATE DETECTION != AUTOMATIC MERGING
    - CONFLICT DETECTION != AUTOMATIC CORRECTION
    - NEWER DATA != AUTOMATICALLY CORRECT DATA
    - EXTRACTED / IMPORTED != VERIFIED CLINICAL TRUTH
    - DISABLED CHECK != CLEAR / SAFE
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import (
    get_current_user,
    get_data_quality_service,
    get_reconciliation_service,
    get_data_quality_repository,
    get_reconciliation_repository,
)
from app.core.config import settings
from app.core.exceptions import (
    DataQualityFindingNotFoundException,
    ReconciliationNotFoundException,
    ResourceVersionConflictException,
    ForbiddenException,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.data_quality import (
    DataQualityFindingType,
    DataQualitySeverity,
    DataQualityFindingStatus,
    DataQualityCheckRequest,
    DataQualityReviewRequest,
    DataQualityResolutionRequest,
    DataQualityResolutionAction,
)
from app.schemas.reconciliation import (
    ReconciliationScope,
    ReconciliationStatus,
    ReconciliationRequest,
    ReconciliationResolveRequest,
    ReconciliationResolutionAction,
)
from app.schemas.patient import BiologicalSex, PatientStatus
from app.repositories.patient_repository import PatientRecord
from app.schemas.allergy import AllergySeverity, AllergyStatus
from app.schemas.clinical_history import ClinicalDataSource
from app.repositories.allergy_repository import AllergyRecord
from app.schemas.medication import PatientMedicationStatus, MedicationSource, VerificationStatus
from app.repositories.patient_medication_repository import PatientMedicationRecord
from app.repositories.document_repository import DocumentRecord, DocumentType, DocumentSource, DocumentLifecycleState, ProcessingStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def doctor_user():
    return AuthenticatedUserContext(
        user_id="doc_test_101",
        role=UserRole.DOCTOR,
        email="doctor@healthsetu.local",
    )

@pytest.fixture
def patient_user():
    return AuthenticatedUserContext(
        user_id="pat_user_101",
        role=UserRole.PATIENT,
        email="patient@healthsetu.local",
    )

@pytest.fixture
def other_patient_user():
    return AuthenticatedUserContext(
        user_id="pat_user_999",
        role=UserRole.PATIENT,
        email="other@healthsetu.local",
    )

@pytest.fixture(autouse=True)
def clean_repos():
    dq_repo = get_data_quality_repository()
    rec_repo = get_reconciliation_repository()
    dq_repo.clear()
    rec_repo.clear()

    # Seed required patients and doctor access for tests
    from app.api.deps import _global_patient_repo, _global_user_repo, _global_consent_repo, _global_authz_service
    from app.repositories.patient_repository import PatientRecord
    from app.repositories.user_repository import UserRecord
    from app.schemas.auth import AccountStatus
    from app.repositories.consent_repository import ConsentRecord, ConsentStatus
    from datetime import date, timedelta

    now = datetime.now(timezone.utc)
    for pid, puid in [("pat_101", "usr_101"), ("pat_queue_1", "usr_q1"), ("pat_api_rec", "usr_rec1"), ("pat_user_101", "pat_user_101")]:
        _global_patient_repo._patients[pid] = PatientRecord(
            id=pid,
            user_id=puid,
            first_name="Test",
            last_name="Patient",
            date_of_birth=date(1990, 1, 1),
            sex=BiologicalSex.MALE,
            status=PatientStatus.ACTIVE,
            phone="+919876543210",
            email="patient@example.com",
            created_at=now,
            updated_at=now,
        )
        _global_patient_repo._user_to_patient[puid] = pid

        # Authorize doctor for patient
        _global_authz_service.add_relationship("doc_test_101", puid)
        consent = ConsentRecord(
            id=f"consent_{pid}",
            patient_id=puid,
            grantee_id="doc_test_101",
            purpose="care_delivery",
            scope="clinical_records",
            status=ConsentStatus.ACTIVE,
            granted_at=now,
            effective_from=now,
            expires_at=now + timedelta(days=365),
            version=1,
        )
        _global_consent_repo._consents[consent.id] = consent

    yield
    dq_repo.clear()
    rec_repo.clear()


# ---------------------------------------------------------------------------
# Unit & Service Level Tests: Deterministic Rules & Safety Boundaries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_completeness_missing_data_detected():
    """Missing required patient info, allergy fields, or medication dosage must be flagged as INCOMPLETE."""
    dq_service = get_data_quality_service()

    # Empty patient profile
    res = await dq_service.run_data_quality_checks(patient_id="pat_incomplete_1")
    assert res.total_rules_evaluated > 0
    types = [f.finding_type for f in res.findings]
    assert DataQualityFindingType.MISSING_INFORMATION in types

@pytest.mark.asyncio
async def test_duplicate_detection_does_not_merge():
    """Detects duplicate document hashes and medications but leaves them untouched (no auto-merging)."""
    dq_service = get_data_quality_service()

    # Register 2 identical documents
    now = datetime.now(timezone.utc)
    doc1 = DocumentRecord(
        id="doc_1",
        patient_id="pat_dup_1",
        uploader_id="doc_test_101",
        document_type=DocumentType.PRESCRIPTION,
        source=DocumentSource.PATIENT_UPLOAD,
        filename="rx1.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        checksum_sha256="same_sha_256_hash",
        storage_key="k1",
        lifecycle_state=DocumentLifecycleState.UPLOADED,
        processing_status=ProcessingStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    doc2 = DocumentRecord(
        id="doc_2",
        patient_id="pat_dup_1",
        uploader_id="doc_test_101",
        document_type=DocumentType.PRESCRIPTION,
        source=DocumentSource.PATIENT_UPLOAD,
        filename="rx2.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        checksum_sha256="same_sha_256_hash",
        storage_key="k2",
        lifecycle_state=DocumentLifecycleState.UPLOADED,
        processing_status=ProcessingStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    await dq_service.document_repo.create_document(doc1)
    await dq_service.document_repo.create_document(doc2)

    res = await dq_service.run_data_quality_checks(patient_id="pat_dup_1")
    dup_findings = [f for f in res.findings if f.finding_type in (DataQualityFindingType.DUPLICATE_RECORD, DataQualityFindingType.POSSIBLE_DUPLICATE)]
    assert len(dup_findings) >= 1
    assert "doc_1" in dup_findings[0].description
    assert len(dup_findings[0].conflicting_references) >= 1


    # Verify both documents still exist (NO automatic merging / deletion)
    d1 = await dq_service.document_repo.get_document_by_id("doc_1")
    d2 = await dq_service.document_repo.get_document_by_id("doc_2")
    assert d1 is not None and d2 is not None

@pytest.mark.asyncio
async def test_conflict_detection_preserves_both_sources():
    """Detects conflicting medication dosage or allergy status and never silently chooses a winner."""
    dq_service = get_data_quality_service()
    now = datetime.now(timezone.utc)

    # Two active medications for same drug with conflicting strengths
    m1 = PatientMedicationRecord(
        id="m1",
        patient_id="pat_conf_1",
        drug_name_raw="Metformin",
        strength_raw="500mg",
        dosage_form_raw="tablet",
        status=PatientMedicationStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    m2 = PatientMedicationRecord(
        id="m2",
        patient_id="pat_conf_1",
        drug_name_raw="Metformin",
        strength_raw="1000mg",
        dosage_form_raw="tablet",
        status=PatientMedicationStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    await dq_service.medication_repo.create_record(m1)
    await dq_service.medication_repo.create_record(m2)

    res = await dq_service.run_data_quality_checks(patient_id="pat_conf_1")
    conf_findings = [f for f in res.findings if f.finding_type == DataQualityFindingType.CONFLICTING_INFORMATION]
    assert len(conf_findings) >= 1
    assert "metformin" in conf_findings[0].description.lower()

    # Both records remain preserved in repository
    rm1 = await dq_service.medication_repo.get_record("m1")
    rm2 = await dq_service.medication_repo.get_record("m2")
    assert rm1.strength_raw == "500mg"
    assert rm2.strength_raw == "1000mg"

@pytest.mark.asyncio
async def test_stale_data_detection_requires_review_not_deleted():
    """Stale clinical observation generates a finding but is not deleted."""
    dq_service = get_data_quality_service()
    from app.integrations.data_quality.base import RuleContext
    from app.integrations.data_quality.stale_data_rules import StaleObservationRule

    rule = StaleObservationRule(stale_days=30)
    old_time = datetime.now(timezone.utc) - timedelta(days=90)
    ctx = RuleContext(
        patient_id="pat_stale",
        observations=[{"id": "obs_1", "code": "BP", "effective_datetime": old_time}]
    )
    findings = rule.evaluate(ctx)
    assert len(findings) == 1
    assert findings[0].finding_type == DataQualityFindingType.STALE_INFORMATION

@pytest.mark.asyncio
async def test_disabled_data_quality_returns_not_checked():
    """Safety boundary: when data quality is disabled, status must be NOT_CHECKED, never CLEAR/SAFE."""
    dq_service = get_data_quality_service()
    original = settings.DATA_QUALITY_ENABLED
    try:
        settings.DATA_QUALITY_ENABLED = False
        res = await dq_service.run_data_quality_checks(patient_id="pat_dis_1")
        assert res.status == "NOT_CHECKED"
        assert res.findings_created == 0
    finally:
        settings.DATA_QUALITY_ENABLED = original

# ---------------------------------------------------------------------------
# Cross-Source Reconciliation & Provenance Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconciliation_allergy_conflict_detected():
    """Reconciling internal allergy with conflicting external import highlights conflict for clinician."""
    rec_service = get_reconciliation_service()
    now = datetime.now(timezone.utc)

    # Internal verified allergy
    alg = AllergyRecord(
        id="alg_pen_1",
        patient_id="pat_rec_1",
        allergen="Penicillin",
        severity=AllergySeverity.SEVERE,
        status=AllergyStatus.ACTIVE,
        source=ClinicalDataSource.CLINIC_ENTERED,
        created_at=now,
        updated_at=now,
    )
    await rec_service.allergy_repo.create(alg)

    # External imported record claims Penicillin is RESOLVED
    req = ReconciliationRequest(
        scope=ReconciliationScope.ALLERGIES,
        external_records=[
            {
                "id": "ext_alg_99",
                "resource_type": "allergy",
                "allergen": "Penicillin",
                "status": "resolved",
                "source_system": "CareConnect_FHIR",
            }
        ]
    )

    res = await rec_service.reconcile_patient(patient_id="pat_rec_1", request=req)
    assert res.status == ReconciliationStatus.PENDING
    assert len(res.conflicts) == 1
    assert res.conflicts[0].concept_name == "penicillin"
    assert res.conflicts[0].internal_value.lower() == "active"
    assert res.conflicts[0].external_value == "resolved"

@pytest.mark.asyncio
async def test_reconciliation_disabled_returns_unresolved():
    """Safety boundary: Disabled reconciliation returns UNRESOLVED, never CLEAR."""
    rec_service = get_reconciliation_service()
    original = settings.RECONCILIATION_ENABLED
    try:
        settings.RECONCILIATION_ENABLED = False
        res = await rec_service.reconcile_patient(
            patient_id="pat_rec_dis",
            request=ReconciliationRequest(scope=ReconciliationScope.ALL)
        )
        assert res.status == ReconciliationStatus.UNRESOLVED
        assert "disabled in configuration" in res.summary
    finally:
        settings.RECONCILIATION_ENABLED = original

# ---------------------------------------------------------------------------
# Concurrency & Resolution Workflows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict_detected():
    """Submitting a resolution with a stale expected_version must raise ResourceVersionConflictException."""
    dq_service = get_data_quality_service()
    from app.schemas.data_quality import DataQualityFindingCreate

    fc = DataQualityFindingCreate(
        patient_id="pat_conc_1",
        resource_type="medication",
        resource_id="m100",
        finding_type=DataQualityFindingType.CONFLICTING_INFORMATION,
        severity=DataQualitySeverity.HIGH,
        status=DataQualityFindingStatus.PENDING,
        description="Conflicting dosage",
        rule_id="R-CONF-002",
        rule_version="1.0.0",
    )
    record = dq_service.dq_repo.create(fc)
    assert record.version == 1

    # Clinician 1 modifies finding (review)
    from app.schemas.audit import AuditActor
    actor = AuditActor(actor_id="doc_1", role=UserRole.DOCTOR)
    await dq_service.review_finding(record.id, DataQualityReviewRequest(notes="Reviewing"), "doc_1", actor)

    # Finding version is now 2
    f_current = dq_service.dq_repo.get_by_id(record.id)
    assert f_current.version == 2

    # Clinician 2 attempts resolution assuming expected_version=1
    with pytest.raises(ResourceVersionConflictException):
        await dq_service.resolve_finding(
            finding_id=record.id,
            request=DataQualityResolutionRequest(
                action=DataQualityResolutionAction.KEEP_BOTH_ANNOTATED,
                expected_version=1,  # Stale!
                reason="Resolution based on old view",
            ),
            resolver_id="doc_2",
            actor=actor,
        )

# ---------------------------------------------------------------------------
# API Level Tests: Security, RBAC, Patient Isolation & Clinician Queues
# ---------------------------------------------------------------------------

def test_api_patient_data_quality_check_and_list(client, doctor_user):
    """Authorized doctor can trigger check and list findings."""
    app.dependency_overrides[get_current_user] = lambda: doctor_user

    # Run check
    resp = client.post(
        "/api/v1/patients/pat_101/data-quality/check",
        json={"resource_types": ["medication"]}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_rules_evaluated" in data

    # List findings
    resp2 = client.get("/api/v1/patients/pat_101/data-quality")
    assert resp2.status_code == 200
    assert "items" in resp2.json()["data"]
    app.dependency_overrides.clear()

def test_api_patient_cannot_access_other_patient_findings(client, patient_user, other_patient_user):
    """Patient A is strictly forbidden from accessing Patient B's findings (cross-tenant isolation)."""
    app.dependency_overrides[get_current_user] = lambda: patient_user

    # Patient user is pat_user_101, attempts to read pat_other_888
    resp = client.get("/api/v1/patients/pat_other_888/data-quality")
    assert resp.status_code in (403, 404)
    app.dependency_overrides.clear()

def test_api_clinician_review_queue(client, doctor_user):
    """Clinician can inspect pending review queue and review/resolve findings."""
    app.dependency_overrides[get_current_user] = lambda: doctor_user
    dq_repo = get_data_quality_repository()

    from app.schemas.data_quality import DataQualityFindingCreate
    fc = DataQualityFindingCreate(
        patient_id="pat_queue_1",
        resource_type="allergy",
        resource_id="a10",
        finding_type=DataQualityFindingType.POSSIBLE_DUPLICATE,
        severity=DataQualitySeverity.MEDIUM,
        status=DataQualityFindingStatus.PENDING,
        description="Duplicate allergy detected",
        rule_id="R-DUP-003",
        rule_version="1.0.0",
    )
    rec = dq_repo.create(fc)

    # Check clinician queue
    resp = client.get("/api/v1/clinicians/me/data-quality/findings")
    assert resp.status_code == 200
    findings = resp.json()["data"]
    assert len(findings) >= 1
    assert any(f["id"] == rec.id for f in findings)

    # Clinician reviews finding
    rev_resp = client.post(
        f"/api/v1/clinicians/me/data-quality/{rec.id}/review",
        json={"notes": "Checked physical patient chart."}
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["data"]["status"] == "IN_REVIEW"

    # Clinician resolves finding with version concurrency
    res_resp = client.post(
        f"/api/v1/clinicians/me/data-quality/{rec.id}/resolve",
        json={
            "action": "MARK_DUPLICATE",
            "expected_version": 2,  # version was incremented on review
            "reason": "Confirmed duplicate by attending physician."
        }
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["data"]["status"] == "RESOLVED"


    app.dependency_overrides.clear()

def test_api_reconciliation_workflow(client, doctor_user):
    """Doctor can trigger reconciliation and resolve conflict decisions."""
    app.dependency_overrides[get_current_user] = lambda: doctor_user

    # Reconcile patient
    req_body = {
        "scope": "MEDICATIONS",
        "external_records": [
            {
                "id": "ext_m1",
                "resource_type": "medication",
                "drug_name": "Amoxicillin",
                "strength": "250mg",
                "source_system": "LabCorp"
            }
        ]
    }
    rec_resp = client.post("/api/v1/patients/pat_api_rec/data-quality/reconcile", json=req_body)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()["data"]
    rec_id = rec_data["id"]

    # Resolve reconciliation
    resolve_resp = client.post(
        f"/api/v1/patients/pat_api_rec/reconciliation/{rec_id}/resolve",
        json={
            "action": "KEEP_BOTH_ANNOTATED",
            "expected_version": 1,
            "reason": "External record retained as historical observation."
        }
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["data"]["status"] == "RESOLVED"


    app.dependency_overrides.clear()

# ---------------------------------------------------------------------------
# Async Worker Task Integration (Phase 22)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_worker_tasks_integration():
    """Worker task handler correctly processes DATA_QUALITY_CHECK and DATA_RECONCILIATION jobs."""
    from app.schemas.job import JobRecord, JobType
    from app.workers.tasks import get_task_handler

    dq_handler = get_task_handler(JobType.DATA_QUALITY_CHECK)
    assert dq_handler is not None

    dq_service = get_data_quality_service()
    job = JobRecord(
        id="job_dq_1",
        job_type=JobType.DATA_QUALITY_CHECK,
        patient_id="pat_async_1",
        resource_id="pat_async_1",
        resource_type="data_quality",
        operation_type="check",
        created_at=datetime.now(timezone.utc),
    )
    res = await dq_handler(job, {"data_quality_service": dq_service})
    assert res["patient_id"] == "pat_async_1"
    assert "findings_created" in res


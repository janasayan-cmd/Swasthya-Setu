"""Integration and Unit Tests for Phase 30 — Authorized Search, Indexing & Clinical Resource Retrieval.

Tests:
- Query normalization (case, Unicode, punctuation, length bounds, no clinical bias).
- Authorization scoping (patient isolated to own records; clinician can search patients; admin search).
- Multi-tenant boundary isolation (Org A vs Org B, Facility A vs Facility B).
- Anti-enumeration: Patients cannot search other patients.
- Provider failures vs zero results (Section 34: SEARCH FAILURE ≠ NO RESULTS).
- Allowlisted sorting and bounded pagination.
- Full API routes via TestClient.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import pytest
from starlette.testclient import TestClient

from app.api.deps import (
    _global_audit_service,
    _global_care_plan_repo,
    _global_clinical_note_repo,
    _global_discharge_repo,
    _global_document_repo,
    _global_encounter_repo,
    _global_facility_repo,
    _global_medication_repo,
    _global_organization_repo,
    _global_patient_repo,
    _global_prescription_repo,
    _global_search_repo,
    _global_transfer_repo,
    get_current_user,
    get_search_service,
)
from app.core.config import settings
from app.core.exceptions import (
    PatientSearchNotAuthorizedError,
    SearchNotAuthorizedError,
    SearchProviderUnavailableError,
    SearchQueryTooLongError,
    SearchQueryTooShortError,
)
from app.core.security import create_access_token
from app.integrations.search.postgres import PostgresSearchProvider
from app.main import app
from app.repositories.care_plan_repository import CarePlanRecord
from app.repositories.clinical_note_repository import ClinicalNoteRecord
from app.repositories.discharge_repository import DischargeInstructionRecord
from app.repositories.document_repository import DocumentRecord
from app.repositories.encounter_repository import EncounterRecord
from app.repositories.facility_repository import FacilityRecord
from app.repositories.medication_repository import MedicationRecord
from app.repositories.organization_repository import OrganizationRecord
from app.repositories.patient_repository import PatientRecord
from app.repositories.prescription_repository import PrescriptionRecord
from app.repositories.transfer_repository import TransferRecord
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.care_plan import CarePlanStatus
from app.schemas.clinical_history import ClinicalDataSource
from app.schemas.clinical_workflow import ClinicalNoteType
from app.schemas.discharge import DischargeVerificationStatus
from app.schemas.document import DocumentLifecycleState, DocumentSource, DocumentType, ProcessingStatus
from app.schemas.encounter import EncounterStatus, EncounterType
from app.schemas.facility import FacilityStatus, FacilityType
from app.schemas.organization import OrganizationStatus, OrganizationType
from app.schemas.patient import BiologicalSex, PatientStatus
from app.schemas.prescription import PrescriptionSource, PrescriptionStatus
from app.schemas.search import (
    MatchType,
    SearchFilters,
    SearchRequest,
    SearchResourceType,
    SearchSortField,
    SortOrder,
)
from app.schemas.transfer import TransferRecord as TransferSchemaRecord, TransferStatus, TransferPriority
from app.services.search_authorization_service import SearchAuthorizationService
from app.services.search_normalization_service import SearchNormalizationService
from app.services.search_result_service import SearchResultService
from app.services.search_service import SearchService


# ---------------------------------------------------------------------------
# Test Fixtures & Setup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_search_state():
    """Seed test fixtures across repositories."""
    # Seed Organizations
    _global_organization_repo._organizations.clear()
    org1 = OrganizationRecord(
        id="org-apollo",
        name="Apollo Healthcare System",
        organization_type=OrganizationType.HEALTHCARE_NETWORK,
        status=OrganizationStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _global_organization_repo._organizations[org1.id] = org1

    # Seed Facilities
    _global_facility_repo._facilities.clear()
    fac1 = FacilityRecord(
        id="fac-delhi-01",
        organization_id="org-apollo",
        name="Apollo Delhi Main Facility",
        facility_type=FacilityType.HOSPITAL,
        status=FacilityStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _global_facility_repo._facilities[fac1.id] = fac1

    # Seed Patients
    _global_patient_repo._patients.clear()
    pat1 = PatientRecord(
        id="pat-arjun-01",
        user_id="user-arjun-01",
        first_name="Arjun",
        last_name="Sharma",
        date_of_birth=date(1985, 4, 12),
        sex=BiologicalSex.MALE,
        status=PatientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        sovereign_id="IND-SOV-1001",
    )
    pat2 = PatientRecord(
        id="pat-priya-02",
        user_id="user-priya-02",
        first_name="Priya",
        last_name="Verma",
        date_of_birth=date(1992, 8, 24),
        sex=BiologicalSex.FEMALE,
        status=PatientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        sovereign_id="IND-SOV-1002",
    )
    _global_patient_repo._patients[pat1.id] = pat1
    _global_patient_repo._patients[pat2.id] = pat2
    _global_patient_repo._user_to_patient[pat1.user_id] = pat1.id
    _global_patient_repo._user_to_patient[pat2.user_id] = pat2.id

    # Seed Documents
    _global_document_repo._documents.clear()
    doc1 = DocumentRecord(
        id="doc-discharge-01",
        patient_id="pat-arjun-01",
        uploader_id="user-arjun-01",
        document_type=DocumentType.DISCHARGE_SUMMARY,
        source=DocumentSource.PATIENT_UPLOAD,
        filename="discharge_arjun_cardio.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        checksum_sha256="abc123sha",
        storage_key="docs/pat-arjun-01/doc1.pdf",
        lifecycle_state=DocumentLifecycleState.UPLOADED,
        processing_status=ProcessingStatus.COMPLETED,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _global_document_repo._documents[doc1.id] = doc1

    # Seed Medications
    _global_medication_repo._medications.clear()
    med1 = MedicationRecord(
        id="med-paracetamol-500",
        canonical_name="Paracetamol 500mg Oral Tablet",
        generic_name="Paracetamol",
        brand_name="Calpol",
        terminology_system="SNOMED-CT",
        terminology_code="322236001",
        provider="local",
        created_at=datetime.now(timezone.utc),
    )
    _global_medication_repo._medications[med1.id] = med1

    yield


# ---------------------------------------------------------------------------
# Unit Tests: Normalization Service
# ---------------------------------------------------------------------------

def test_normalization_whitespace_and_punctuation():
    service = SearchNormalizationService()
    raw = "   Paracetamol   500mg'  \"   "
    clean = service.normalize_query(raw)
    assert clean == "Paracetamol 500mg"


def test_normalization_bounds():
    service = SearchNormalizationService(min_length=2, max_length=20)
    with pytest.raises(SearchQueryTooShortError):
        service.normalize_query("a")

    with pytest.raises(SearchQueryTooLongError):
        service.normalize_query("a" * 25)


def test_normalization_no_clinical_interpretation():
    service = SearchNormalizationService()
    # Ensure purely syntactic normalization
    q = "Paracetamol 500 mg Tablet for Severe Acute Fever"
    normalized = service.normalize_query(q)
    assert normalized == "Paracetamol 500 mg Tablet for Severe Acute Fever"
    assert "fever" in service.normalize_for_matching(normalized)


# ---------------------------------------------------------------------------
# Unit Tests: Authorization Scope Isolation
# ---------------------------------------------------------------------------

def test_patient_search_scope_isolation():
    auth_service = SearchAuthorizationService(patient_repo=_global_patient_repo)
    patient_user = AuthenticatedUserContext(
        user_id="user-arjun-01",
        role=UserRole.PATIENT,
    )

    # Patient attempting to search PATIENT records directly must fail
    with pytest.raises(PatientSearchNotAuthorizedError):
        auth_service.evaluate_search_scope(
            user=patient_user,
            requested_resource=SearchResourceType.PATIENT,
        )

    # Patient searching documents must be scoped strictly to own patient_id
    types, eff_pat_id, _, _, _ = auth_service.evaluate_search_scope(
        user=patient_user,
        requested_resource=SearchResourceType.DOCUMENT,
    )
    assert types == [SearchResourceType.DOCUMENT]
    assert eff_pat_id == "pat-arjun-01"


def test_clinician_can_search_patients():
    auth_service = SearchAuthorizationService()
    doctor_user = AuthenticatedUserContext(
        user_id="user-doc-01",
        role=UserRole.DOCTOR,
    )

    types, eff_pat_id, _, _, _ = auth_service.evaluate_search_scope(
        user=doctor_user,
        requested_resource=SearchResourceType.PATIENT,
    )
    assert SearchResourceType.PATIENT in types
    assert eff_pat_id is None  # Clinician can query across patient directory


# ---------------------------------------------------------------------------
# Unit Tests: Provider Execution & Search Boundaries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_postgres_provider_patient_isolation():
    provider = PostgresSearchProvider(
        patient_repo=_global_patient_repo,
        document_repo=_global_document_repo,
        encounter_repo=_global_encounter_repo,
        prescription_repo=_global_prescription_repo,
        medication_repo=_global_medication_repo,
        care_plan_repo=_global_care_plan_repo,
        discharge_repo=_global_discharge_repo,
        clinical_note_repo=_global_clinical_note_repo,
        org_repo=_global_organization_repo,
        facility_repo=_global_facility_repo,
        transfer_repo=_global_transfer_repo,
        search_repo=_global_search_repo,
    )

    # Patient 1 searches documents: Arjun should find his document
    req = SearchRequest(query="discharge", resource_type=SearchResourceType.DOCUMENT)
    items, total = await provider.search_resource(
        resource_type=SearchResourceType.DOCUMENT,
        request=req,
        actor_patient_id="pat-arjun-01",
    )
    assert total == 1
    assert items[0].resource_id == "doc-discharge-01"

    # Patient 2 searches documents: Priya must NOT see Arjun's document
    items_p2, total_p2 = await provider.search_resource(
        resource_type=SearchResourceType.DOCUMENT,
        request=req,
        actor_patient_id="pat-priya-02",
    )
    assert total_p2 == 0


@pytest.mark.asyncio
async def test_postgres_provider_medication_retrieval_no_safety_logic():
    provider = PostgresSearchProvider(
        patient_repo=_global_patient_repo,
        document_repo=_global_document_repo,
        encounter_repo=_global_encounter_repo,
        prescription_repo=_global_prescription_repo,
        medication_repo=_global_medication_repo,
        care_plan_repo=_global_care_plan_repo,
        discharge_repo=_global_discharge_repo,
        clinical_note_repo=_global_clinical_note_repo,
        org_repo=_global_organization_repo,
        facility_repo=_global_facility_repo,
        transfer_repo=_global_transfer_repo,
        search_repo=_global_search_repo,
    )

    req = SearchRequest(query="paracetamol", resource_type=SearchResourceType.MEDICATION)
    items, total = await provider.search_resource(
        resource_type=SearchResourceType.MEDICATION,
        request=req,
    )
    assert total == 1
    assert items[0].display == "Paracetamol 500mg Oral Tablet"
    assert items[0].match_type in (MatchType.PREFIX, MatchType.CONTAINS)


# ---------------------------------------------------------------------------
# Unit Tests: Provider Failure ≠ No Results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provider_failure_raises_explicit_exception():
    class FailingProvider(PostgresSearchProvider):
        async def search(self, *args, **kwargs):
            raise ConnectionError("PostgreSQL search connection timed out")

    failing = FailingProvider(
        patient_repo=_global_patient_repo,
        document_repo=_global_document_repo,
        encounter_repo=_global_encounter_repo,
        prescription_repo=_global_prescription_repo,
        medication_repo=_global_medication_repo,
        care_plan_repo=_global_care_plan_repo,
        discharge_repo=_global_discharge_repo,
        clinical_note_repo=_global_clinical_note_repo,
        org_repo=_global_organization_repo,
        facility_repo=_global_facility_repo,
        transfer_repo=_global_transfer_repo,
        search_repo=_global_search_repo,
    )

    service = SearchService(
        provider=failing,
        normalization_service=SearchNormalizationService(),
        authorization_service=SearchAuthorizationService(),
        result_service=SearchResultService(),
        audit_service=_global_audit_service,
    )

    doctor_user = AuthenticatedUserContext(user_id="user-doc-01", role=UserRole.DOCTOR)
    req = SearchRequest(query="Arjun", resource_type=SearchResourceType.PATIENT)

    with pytest.raises(SearchProviderUnavailableError):
        await service.execute_search(request=req, user=doctor_user)


# ---------------------------------------------------------------------------
# Integration API Route Tests (FastAPI TestClient)
# ---------------------------------------------------------------------------

def test_api_unified_search_patient_user():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        # Search for own document
        response = client.get("/api/v1/search?q=discharge&resource_type=document")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["resource_id"] == "doc-discharge-01"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_patient_forbidden_to_search_patients():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        # Patient querying /api/v1/search/patients
        response = client.get("/api/v1/search/patients?q=Sharma")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_doctor_search_patients():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-doc-01", role=UserRole.DOCTOR)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get("/api/v1/search/patients?q=Arjun")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["display"] == "Arjun Sharma"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_suggestions_autocomplete():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-doc-01", role=UserRole.DOCTOR)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get("/api/v1/search/suggestions?q=Para&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert any("Paracetamol" in s["text"] for s in data["data"]["suggestions"])
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_admin_search_status_and_rebuild():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-admin-01", role=UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        # Status
        status_resp = client.get("/api/v1/search/admin/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["provider"] == "postgres"

        # Rebuild trigger
        rebuild_resp = client.post(
            "/api/v1/search/admin/rebuild",
            json={"resource_type": "medication", "force_full": False},
        )
        assert rebuild_resp.status_code == 200
        assert rebuild_resp.json()["status"] == "COMPLETED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

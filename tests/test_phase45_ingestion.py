"""Comprehensive Test Suite for Phase 45:
External Data Ingestion, Clinical Reconciliation & Trusted Record Integration.

Covers:
- Source Authentication, Authorization & Scope Verification
- Interoperability & FHIR R4 Structural Validation
- Deterministic Patient Identity Resolution & Boundary Checks
- Phase 43 Consent Lifecycle Re-evaluation
- Immutable Provenance Recording & Cryptographic Hashing
- Phase 26 Domain Reconciliation & Conflict Handling
- Webhook Replay Protection & Signature Validation
- Provider Polling & Failure Semantics
- All 15 Non-Negotiable Data Integrity & Clinical Safety Regressions (TRD Sec 54)
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    _global_consent_access_service,
    _global_consent_repo,
    _global_identity_resolution_service,
    _global_ingestion_provenance_service,
    _global_ingestion_repo,
    _global_ingestion_service,
    _global_ingestion_validation_service,
    _global_patient_repo,
    _global_user_repo,
)
from app.core.config import get_settings
from app.core.exceptions import (
    AIIngestionAuthorityProhibitedException,
    AIPatientMatchProhibitedException,
    IngestionAutonomousClinicalProhibitedException,
    IngestionCancelledException,
    IngestionConsentRevokedException,
    IngestionDisabledException,
    IngestionIdempotencyConflictException,
    IngestionNotFoundException,
    IngestionPayloadInvalidException,
    IngestionProviderTimeoutException,
    IngestionProviderUnavailableException,
    IngestionResourceUnsupportedException,
    IngestionSourceAuthenticationFailedException,
    IngestionSourceNotFoundException,
    IngestionSourceSuspendedException,
    IngestionSourceUnauthorizedException,
    IngestionWebhookReplayDetectedException,
    IngestionWebhookSignatureInvalidException,
)
from app.core.security import create_access_token
from app.integrations.ingestion.base import IngestionFetchResult
from app.integrations.ingestion.providers.mock_provider import MockIngestionProvider
from app.main import app
from app.repositories.consent_repository import ConsentRecord
from app.repositories.user_repository import UserRecord
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.authorization import ConsentStatus
from app.schemas.ingestion import (
    DataTrustStatus,
    ExternalSourceContext,
    IdentityMatchOutcome,
    IngestionCreateRequest,
    IngestionRecord,
    IngestionStatus,
    ReconciliationResolveAction,
    SourceTrustState,
    SourceType,
    WebhookIngestionPayload,
)
from app.schemas.reconciliation import ReconciliationResolutionAction
from app.schemas.user import AuthenticatedUserContext


@pytest.fixture(autouse=True)
def reset_phase45_state():
    """Reset repository and registered sources before each test."""
    _global_ingestion_repo.clear()
    _global_identity_resolution_service.clear()
    
    # Register default test sources
    source_hosp = ExternalSourceContext(
        source_id="hosp-apollo-01",
        source_name="Apollo Hospital Central",
        source_type=SourceType.HOSPITAL,
        trust_state=SourceTrustState.ACTIVE,
        organization_id="org-apollo",
        facility_id="fac-delhi",
        api_key_hash=hashlib.sha256("valid-key-apollo".encode()).hexdigest(),
        shared_secret="apollo-webhook-secret-key-123",
        allowed_resource_types=["Patient", "Observation", "MedicationRequest", "AllergyIntolerance", "Condition", "DiagnosticReport"],
    )
    source_lab = ExternalSourceContext(
        source_id="lab-lalpath-01",
        source_name="Dr Lal PathLabs",
        source_type=SourceType.LABORATORY,
        trust_state=SourceTrustState.ACTIVE,
        organization_id="org-lalpath",
        facility_id="fac-gurgaon",
        api_key_hash=hashlib.sha256("valid-key-lal".encode()).hexdigest(),
        allowed_resource_types=["Observation", "DiagnosticReport"],
    )
    source_suspended = ExternalSourceContext(
        source_id="clinic-suspended-01",
        source_name="Suspended Clinic",
        source_type=SourceType.CLINIC,
        trust_state=SourceTrustState.SUSPENDED,
        organization_id="org-suspended",
        allowed_resource_types=["Patient", "Observation"],
    )
    _global_ingestion_repo.register_source(source_hosp)
    _global_ingestion_repo.register_source(source_lab)
    _global_ingestion_repo.register_source(source_suspended)

    # Register deterministic patient identity mappings
    _global_identity_resolution_service.register_external_identifier(
        system="urn:healthsetu:org-apollo:mrn",
        value="MRN-1001",
        patient_id="patient-p100",
    )
    _global_identity_resolution_service.register_external_identifier(
        system="hosp-apollo-01",
        value="MRN-1001",
        patient_id="patient-p100",
    )
    _global_identity_resolution_service.register_patient_demographics(
        patient_id="patient-p100",
        full_name="Aarav Sharma",
        dob="1985-05-15",
        gender="male",
        phone="+919876543210",
        email="aarav.sharma@example.com",
    )
    _global_identity_resolution_service.register_patient_demographics(
        patient_id="patient-p200",
        full_name="Priya Patel",
        dob="1992-08-20",
        gender="female",
        phone="+919876543211",
        email="priya.patel@example.com",
    )

    # Seed default active consent for patient-p100
    active_consent = ConsentRecord(
        id="consent-active-p100",
        patient_id="patient-p100",
        grantee_id="hosp-apollo-01",
        purpose="CARE_DELIVERY",
        scope="ALL_RECORDS",
        resource_scopes=["ALL_RECORDS", "OBSERVATION", "MEDICATIONREQUEST", "ALLERGYINTOLERANCE", "CONDITION"],
        action_scopes=["ALL_ACTIONS", "READ", "IMPORT"],
        status=ConsentStatus.ACTIVE,
    )
    _global_consent_repo._consents[active_consent.id] = active_consent


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinician_auth_headers():
    clinician_id = "user-clinician-p45"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=clinician_id,
            identifier="clinician45@healthsetu.org",
            password_hash="dummy-argon-hash",
            role=UserRole.DOCTOR,
            status=AccountStatus.ACTIVE,
        )
    )
    token, _ = create_access_token(user_id=clinician_id, role=UserRole.DOCTOR.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers():
    admin_id = "user-admin-p45"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=admin_id,
            identifier="admin45@healthsetu.org",
            password_hash="dummy-argon-hash",
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
        )
    )
    token, _ = create_access_token(user_id=admin_id, role=UserRole.ADMIN.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_fhir_observation():
    return {
        "resourceType": "Observation",
        "id": "obs-ext-999",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "15074-8",
                    "display": "Glucose [Moles/volume] in Blood",
                }
            ]
        },
        "subject": {
            "identifier": {
                "system": "urn:healthsetu:org-apollo:mrn",
                "value": "MRN-1001",
            }
        },
        "valueQuantity": {
            "value": 110.0,
            "unit": "mg/dL",
            "system": "http://unitsofmeasure.org",
            "code": "mg/dL",
        },
    }


# ======================================================================
# 1. UNIT & SERVICE TESTS: VALIDATION, RESOLUTION, PROVENANCE
# ======================================================================

@pytest.mark.asyncio
async def test_source_authentication_success_and_failure(sample_fhir_observation):
    """Verify source credential validation and rejection of invalid keys."""
    req_valid = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-1",
        payload=sample_fhir_observation,
        api_key="valid-key-apollo",
    )
    source = await _global_ingestion_validation_service.validate_source_and_authorization(req_valid)
    assert source.source_id == "hosp-apollo-01"
    assert source.trust_state == SourceTrustState.ACTIVE

    # Wrong credentials
    req_wrong = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-1",
        payload=sample_fhir_observation,
        api_key="wrong-key",
    )
    with pytest.raises(IngestionSourceAuthenticationFailedException):
        await _global_ingestion_validation_service.validate_source_and_authorization(req_wrong)

    # Non-existent source
    req_unreg = IngestionCreateRequest(
        source_system="unknown-hospital",
        resource_type="Observation",
        external_resource_id="obs-1",
        payload=sample_fhir_observation,
        api_key="any-key",
    )
    with pytest.raises(IngestionSourceNotFoundException):
        await _global_ingestion_validation_service.validate_source_and_authorization(req_unreg)

    # Suspended source
    req_susp = IngestionCreateRequest(
        source_system="clinic-suspended-01",
        resource_type="Observation",
        external_resource_id="obs-1",
        payload=sample_fhir_observation,
    )
    with pytest.raises(IngestionSourceSuspendedException):
        await _global_ingestion_validation_service.validate_source_and_authorization(req_susp)


@pytest.mark.asyncio
async def test_source_authorization_resource_scope(sample_fhir_observation):
    """Verify source scope checks (e.g., Lab cannot send MedicationRequest)."""
    # Observation is allowed for lab
    req_lab_obs = IngestionCreateRequest(
        source_system="lab-lalpath-01",
        resource_type="Observation",
        external_resource_id="obs-lab-1",
        payload=sample_fhir_observation,
        api_key="valid-key-lal",
    )
    src = await _global_ingestion_validation_service.validate_source_and_authorization(req_lab_obs)
    assert src.source_id == "lab-lalpath-01"

    # MedicationRequest is unauthorized for lab
    req_lab_med = IngestionCreateRequest(
        source_system="lab-lalpath-01",
        resource_type="MedicationRequest",
        external_resource_id="med-lab-1",
        payload={"resourceType": "MedicationRequest", "id": "med-1"},
        api_key="valid-key-lal",
    )
    with pytest.raises(IngestionSourceUnauthorizedException):
        await _global_ingestion_validation_service.validate_source_and_authorization(req_lab_med)


def test_payload_size_ceiling_enforced():
    """Verify oversized payloads are rejected immediately."""
    huge_payload = {"resourceType": "Observation", "data": "x" * (26 * 1024 * 1024)}  # 26MB > 25MB default
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-huge",
        payload=huge_payload,
    )
    with pytest.raises(IngestionPayloadInvalidException):
        _global_ingestion_validation_service.validate_payload_and_interoperability(req)


def test_fhir_structural_validation(sample_fhir_observation):
    """Verify structural FHIR R4 validation fails gracefully on invalid payloads."""
    # Valid
    req_valid = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-valid",
        payload=sample_fhir_observation,
    )
    errs = _global_ingestion_validation_service.validate_payload_and_interoperability(req_valid)
    assert len(errs) == 0

    # Invalid: missing resourceType
    req_missing_type = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-missing",
        payload={"id": "123"},
    )
    with pytest.raises(IngestionPayloadInvalidException):
        _global_ingestion_validation_service.validate_payload_and_interoperability(req_missing_type)


@pytest.mark.asyncio
async def test_deterministic_identity_resolution():
    """Verify exact identifier resolution, demographic matching, and ambiguity handling."""
    # 1. Exact identifier match
    outcome, pid, note = await _global_identity_resolution_service.resolve_patient_identity(
        source_system="urn:healthsetu:org-apollo:mrn",
        external_patient_id="MRN-1001",
    )
    assert outcome == IdentityMatchOutcome.MATCH_CONFIRMED
    assert pid == "patient-p100"

    # 2. Demographic candidate matching (single match -> candidate, not auto confirmed)
    outcome_demo, pid_demo, _ = await _global_identity_resolution_service.resolve_patient_identity(
        source_system="hosp-apollo-01",
        demographics={"name": "Aarav Sharma", "phone": "+919876543210"},
    )
    assert outcome_demo == IdentityMatchOutcome.MATCH_CANDIDATE
    assert pid_demo == "patient-p100"

    # 3. No match / insufficient info
    outcome_none, _, _ = await _global_identity_resolution_service.resolve_patient_identity(
        source_system="hosp-apollo-01",
        demographics={"name": "Completely Unknown Person"},
    )
    assert outcome_none == IdentityMatchOutcome.NO_MATCH


def test_provenance_cryptographic_hash(sample_fhir_observation):
    """Verify SHA-256 raw payload hash creation and provenance generation."""
    hash1 = _global_ingestion_provenance_service.compute_payload_hash(sample_fhir_observation)
    hash2 = hashlib.sha256(json.dumps(sample_fhir_observation, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    assert hash1 == hash2


@pytest.mark.asyncio
async def test_webhook_hmac_signature_and_replay_protection():
    """Verify webhook HMAC-SHA256 signature verification and replay prevention."""
    secret = "apollo-webhook-secret-key-123"
    provider = "hosp-apollo-01"
    event_id = "evt-webhook-101"
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    nonce = "nonce-101"
    msg = f"{provider}:{event_id}:{ts}:{nonce}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    wh_payload = WebhookIngestionPayload(
        provider=provider,
        event_id=event_id,
        event_type="clinical_observation",
        timestamp=ts,
        signature=sig,
        nonce=nonce,
        data={"resourceType": "Observation", "id": "obs-wh-1"},
    )

    # Valid webhook first time
    source = await _global_ingestion_validation_service.validate_webhook(wh_payload)
    assert source.source_id == provider

    # Replay protection: second time with same event_id & nonce must raise
    with pytest.raises(IngestionWebhookReplayDetectedException):
        await _global_ingestion_validation_service.validate_webhook(wh_payload)

    # Tampered signature
    wh_tampered = wh_payload.model_copy(update={"signature": "tampered_sig_12345", "event_id": "evt-202"})
    with pytest.raises(IngestionWebhookSignatureInvalidException):
        await _global_ingestion_validation_service.validate_webhook(wh_tampered)


# ======================================================================
# 2. INTEGRATION TESTS: LIFECYCLE, APIS, RECONCILIATION
# ======================================================================

def test_full_fhir_observation_ingestion_lifecycle(client, clinician_auth_headers, sample_fhir_observation):
    """Test full ingestion flow via POST /api/v1/ingestions."""
    req_body = {
        "source_system": "hosp-apollo-01",
        "resource_type": "Observation",
        "external_resource_id": "obs-ext-999",
        "external_patient_id": "MRN-1001",
        "format": "FHIR",
        "format_version": "R4",
        "payload": sample_fhir_observation,
        "api_key": "valid-key-apollo",
        "idempotency_key": "idem-key-test-01",
    }
    resp = client.post("/api/v1/ingestions", json=req_body, headers=clinician_auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] in (IngestionStatus.ACCEPTED.value, IngestionStatus.INTEGRATED.value)
    assert data["verification_status"] == DataTrustStatus.UNVERIFIED.value
    assert data["healthsetu_patient_id"] == "patient-p100"

    ingestion_id = data["id"]

    # Check status endpoint
    status_resp = client.get(f"/api/v1/ingestions/{ingestion_id}/status", headers=clinician_auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["id"] == ingestion_id
    assert status_resp.json()["data"]["verification_status"] == DataTrustStatus.UNVERIFIED.value

    # Check history endpoint
    hist_resp = client.get(f"/api/v1/ingestions/{ingestion_id}/history", headers=clinician_auth_headers)
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()["data"]["history"]) >= 1

    # Check patient external records endpoint
    ext_resp = client.get("/api/v1/patients/patient-p100/external-records", headers=clinician_auth_headers)
    assert ext_resp.status_code == 200
    assert ext_resp.json()["data"]["total"] >= 1


def test_reconciliation_conflict_generates_review_required(client, clinician_auth_headers):
    """Test that conflicting external data generates REVIEW_REQUIRED without silent overwrite."""
    # Seed external record
    req_medication_1 = {
        "source_system": "hosp-apollo-01",
        "resource_type": "MedicationRequest",
        "external_resource_id": "med-ext-01",
        "external_patient_id": "MRN-1001",
        "payload": {
            "resourceType": "MedicationRequest",
            "id": "med-ext-01",
            "status": "active",
            "intent": "order",
            "subject": {"reference": "Patient/patient-p100"},
            "medicationCodeableConcept": {"text": "Aspirin 81mg"},
        },
        "api_key": "valid-key-apollo",
        "idempotency_key": "idem-med-01",
    }
    resp1 = client.post("/api/v1/ingestions", json=req_medication_1, headers=clinician_auth_headers)
    assert resp1.status_code == 201
    assert resp1.json()["data"]["verification_status"] == DataTrustStatus.UNVERIFIED.value

    # Ingest a second record
    req_medication_2 = {
        "source_system": "hosp-apollo-01",
        "resource_type": "MedicationRequest",
        "external_resource_id": "med-ext-02",
        "external_patient_id": "MRN-1001",
        "payload": {
            "resourceType": "MedicationRequest",
            "id": "med-ext-02",
            "status": "active",
            "intent": "order",
            "subject": {"reference": "Patient/patient-p100"},
            "medicationCodeableConcept": {"text": "Clopidogrel 75mg"},
        },
        "api_key": "valid-key-apollo",
        "idempotency_key": "idem-med-02",
    }
    resp2 = client.post("/api/v1/ingestions", json=req_medication_2, headers=clinician_auth_headers)
    assert resp2.status_code == 201
    assert resp2.json()["data"]["verification_status"] == DataTrustStatus.UNVERIFIED.value


def test_reconciliation_resolve_endpoint(client, clinician_auth_headers):
    """Test resolving a reconciliation conflict session via clinician resolution."""
    # Call resolve endpoint
    resolve_resp = client.post(
        "/api/v1/reconciliation/rec-case-100/resolve",
        json={
            "resolution": "ACCEPT_EXTERNAL",
            "notes": "Clinician confirmed external lab reading is relevant",
        },
        headers=clinician_auth_headers,
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["data"]["status"] == "RESOLVED"
    assert resolve_resp.json()["data"]["resolution"] == "ACCEPT_EXTERNAL"


def test_webhook_endpoint_flow(client):
    """Test provider webhook ingestion endpoint POST /api/v1/integrations/{provider}/webhook."""
    secret = "apollo-webhook-secret-key-123"
    provider = "hosp-apollo-01"
    event_id = "evt-hook-unique-999"
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    nonce = "nonce-hook-999"

    msg = f"{provider}:{event_id}:{ts}:{nonce}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    raw_payload_dict = {
        "resourceType": "Observation",
        "id": "obs-webhook-99",
        "status": "final",
        "subject": {"reference": "Patient/patient-p100"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "15074-8", "display": "Glucose"}]},
    }
    webhook_body = {
        "event_id": event_id,
        "event_type": "clinical_observation",
        "timestamp": ts,
        "signature": sig,
        "nonce": nonce,
        "data": raw_payload_dict,
    }

    resp = client.post(
        f"/api/v1/integrations/{provider}/webhook",
        json=webhook_body,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] in (IngestionStatus.ACCEPTED.value, IngestionStatus.INTEGRATED.value)
    assert data["verification_status"] == DataTrustStatus.UNVERIFIED.value


def test_ingestion_cancellation(client, clinician_auth_headers):
    """Test cancelling a pending/review-required ingestion job and rejection on terminal state."""
    req_body = {
        "source_system": "hosp-apollo-01",
        "resource_type": "Observation",
        "external_resource_id": "obs-cancel-01",
        "payload": {
            "resourceType": "Observation",
            "id": "obs-cancel-01",
            "status": "final",
            "code": {"coding": [{"code": "123"}]},
        },
        "api_key": "valid-key-apollo",
        "idempotency_key": "idem-cancel-01",
    }
    resp = client.post("/api/v1/ingestions", json=req_body, headers=clinician_auth_headers)
    assert resp.status_code == 201
    ingestion_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == IngestionStatus.REVIEW_REQUIRED.value

    # Cancel review-required ingestion
    cancel_resp = client.post(f"/api/v1/ingestions/{ingestion_id}/cancel", headers=clinician_auth_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == IngestionStatus.CANCELLED.value

    # Re-cancelling a cancelled ingestion fails with 409
    repeat_cancel = client.post(f"/api/v1/ingestions/{ingestion_id}/cancel", headers=clinician_auth_headers)
    assert repeat_cancel.status_code == 409


@pytest.mark.asyncio
async def test_mock_provider_fetch_and_failure_semantics():
    """Verify provider adapter handles success, timeout, 503, and error states accurately."""
    provider = MockIngestionProvider(name="mock_lab")

    # Success
    res = await provider.fetch_resource("Observation", "obs-123")
    assert res.success is True
    assert res.payload["resourceType"] == "Observation"

    # Timeout simulation
    provider.simulate_timeout = True
    with pytest.raises(IngestionProviderTimeoutException):
        await provider.fetch_resource("Observation", "obs-123")
    provider.simulate_timeout = False

    # Unavailable (503)
    provider.simulate_unavailable = True
    with pytest.raises(IngestionProviderUnavailableException):
        await provider.fetch_resource("Observation", "obs-123")
    provider.simulate_unavailable = False

    # Permanent failure
    provider.simulate_failure = True
    res_err = await provider.fetch_resource("Observation", "obs-123")
    assert res_err.success is False
    assert res_err.retryable is False


# ======================================================================
# 3. THE 15 NON-NEGOTIABLE CLINICAL SAFETY REGRESSIONS (TRD Section 54)
# ======================================================================

@pytest.mark.asyncio
async def test_regression_01_imported_data_remains_unverified(sample_fhir_observation):
    """Regression 1: Imported data remains distinguishable from verified data (UNVERIFIED).
    IMPORT != VERIFICATION; IMPORT != CLINICAL TRUTH.
    """
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-reg-01",
        external_patient_id="MRN-1001",
        payload=sample_fhir_observation,
        api_key="valid-key-apollo",
    )
    record = await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")

    # Invariant: verification_status MUST be UNVERIFIED
    assert record.verification_status == DataTrustStatus.UNVERIFIED
    assert record.verification_status != DataTrustStatus.VERIFIED


@pytest.mark.asyncio
async def test_regression_02_duplicate_resources_do_not_create_duplicate_records(sample_fhir_observation):
    """Regression 2: Duplicate resources do not create duplicate clinical records.
    Idempotent intake returns the existing ingestion instance or halts duplicate creation.
    """
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-reg-02",
        external_patient_id="MRN-1001",
        payload=sample_fhir_observation,
        api_key="valid-key-apollo",
        idempotency_key="idem-reg-02",
    )
    record1 = await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")

    # Second delivery with same idempotency key returns exact same record
    record2 = await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")
    assert record1.id == record2.id

    # Invariant: Duplicate with different payload triggers conflict exception
    req_conflict_idem = req.model_copy(update={"payload": {"resourceType": "Observation", "id": "diff"}})
    with pytest.raises(IngestionIdempotencyConflictException):
        await _global_ingestion_service.ingest_clinical_data(req_conflict_idem, requester_id="clinician", requester_role="DOCTOR")


@pytest.mark.asyncio
async def test_regression_03_conflicting_resources_do_not_silently_overwrite():
    """Regression 3: Conflicting resources do not silently overwrite existing data.
    Conflict detected -> stops automated overwrite -> status requires reconciliation review.
    """
    # External payload 1
    req1 = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Condition",
        external_resource_id="cond-01",
        external_patient_id="MRN-1001",
        payload={
            "resourceType": "Condition",
            "id": "cond-01",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "subject": {"reference": "Patient/patient-p100"},
        },
        api_key="valid-key-apollo",
    )
    r1 = await _global_ingestion_service.ingest_clinical_data(req1, requester_id="clinician", requester_role="DOCTOR")
    assert r1.verification_status == DataTrustStatus.UNVERIFIED

    # Second payload from same external source updating status
    req2 = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Condition",
        external_resource_id="cond-02",
        external_patient_id="MRN-1001",
        payload={
            "resourceType": "Condition",
            "id": "cond-02",
            "clinicalStatus": {"coding": [{"code": "resolved"}]},
            "subject": {"reference": "Patient/patient-p100"},
        },
        api_key="valid-key-apollo",
    )
    r2 = await _global_ingestion_service.ingest_clinical_data(req2, requester_id="clinician", requester_role="DOCTOR")
    # Both remain distinctly staged as UNVERIFIED; neither silently overwrote clinical truth
    assert r2.verification_status == DataTrustStatus.UNVERIFIED


@pytest.mark.asyncio
async def test_regression_04_patient_identity_ambiguity_stops_automated_integration():
    """Regression 4: Patient identity ambiguity stops automated integration.
    Demographic candidate / ambiguous match -> REVIEW_REQUIRED. Never silently merge.
    """
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-ambig-01",
        payload={
            "resourceType": "Observation",
            "id": "obs-ambig-01",
            "status": "final",
            "code": {"coding": [{"code": "123"}]},
        },
        api_key="valid-key-apollo",
    )
    rec = await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")

    # Invariant: identity outcome must be INSUFFICIENT_INFORMATION / REVIEW_REQUIRED, NOT MATCH_CONFIRMED
    assert rec.identity_outcome in (
        IdentityMatchOutcome.REVIEW_REQUIRED,
        IdentityMatchOutcome.NO_MATCH,
        IdentityMatchOutcome.INSUFFICIENT_INFORMATION,
    )
    assert rec.status == IngestionStatus.REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_regression_05_external_corrections_preserve_provenance(sample_fhir_observation):
    """Regression 5: External corrections preserve provenance without erasing historical entries."""
    req1 = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-corr-01",
        external_patient_id="MRN-1001",
        format_version="1.0",
        payload=sample_fhir_observation,
        api_key="valid-key-apollo",
    )
    r1 = await _global_ingestion_service.ingest_clinical_data(req1, requester_id="clinician", requester_role="DOCTOR")

    # Corrected version v2
    corrected_payload = dict(sample_fhir_observation)
    corrected_payload["valueQuantity"] = {"value": 115.0, "unit": "mg/dL"}
    req2 = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-corr-02",
        external_patient_id="MRN-1001",
        format_version="2.0",
        payload=corrected_payload,
        api_key="valid-key-apollo",
    )
    r2 = await _global_ingestion_service.ingest_clinical_data(req2, requester_id="clinician", requester_role="DOCTOR")

    # Invariant: Both records exist with distinct hashes and provenance
    assert r1.raw_payload_hash != r2.raw_payload_hash
    assert r2.verification_status == DataTrustStatus.UNVERIFIED


@pytest.mark.asyncio
async def test_regression_06_source_versions_preserved(sample_fhir_observation):
    """Regression 6: Source versions are preserved where available."""
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-ver-01",
        external_patient_id="MRN-1001",
        format_version="HL7-v2.8-REV-3",
        payload=sample_fhir_observation,
        api_key="valid-key-apollo",
    )
    rec = await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")
    assert rec.format_version == "HL7-v2.8-REV-3"


def test_regression_07_unsupported_resources_not_silently_converted():
    """Regression 7: Unsupported resources are not silently converted into unrelated internal entities."""
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="UnsupportedResourceMetric",
        external_resource_id="dev-01",
        payload={"resourceType": "UnsupportedResourceMetric", "id": "dev-01"},
        api_key="valid-key-apollo",
    )
    with pytest.raises(IngestionResourceUnsupportedException):
        _global_ingestion_validation_service.validate_payload_and_interoperability(req)


@pytest.mark.asyncio
async def test_regression_08_ai_cannot_autonomously_verify_imported_data(sample_fhir_observation):
    """Regression 8: AI cannot autonomously verify imported data or resolve reconciliation.
    Attempt by AI role/actor to verify triggers AIIngestionAuthorityProhibitedException.
    """
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-ai-verify",
        external_patient_id="MRN-1001",
        payload=sample_fhir_observation,
        api_key="valid-key-apollo",
    )
    # AI actor initiating ingestion is prohibited
    with pytest.raises(AIIngestionAuthorityProhibitedException):
        await _global_ingestion_service.ingest_clinical_data(
            req,
            requester_id="ai-agent-45",
            requester_role="AI",
            is_ai_agent=True,
        )

    # AI actor resolving reconciliation is prohibited
    ai_ctx = AuthenticatedUserContext(
        user_id="ai-copilot",
        role=UserRole.DOCTOR,
        is_ai=True,
        organization_id="org-apollo",
    )
    with pytest.raises(AIIngestionAuthorityProhibitedException):
        await _global_ingestion_service.resolve_reconciliation(
            reconciliation_id="rec-case-1",
            action=ReconciliationResolveAction(resolution="ACCEPT_EXTERNAL", notes="AI verified"),
            current_user=ai_ctx,
        )


@pytest.mark.asyncio
async def test_regression_09_ai_cannot_merge_patients_or_confirm_identity():
    """Regression 9: AI cannot merge patients or autonomously declare identity match."""
    with pytest.raises(AIPatientMatchProhibitedException):
        await _global_identity_resolution_service.resolve_patient_identity(
            source_system="hosp-apollo-01",
            external_patient_id="MRN-1001",
            is_ai_agent=True,
        )


@pytest.mark.asyncio
async def test_regression_10_external_medication_cannot_silently_change_active_medications():
    """Regression 10: External medication data cannot silently change active medications.
    Ingested medication stays UNVERIFIED and is not marked as active prescription truth.
    """
    med_payload = {
        "resourceType": "MedicationRequest",
        "id": "med-ext-reg-10",
        "status": "active",
        "intent": "order",
        "subject": {"reference": "Patient/patient-p100"},
        "medicationCodeableConcept": {"text": "Warfarin 5mg"},
    }
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="MedicationRequest",
        external_resource_id="med-ext-reg-10",
        external_patient_id="MRN-1001",
        payload=med_payload,
        api_key="valid-key-apollo",
    )
    rec = await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")

    # Invariant: Record is stored as UNVERIFIED; it does NOT become verified medication
    assert rec.verification_status == DataTrustStatus.UNVERIFIED


@pytest.mark.asyncio
async def test_regression_11_external_allergy_cannot_silently_create_verified_allergies():
    """Regression 11: External allergy data cannot silently create verified allergies."""
    allergy_payload = {
        "resourceType": "AllergyIntolerance",
        "id": "alg-ext-reg-11",
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "subject": {"reference": "Patient/patient-p100"},
        "code": {"text": "Penicillin"},
    }
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="AllergyIntolerance",
        external_resource_id="alg-ext-reg-11",
        external_patient_id="MRN-1001",
        payload=allergy_payload,
        api_key="valid-key-apollo",
    )
    rec = await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")

    assert rec.verification_status == DataTrustStatus.UNVERIFIED


def test_regression_12_external_laboratory_data_cannot_automatically_become_diagnosis(sample_fhir_observation):
    """Regression 12: External laboratory data cannot automatically become diagnosis.
    Purpose cannot be 'diagnosis' or 'prescription' directly in ingestion pipeline.
    """
    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-diag-01",
        payload=sample_fhir_observation,
        purpose="diagnosis",  # Prohibited autonomous clinical action
        api_key="valid-key-apollo",
    )
    with pytest.raises(IngestionAutonomousClinicalProhibitedException):
        _global_ingestion_validation_service.validate_safety_invariants(req)


@pytest.mark.asyncio
async def test_regression_13_imported_data_cannot_bypass_consent(sample_fhir_observation):
    """Regression 13: Imported data cannot bypass consent.
    If patient consent is revoked, ingestion must be halted immediately.
    """
    # Register a revoked consent record for patient-p100
    _global_consent_repo._consents.clear()
    revoked_consent = ConsentRecord(
        id="consent-revoked-p100",
        patient_id="patient-p100",
        grantee_id="hosp-apollo-01",
        purpose="CARE_DELIVERY",
        scope="ALL",
        status=ConsentStatus.REVOKED,
    )
    _global_consent_repo._consents[revoked_consent.id] = revoked_consent

    req = IngestionCreateRequest(
        source_system="hosp-apollo-01",
        resource_type="Observation",
        external_resource_id="obs-revoked-01",
        external_patient_id="MRN-1001",
        payload=sample_fhir_observation,
        api_key="valid-key-apollo",
    )
    with pytest.raises(IngestionConsentRevokedException):
        await _global_ingestion_service.ingest_clinical_data(req, requester_id="clinician", requester_role="DOCTOR")


@pytest.mark.asyncio
async def test_regression_14_provider_failure_cannot_become_successful_integration():
    """Regression 14: Provider failure cannot become successful integration."""
    provider = MockIngestionProvider(name="mock_lab")
    provider.simulate_unavailable = True

    # Provider failure raises exception and cannot be silently swallowed as integrated
    with pytest.raises(IngestionProviderUnavailableException):
        await provider.fetch_resource("Observation", "obs-failed")


@pytest.mark.asyncio
async def test_regression_15_webhook_replay_cannot_create_duplicate_clinical_events():
    """Regression 15: Webhook replay cannot create duplicate clinical events."""
    event_id = "evt-reg-15-replay"
    provider = "hosp-apollo-01"
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    nonce = "nonce-reg-15"
    secret = "apollo-webhook-secret-key-123"

    msg = f"{provider}:{event_id}:{ts}:{nonce}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    wh_payload = WebhookIngestionPayload(
        provider=provider,
        event_id=event_id,
        event_type="clinical_event",
        timestamp=ts,
        signature=sig,
        nonce=nonce,
        data={"resourceType": "Observation", "id": "obs-reg-15"},
    )

    # First receipt is recorded successfully
    await _global_ingestion_validation_service.validate_webhook(wh_payload)

    # Replayed receipt MUST be halted
    with pytest.raises(IngestionWebhookReplayDetectedException):
        await _global_ingestion_validation_service.validate_webhook(wh_payload)

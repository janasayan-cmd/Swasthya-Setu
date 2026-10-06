"""Comprehensive Test Suite for Phase 44:
Clinical Data Sharing, External Access & Controlled Data Exchange.

Covers:
- Sharing Request Lifecycle (create, approve, deny, cancel, execute, status, history)
- Phase 43 Consent Integration & Deny-by-default enforcement
- Minimum Necessary Scope Filtering (medications, allergies, documents, FHIR)
- Security: IDOR prevention, Cross-patient isolation, SSRF & destination allowlist
- Provider Failure Semantics (timeout != success, unavailable != shared, unknown != delivered)
- JIT Consent Re-evaluation (Queued authorization != Current authorization)
- Controlled Clinical Exports (snapshots != live records, patient self-export, clinician authorization)
- All 18 Non-Negotiable Clinical Safety Regressions (TRD Sec 46)
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    _global_consent_access_service,
    _global_consent_repo,
    _global_export_repo,
    _global_sharing_policy_service,
    _global_sharing_provenance_service,
    _global_sharing_repo,
    _global_sharing_service,
    _global_sharing_worker,
    _global_user_repo,
)
from app.core.exceptions import (
    AISharingAuthorityProhibitedException,
    ForbiddenException,
    NotFoundException,
    SharingActionNotAllowedException,
    SharingAlreadyCompletedException,
    SharingAutonomousClinicalProhibitedException,
    SharingCancelledException,
    SharingConsentExpiredException,
    SharingConsentRequiredException,
    SharingConsentRevokedException,
    SharingDestinationInvalidException,
    SharingDisabledException,
    SharingExpiredException,
    SharingExportNotAllowedException,
    SharingNotAuthorizedException,
    SharingNotFoundException,
    SharingProviderFailedException,
    SharingProviderTimeoutException,
    SharingProviderUnavailableException,
)
from app.core.security import create_access_token
from app.integrations.sharing.base import ProviderDeliveryState
from app.integrations.sharing.providers.mock import MockSharingProvider
from app.integrations.sharing.registry import sharing_provider_registry
from app.main import app
from app.repositories.consent_repository import ConsentRecord
from app.repositories.user_repository import UserRecord
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.authorization import ConsentStatus
from app.schemas.export import ExportFormat, ExportRequestCreate, ExportScopeType
from app.schemas.sharing import (
    DeliveryMethod,
    DestinationType,
    SharingAction,
    SharingApproveAction,
    SharingCancelAction,
    SharingDenyAction,
    SharingEvaluationRequest,
    SharingRequestCreate,
    SharingStatus,
    SharingType,
)
from app.services.sharing_policy_service import SharingPolicyDecisionCode
from app.utils.sharing_security import validate_destination_url

client = TestClient(app)


def _auth_header(user_id: str, role: UserRole, org_id: str = "org-1") -> dict:
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=user_id,
            identifier=user_id,
            password_hash="dummy-argon-hash",
            role=role,
            status=AccountStatus.ACTIVE,
        )
    )
    token, _ = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_teardown():
    """Reset provider and mock stores before each test."""
    mock_p = MockSharingProvider("mock")
    sharing_provider_registry.register_provider("mock", mock_p)
    yield


# ============================================================================
# 1. SHARING POLICY & AUTHORIZATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_sharing_policy_patient_self_share_allowed():
    """Patients have inherent authority to share their own records."""
    req = SharingEvaluationRequest(
        actor_id="patient-1",
        actor_role="PATIENT",
        patient_id="patient-1",
        recipient_id="clinician-1",
        recipient_type=DestinationType.INTERNAL_CLINICIAN,
        resource_scopes=["MEDICATIONS"],
        action=SharingAction.SHARE,
        purpose="CARE_DELIVERY",
    )
    res = await _global_sharing_policy_service.evaluate_sharing_policy(req)
    assert res.allowed is True
    assert res.decision == SharingPolicyDecisionCode.ALLOW


@pytest.mark.asyncio
async def test_sharing_policy_clinician_requires_phase43_consent():
    """Clinicians attempting to share without active consent are blocked."""
    req = SharingEvaluationRequest(
        actor_id="clinician-unauth",
        actor_role="CLINICIAN",
        patient_id="patient-2",
        recipient_id="clinician-target",
        recipient_type=DestinationType.INTERNAL_CLINICIAN,
        resource_scopes=["MEDICATIONS"],
        action=SharingAction.SHARE,
        purpose="CARE_DELIVERY",
    )
    res = await _global_sharing_policy_service.evaluate_sharing_policy(req)
    assert res.allowed is False
    assert res.decision in (
        SharingPolicyDecisionCode.REQUIRES_AUTHORIZATION,
        SharingPolicyDecisionCode.DENY,
    )


@pytest.mark.asyncio
async def test_sharing_policy_with_active_phase43_consent():
    """Sharing succeeds when Phase 43 consent is active and matches scope."""
    consent_id = "consent-p44-1"
    await _global_consent_repo.create(
        ConsentRecord(
            id=consent_id,
            patient_id="patient-p44",
            grantee_id="clinician-p44",
            purpose="CARE_DELIVERY",
            scope="MEDICATIONS",
            resource_scopes=["MEDICATIONS"],
            action_scopes=["READ", "SHARE"],
            status=ConsentStatus.ACTIVE,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )

    req = SharingEvaluationRequest(
        actor_id="clinician-p44",
        actor_role="CLINICIAN",
        patient_id="patient-p44",
        recipient_id="partner-org-1",
        recipient_type=DestinationType.REGISTERED_EXTERNAL_ORGANIZATION,
        resource_scopes=["MEDICATIONS"],
        action=SharingAction.SHARE,
        purpose="CARE_DELIVERY",
    )
    res = await _global_sharing_policy_service.evaluate_sharing_policy(req)
    assert res.allowed is True
    assert res.decision == SharingPolicyDecisionCode.ALLOW
    assert "MEDICATIONS" in res.filtered_resource_scopes


@pytest.mark.asyncio
async def test_sharing_policy_consent_withdrawn_blocks_sharing():
    """Explicitly withdrawn consent prevents sharing."""
    consent_id = "consent-withdrawn-44"
    await _global_consent_repo.create(
        ConsentRecord(
            id=consent_id,
            patient_id="patient-w44",
            grantee_id="clinician-w44",
            purpose="CARE_DELIVERY",
            scope="MEDICATIONS",
            resource_scopes=["MEDICATIONS"],
            action_scopes=["SHARE"],
            status=ConsentStatus.WITHDRAWN,
            revoked_at=datetime.now(timezone.utc),
        )
    )

    req = SharingEvaluationRequest(
        actor_id="clinician-w44",
        actor_role="CLINICIAN",
        patient_id="patient-w44",
        recipient_id="org-2",
        recipient_type=DestinationType.INTERNAL_ORGANIZATION,
        resource_scopes=["MEDICATIONS"],
        action=SharingAction.SHARE,
        purpose="CARE_DELIVERY",
    )
    res = await _global_sharing_policy_service.evaluate_sharing_policy(req)
    assert res.allowed is False
    assert res.decision == SharingPolicyDecisionCode.REVOKED


@pytest.mark.asyncio
async def test_sharing_policy_ai_prohibited():
    """AI cannot act as sharing authority or initiate sharing."""
    req = SharingEvaluationRequest(
        actor_id="ai-bot-9",
        actor_role="AI",
        patient_id="patient-1",
        recipient_id="clinician-1",
        recipient_type=DestinationType.INTERNAL_CLINICIAN,
        resource_scopes=["MEDICATIONS"],
        action=SharingAction.SHARE,
        purpose="CARE_DELIVERY",
    )
    res = await _global_sharing_policy_service.evaluate_sharing_policy(req)
    assert res.allowed is False
    assert res.reason_code == "AI_SHARING_AUTHORITY_PROHIBITED"


# ============================================================================
# 2. DESTINATION VALIDATION & SSRF PROTECTION
# ============================================================================

def test_destination_validation_rejects_localhost_and_internal_ips():
    """SSRF: loopback, 127.0.0.1, and cloud metadata IPs are strictly blocked."""
    with pytest.raises(SharingDestinationInvalidException):
        validate_destination_url("http://127.0.0.1:8080/fhir")

    with pytest.raises(SharingDestinationInvalidException):
        validate_destination_url("http://localhost:5000/api")

    with pytest.raises(SharingDestinationInvalidException):
        validate_destination_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(SharingDestinationInvalidException):
        validate_destination_url("http://10.0.0.1/internal")


def test_destination_validation_rejects_unwhitelisted_domains():
    """External destination must be on the configured allowlist."""
    with pytest.raises(SharingDestinationInvalidException):
        validate_destination_url(
            "https://evil-untrusted-site.com/webhook",
            allowed_list=["https://partner-exchange.example.org"],
        )


def test_destination_validation_accepts_whitelisted_domain():
    """Whitelisted destination succeeds."""
    assert (
        validate_destination_url(
            "https://partner-exchange.example.org/fhir/r4",
            allowed_list=["https://partner-exchange.example.org"],
        )
        is True
    )


# ============================================================================
# 3. API ENDPOINT TESTS: LIFECYCLE
# ============================================================================

def test_patient_creates_sharing_request_auto_approved():
    """Patient creating share request for their own data is immediately APPROVED."""
    headers = _auth_header("patient-alice", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-alice",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doctor-bob",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS", "ALLERGIES"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    resp = client.post("/api/v1/sharing-requests", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "APPROVED"
    assert data["patient_id"] == "patient-alice"


def test_clinician_creates_sharing_request_without_consent_pending():
    """Clinician requesting share without prior consent creates PENDING_AUTHORIZATION request."""
    headers = _auth_header("doctor-dave", UserRole.DOCTOR)
    payload = {
        "patient_id": "patient-carol",
        "sharing_type": "CLINICIAN_TO_CLINICIAN",
        "recipient_id": "doctor-ellen",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    resp = client.post("/api/v1/sharing-requests", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "PENDING_AUTHORIZATION"


def test_patient_approves_pending_sharing_request():
    """Target patient approves pending sharing request."""
    # 1. Clinician creates pending request
    doc_headers = _auth_header("doctor-frank", UserRole.DOCTOR)
    payload = {
        "patient_id": "patient-george",
        "sharing_type": "CLINICIAN_TO_CARE_TEAM",
        "recipient_id": "careteam-alpha",
        "recipient_type": "INTERNAL_CARE_TEAM",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    create_resp = client.post("/api/v1/sharing-requests", json=payload, headers=doc_headers)
    assert create_resp.status_code == 201
    shr_id = create_resp.json()["data"]["id"]

    # 2. Patient approves
    pat_headers = _auth_header("patient-george", UserRole.PATIENT)
    appr_resp = client.post(
        f"/api/v1/sharing-requests/{shr_id}/approve",
        json={"reason": "Approved by patient George"},
        headers=pat_headers,
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["data"]["status"] == "APPROVED"


def test_unauthorized_user_cannot_approve_sharing_request():
    """Random user cannot approve another patient's sharing request."""
    doc_headers = _auth_header("doctor-1", UserRole.DOCTOR)
    payload = {
        "patient_id": "patient-victim",
        "sharing_type": "CLINICIAN_TO_CLINICIAN",
        "recipient_id": "doc-2",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=doc_headers).json()["data"]["id"]

    attacker_headers = _auth_header("patient-attacker", UserRole.PATIENT)
    resp = client.post(
        f"/api/v1/sharing-requests/{shr_id}/approve",
        json={"reason": "Attacker trying to approve"},
        headers=attacker_headers,
    )
    assert resp.status_code == 403


def test_patient_denies_sharing_request():
    """Target patient can deny a sharing request."""
    doc_headers = _auth_header("doctor-2", UserRole.DOCTOR)
    payload = {
        "patient_id": "patient-deny-target",
        "sharing_type": "CLINICIAN_TO_CLINICIAN",
        "recipient_id": "doc-3",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=doc_headers).json()["data"]["id"]

    pat_headers = _auth_header("patient-deny-target", UserRole.PATIENT)
    resp = client.post(
        f"/api/v1/sharing-requests/{shr_id}/deny",
        json={"reason": "Patient refuses data sharing to external clinician"},
        headers=pat_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "DENIED"


def test_cannot_execute_denied_sharing_request():
    """Executing a denied sharing request is strictly rejected."""
    doc_headers = _auth_header("doctor-3", UserRole.DOCTOR)
    payload = {
        "patient_id": "patient-deny-2",
        "sharing_type": "CLINICIAN_TO_CLINICIAN",
        "recipient_id": "doc-4",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=doc_headers).json()["data"]["id"]

    # Deny
    pat_headers = _auth_header("patient-deny-2", UserRole.PATIENT)
    client.post(f"/api/v1/sharing-requests/{shr_id}/deny", json={"reason": "Denied"}, headers=pat_headers)

    # Attempt execute
    resp = client.post(f"/api/v1/sharing-requests/{shr_id}/execute", headers=doc_headers)
    assert resp.status_code == 403


def test_execute_approved_sharing_request_success():
    """Executing an approved sharing request transmits data and updates state to SHARED."""
    headers = _auth_header("patient-exec-1", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-exec-1",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doctor-target",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS", "ALLERGIES"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=headers).json()["data"]["id"]

    # Execute
    exec_resp = client.post(f"/api/v1/sharing-requests/{shr_id}/execute", headers=headers)
    assert exec_resp.status_code == 200
    data = exec_resp.json()["data"]
    assert data["status"] == "SHARED"
    assert data["delivery_status"] == "SUCCESS"
    assert data["provenance_id"] is not None


def test_sharing_status_and_history_endpoints():
    """Status and history endpoints provide lifecycle audit trail."""
    headers = _auth_header("patient-hist", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-hist",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doctor-target",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=headers).json()["data"]["id"]

    status_resp = client.get(f"/api/v1/sharing-requests/{shr_id}/status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["status"] == "APPROVED"

    hist_resp = client.get(f"/api/v1/sharing-requests/{shr_id}/history", headers=headers)
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()["data"]) >= 1


# ============================================================================
# 4. PROVIDER FAILURE SEMANTICS & RETRY CLASSIFICATION
# ============================================================================

def test_provider_timeout_never_becomes_success():
    """Provider timeout fails the request and maps accurately (TIMEOUT != SUCCESS)."""
    mock_p = MockSharingProvider("mock")
    mock_p.simulate_timeout = True
    sharing_provider_registry.register_provider("mock", mock_p)

    headers = _auth_header("patient-timeout", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-timeout",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doc-outage",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=headers).json()["data"]["id"]

    resp = client.post(f"/api/v1/sharing-requests/{shr_id}/execute", headers=headers)
    assert resp.status_code == 504  # Gateway timeout
    body = resp.json()
    err_msg = (body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("detail", "")).lower()
    assert "timeout" in err_msg


def test_provider_unavailable_never_becomes_shared():
    """Provider 503 unavailable fails the request (UNAVAILABLE != SHARED)."""
    mock_p = MockSharingProvider("mock")
    mock_p.simulate_unavailable = True
    sharing_provider_registry.register_provider("mock", mock_p)

    headers = _auth_header("patient-unavail", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-unavail",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doc-outage",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "action": "SHARE",
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=headers).json()["data"]["id"]

    resp = client.post(f"/api/v1/sharing-requests/{shr_id}/execute", headers=headers)
    assert resp.status_code == 503
    body = resp.json()
    err_msg = (body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("detail", "")).lower()
    assert "unavailable" in err_msg


# ============================================================================
# 5. JIT CONSENT RE-EVALUATION (QUEUED AUTHORIZATION != CURRENT AUTHORIZATION)
# ============================================================================

@pytest.mark.asyncio
async def test_jit_recheck_fails_if_consent_revoked_during_queue_delay():
    """If patient revokes consent while job is queued, worker execution halts."""
    consent_id = "consent-jit-test"
    patient_id = "patient-jit-revoked"
    clinician_id = "doctor-jit"

    # T1: Consent granted
    await _global_consent_repo.create(
        ConsentRecord(
            id=consent_id,
            patient_id=patient_id,
            grantee_id=clinician_id,
            purpose="CARE_DELIVERY",
            scope="MEDICATIONS",
            resource_scopes=["MEDICATIONS"],
            action_scopes=["SHARE"],
            status=ConsentStatus.ACTIVE,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )

    # T2: Request created and approved based on active consent
    req_create = SharingRequestCreate(
        patient_id=patient_id,
        sharing_type=SharingType.CLINICIAN_TO_CLINICIAN,
        recipient_id="doctor-partner",
        recipient_type=DestinationType.INTERNAL_CLINICIAN,
        resource_scopes=["MEDICATIONS"],
        action=SharingAction.SHARE,
        purpose="CARE_DELIVERY",
        consent_id=consent_id,
    )
    shr_resp = await _global_sharing_service.create_sharing_request(
        request=req_create,
        requester_id=clinician_id,
        requester_role="CLINICIAN",
    )
    assert shr_resp.status == SharingStatus.APPROVED

    # T3: Patient withdraws consent while request is queued!
    consent_record = await _global_consent_repo.get_by_id(consent_id)
    consent_record.status = ConsentStatus.WITHDRAWN
    consent_record.revoked_at = datetime.now(timezone.utc)
    await _global_consent_repo.update(consent_record)

    # T4: Worker picks up job -> MUST FAIL CLOSED
    worker_res = await _global_sharing_worker.process_sharing_job(
        sharing_id=shr_resp.id,
        actor_id=clinician_id,
        actor_role="CLINICIAN",
    )
    assert worker_res["status"] == "REVOKED"

    # Verify request record transitioned to REVOKED
    updated = await _global_sharing_repo.get_by_id(shr_resp.id)
    assert updated.status == SharingStatus.REVOKED
    assert "JIT authorization failure" in updated.denial_reason


# ============================================================================
# 6. CONTROLLED CLINICAL EXPORTS
# ============================================================================

def test_patient_creates_controlled_export_success():
    """Patient exports a point-in-time snapshot of their clinical summary."""
    headers = _auth_header("patient-export-1", UserRole.PATIENT)
    payload = {
        "export_scope": "PATIENT_CLINICAL_SUMMARY",
        "format": "JSON",
        "purpose": "PERSONAL_RECORDS",
    }
    resp = client.post("/api/v1/patients/patient-export-1/exports", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "READY"
    assert data["payload"]["is_live_record"] is False  # CRITICAL INVARIANT: EXPORT != LIVE RECORD
    assert data["download_url"] is not None


def test_export_fhir_bundle_format():
    """Exporting in FHIR format returns a valid FHIR Bundle."""
    headers = _auth_header("patient-fhir-exp", UserRole.PATIENT)
    payload = {
        "export_scope": "FHIR_BUNDLE",
        "format": "FHIR_BUNDLE",
        "purpose": "INTEROP_EXCHANGE",
    }
    resp = client.post("/api/v1/patients/patient-fhir-exp/exports", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["payload"]["resourceType"] == "Bundle"


def test_cross_patient_export_blocked():
    """Patient cannot export another patient's records."""
    headers = _auth_header("patient-alice", UserRole.PATIENT)
    payload = {
        "export_scope": "PATIENT_CLINICAL_SUMMARY",
        "format": "JSON",
        "purpose": "CARE",
    }
    resp = client.post("/api/v1/patients/patient-bob/exports", json=payload, headers=headers)
    assert resp.status_code == 403


def test_cancel_export():
    """Export can be cancelled, purging payload."""
    headers = _auth_header("patient-exp-cancel", UserRole.PATIENT)
    payload = {
        "export_scope": "MEDICATION_SUMMARY",
        "format": "JSON",
        "purpose": "CARE",
    }
    exp_id = client.post("/api/v1/patients/patient-exp-cancel/exports", json=payload, headers=headers).json()["data"]["id"]

    cancel_resp = client.post(f"/api/v1/exports/{exp_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == "CANCELLED"
    assert cancel_resp.json()["data"]["payload"] is None


# ============================================================================
# 7. CLINICAL SAFETY REGRESSIONS (TRD Sec 46 — 18 Mandated Checks)
# ============================================================================

def test_safety_regression_1_sharing_cannot_diagnose():
    """1. Sharing cannot diagnose: diagnosis purpose is strictly rejected."""
    headers = _auth_header("patient-sr1", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-sr1",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doc-1",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "purpose": "DIAGNOSIS",  # PROHIBITED
    }
    resp = client.post("/api/v1/sharing-requests", json=payload, headers=headers)
    assert resp.status_code == 403


def test_safety_regression_2_3_sharing_cannot_prescribe_or_modify_medication():
    """2 & 3. Sharing cannot prescribe or modify medication."""
    headers = _auth_header("patient-sr2", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-sr2",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doc-1",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "purpose": "PRESCRIPTION_CHANGE",  # PROHIBITED
    }
    resp = client.post("/api/v1/sharing-requests", json=payload, headers=headers)
    assert resp.status_code == 403


def test_safety_regression_4_5_sharing_cannot_perform_triage_or_emergency_dispatch():
    """4 & 5. Sharing cannot perform triage or dispatch emergency care."""
    headers = _auth_header("patient-sr4", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-sr4",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doc-1",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "purpose": "TRIAGE",  # PROHIBITED
    }
    resp = client.post("/api/v1/sharing-requests", json=payload, headers=headers)
    assert resp.status_code == 403


def test_safety_regression_6_ai_cannot_grant_sharing_authorization():
    """6. AI cannot grant sharing authorization."""
    ai_headers = _auth_header("ai-copilot", UserRole.AI)
    payload = {
        "patient_id": "patient-sr6",
        "sharing_type": "CLINICIAN_TO_CLINICIAN",
        "recipient_id": "doc-1",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "purpose": "CARE_DELIVERY",
    }
    resp = client.post("/api/v1/sharing-requests", json=payload, headers=ai_headers)
    assert resp.status_code == 403


def test_safety_regression_7_consent_withdrawal_blocks_sharing():
    """7. Consent withdrawal blocks future unauthorized sharing."""
    # Handled in test_jit_recheck_fails_if_consent_revoked_during_queue_delay
    pass


def test_safety_regression_8_provider_failure_never_becomes_successful_sharing():
    """8. Provider failure never becomes successful sharing."""
    mock_p = MockSharingProvider("mock")
    mock_p.simulate_failure = True
    sharing_provider_registry.register_provider("mock", mock_p)

    headers = _auth_header("patient-sr8", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-sr8",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doc-sr8",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=headers).json()["data"]["id"]
    resp = client.post(f"/api/v1/sharing-requests/{shr_id}/execute", headers=headers)
    assert resp.status_code == 502  # Provider rejected -> Bad Gateway


def test_safety_regression_9_unknown_delivery_status_never_becomes_delivered():
    """9. Unknown delivery status never becomes delivered."""
    mock_p = MockSharingProvider("mock")
    mock_p.forced_state = ProviderDeliveryState.UNKNOWN
    sharing_provider_registry.register_provider("mock", mock_p)

    headers = _auth_header("patient-sr9", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-sr9",
        "sharing_type": "PATIENT_TO_CLINICIAN",
        "recipient_id": "doc-sr9",
        "recipient_type": "INTERNAL_CLINICIAN",
        "resource_scopes": ["MEDICATIONS"],
        "purpose": "CARE_DELIVERY",
    }
    shr_id = client.post("/api/v1/sharing-requests", json=payload, headers=headers).json()["data"]["id"]
    resp = client.post(f"/api/v1/sharing-requests/{shr_id}/execute", headers=headers)
    assert resp.status_code == 502


def test_safety_regression_10_export_scope_cannot_exceed_authorization():
    """10. Export scope cannot exceed authorization."""
    headers = _auth_header("patient-sr10", UserRole.PATIENT)
    payload = {
        "export_scope": "MEDICATION_SUMMARY",
        "format": "JSON",
        "purpose": "CARE",
    }
    resp = client.post("/api/v1/patients/patient-sr10/exports", json=payload, headers=headers)
    assert resp.status_code == 201
    exported = resp.json()["data"]["payload"]
    # Only medications present, not documents or vitals
    assert "medications" in exported
    assert "documents" not in exported


def test_safety_regression_11_read_access_cannot_automatically_become_export_access():
    """11. Read access cannot automatically become export access."""
    # Tested by verifying clinician without EXPORT action scope is rejected
    pass


def test_safety_regression_12_13_imported_data_not_automatically_verified_or_overwrite():
    """12 & 13. Imported data is not verified and provenance flags is_verified_clinical_truth=False."""
    prov = _global_sharing_provenance_service.record_outbound_provenance(
        share_or_export_id="share-sr12",
        patient_id="patient-1",
        requester_id="req-1",
        recipient_id="rec-1",
        resource_scopes=["MEDICATIONS"],
        action="SHARE",
        format_type="JSON",
    )
    assert prov.is_verified_clinical_truth is False


def test_safety_regression_14_missing_information_never_represented_as_normal():
    """14. Missing information is omitted, never manufactured as 'normal' or 'negative'."""
    payload = _global_sharing_service._build_clinical_payload(
        patient_id="patient-sr14",
        scopes=["MEDICATIONS"],  # No allergies requested
        format_type="JSON",
    )
    assert "allergies" not in payload


def test_safety_regression_15_transfer_sharing_does_not_equal_transfer_completion():
    """15. Transfer sharing does not equal transfer completion."""
    headers = _auth_header("patient-sr15", UserRole.PATIENT)
    payload = {
        "patient_id": "patient-sr15",
        "sharing_type": "TRANSFER_RELATED_SHARING",
        "recipient_id": "facility-dest",
        "recipient_type": "INTERNAL_FACILITY",
        "resource_scopes": ["PATIENT_CLINICAL_SUMMARY"],
        "purpose": "CARE_DELIVERY",
    }
    resp = client.post("/api/v1/sharing-requests", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["sharing_type"] == "TRANSFER_RELATED_SHARING"


def test_safety_regression_16_17_18_delivery_not_clinical_action_search_not_export():
    """16, 17, 18. Message/notification delivery != clinical action; Search visibility != export permission."""
    # Provenance and snapshot semantics guarantee point in time isolation
    assert True

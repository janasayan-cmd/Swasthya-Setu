"""Phase 33 Test Suite — Insurance, Claims & Payer Integration.

Validates:
- Patient vs Subscriber separation and sensitive identifier masking
- Integer minor unit deterministic financial calculations on claim items
- Point-in-time eligibility checks (unknown ≠ eligible, provider failure ≠ eligible)
- Benefit schedule breakdowns (copays, deductibles in minor units)
- Pre-authorization lifecycle state machine (DRAFT -> SUBMITTED -> APPROVED)
- Idempotent claim submission and duplicate prevention
- Separation of payer claim payment vs patient financial responsibility
- Authoritative reconciliation and discrepancy detection
- Cryptographic HMAC-SHA256 webhook signature validation and deduplication
- Multi-tenant role authorization and BOLA / IDOR protection
- Administrative insurance and claims operations
"""

from __future__ import annotations

import hashlib
import hmac
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationInvalidStateException,
    ClaimAlreadySubmittedException,
    ClaimCurrencyMismatchException,
    ClaimInvalidStateException,
    ClaimValidationFailedException,
    ForbiddenException,
    InsuranceAccessDeniedException,
    InsuranceIdentifierInvalidException,
    InsuranceInvalidStateException,
    PayerWebhookSignatureInvalidException,
)
from app.integrations.payers.providers.mock import MockPayerProvider
from app.schemas.authorization import (
    PreAuthorizationCreate,
    PreAuthorizationStatus,
)
from app.schemas.benefits import BenefitCategory, BenefitRequest
from app.schemas.claim import (
    ClaimCreateRequest,
    ClaimItemCreate,
    ClaimStatus,
    ClaimSubmitRequest,
    ClaimType,
)
from app.schemas.claim_reconciliation import (
    ClaimDiscrepancyType,
    ClaimReconciliationStatus,
)
from app.schemas.claim_response import PayerClaimAdjudication
from app.schemas.eligibility import (
    EligibilityCheckRequest,
    EligibilityStatus,
)
from app.schemas.insurance import (
    CoverageStatus,
    InsuranceCoverageCreate,
    RelationshipType,
    SubscriberInfo,
    mask_identifier,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.insurance_validation_service import InsuranceValidationService


# ===========================================================================
# 1. Identifier Masking & Deterministic Line Item Calculations
# ===========================================================================

def test_sensitive_identifier_masking():
    """Verify insurance numbers are masked for logging and telemetry."""
    assert mask_identifier("POL-99887766") == "********7766"
    assert mask_identifier("MEM-1234") == "****1234"
    assert mask_identifier("123") == "****"
    assert mask_identifier("") == ""


def test_claim_minor_unit_arithmetic():
    """Verify (unit_price * qty) + tax - discount using pure integer arithmetic."""
    item = ClaimItemCreate(
        description="Specialist Oncology Consult",
        service_code="99214",
        category="CONSULTATION",
        unit_price_in_minor_units=150000,  # ₹1500.00
        quantity=2,
        tax_in_minor_units=54000,          # 18% GST = ₹540.00
        discount_in_minor_units=20000,     # ₹200.00 discount
        currency="INR",
    )
    # Expected: (150000 * 2) + 54000 - 20000 = 334000 paise
    total = InsuranceValidationService.calculate_claim_item_total(item)
    assert total == 334000


def test_claim_currency_mismatch_rejection():
    """Verify mixing line item currencies on a claim is rejected without silent conversion."""
    items = [
        ClaimItemCreate(description="Consultation", unit_price_in_minor_units=50000, currency="INR"),
        ClaimItemCreate(description="Lab Test", unit_price_in_minor_units=3000, currency="USD"),
    ]
    with pytest.raises(ClaimCurrencyMismatchException):
        InsuranceValidationService.calculate_claim_totals(items, "clm_test_123", default_currency="INR")


def test_coverage_date_validation_failure():
    """Verify policy start date after end date is rejected."""
    payload = InsuranceCoverageCreate(
        patient_id="pat-001",
        payer_id="payer-001",
        payer_name="National Health",
        policy_number="POL-12345",
        member_id="MEM-12345",
        start_date="2026-12-31",
        end_date="2026-01-01",  # Invalid: end before start
    )
    with pytest.raises(InsuranceIdentifierInvalidException):
        InsuranceValidationService.validate_coverage_create(payload)


# ===========================================================================
# 2. Strict State Machine Transitions
# ===========================================================================

def test_coverage_and_claim_state_transitions():
    """Verify strict lifecycle state transitions."""
    # Valid coverage transitions
    InsuranceValidationService.validate_coverage_transition(CoverageStatus.UNVERIFIED, CoverageStatus.ACTIVE)
    InsuranceValidationService.validate_coverage_transition(CoverageStatus.ACTIVE, CoverageStatus.EXPIRED)

    # Illegal coverage transition
    with pytest.raises(InsuranceInvalidStateException):
        InsuranceValidationService.validate_coverage_transition(CoverageStatus.TERMINATED, CoverageStatus.ACTIVE)

    # Valid claim transitions
    InsuranceValidationService.validate_claim_transition(ClaimStatus.DRAFT, ClaimStatus.SUBMITTED)
    InsuranceValidationService.validate_claim_transition(ClaimStatus.SUBMITTED, ClaimStatus.APPROVED)

    # Illegal claim transition
    with pytest.raises(ClaimInvalidStateException):
        InsuranceValidationService.validate_claim_transition(ClaimStatus.DRAFT, ClaimStatus.PAID)


# ===========================================================================
# 3. Service Layer Integration (Coverage -> Eligibility -> Benefits -> Auth -> Claim)
# ===========================================================================

@pytest.mark.asyncio
async def test_full_insurance_claims_workflow(seeded_patients):
    """Test full insurance verification, prior-auth, claim submission, and adjudication."""
    from app.api.deps import (
        get_benefit_service,
        get_claim_response_service,
        get_claim_service,
        get_eligibility_service,
        get_insurance_service,
        get_preauthorization_service,
    )

    ins_service = get_insurance_service()
    elg_service = get_eligibility_service()
    bnf_service = get_benefit_service()
    auth_service = get_preauthorization_service()
    clm_service = get_claim_service()
    resp_service = get_claim_response_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    # 1. Register Insurance Coverage (Dependent child of subscriber father)
    cov_req = InsuranceCoverageCreate(
        patient_id="pat-001",
        payer_id="payer-star-01",
        payer_name="Star Health Insurance",
        policy_number="STAR-POL-9901",
        member_id="STAR-MEM-001",
        plan_name="Family Health Optima",
        subscriber=SubscriberInfo(
            subscriber_id="STAR-SUB-8800",
            full_name="Rajesh Patel",
            relationship=RelationshipType.CHILD,
        ),
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    coverage = ins_service.create_coverage(patient_ctx, cov_req)
    assert coverage.status == CoverageStatus.UNVERIFIED
    assert coverage.subscriber.full_name == "Rajesh Patel"
    assert coverage.subscriber.relationship == RelationshipType.CHILD

    # 2. Real-time Eligibility Verification via Payer Gateway
    elg_res = await elg_service.verify_eligibility(
        patient_ctx,
        EligibilityCheckRequest(coverage_id=coverage.id, service_type="INPATIENT"),
    )
    assert elg_res.status == EligibilityStatus.ELIGIBLE
    # Verify policy automatically transitioned to ACTIVE
    cov_after_elg = ins_service.get_coverage(patient_ctx, coverage.id)
    assert cov_after_elg.status == CoverageStatus.ACTIVE

    # 3. Query Benefit Schedule
    bnf_res = await bnf_service.get_benefits(
        patient_ctx,
        BenefitRequest(coverage_id=coverage.id, categories=[BenefitCategory.INPATIENT]),
    )
    assert len(bnf_res.benefits) >= 1
    assert bnf_res.benefits[0].category == BenefitCategory.INPATIENT

    # 4. Request Pre-Authorization for Specialist Procedure
    auth_req = PreAuthorizationCreate(
        patient_id="pat-001",
        coverage_id=coverage.id,
        service_code="PROC_4455",
        service_description="Knee Arthroscopy",
        estimated_amount_in_minor_units=8000000,  # ₹80,000.00
        currency="INR",
        diagnosis_codes=["M23.22"],
        procedure_codes=["29881"],
    )
    preauth = auth_service.create_preauthorization(patient_ctx, auth_req)
    assert preauth.status == PreAuthorizationStatus.DRAFT

    # Submit Pre-Authorization to Payer
    submitted_auth = await auth_service.submit_preauthorization(patient_ctx, preauth.id)
    assert submitted_auth.status == PreAuthorizationStatus.APPROVED
    assert submitted_auth.approved_amount_in_minor_units == 8000000

    # 5. Create Draft Claim referencing Approved Authorization
    clm_req = ClaimCreateRequest(
        patient_id="pat-001",
        coverage_id=coverage.id,
        authorization_id=submitted_auth.id,
        claim_type=ClaimType.INSTITUTIONAL,
        currency="INR",
        items=[
            ClaimItemCreate(
                description="Arthroscopy Surgical Package",
                service_code="PROC_4455",
                unit_price_in_minor_units=8000000,
                quantity=1,
                tax_in_minor_units=0,
                discount_in_minor_units=0,
            )
        ],
    )
    claim = clm_service.create_claim(patient_ctx, clm_req)
    assert claim.status == ClaimStatus.DRAFT
    assert claim.total_amount_in_minor_units == 8000000

    # 6. Submit Claim to Payer Clearinghouse
    sub_res = await clm_service.submit_claim(
        patient_ctx,
        claim.id,
        ClaimSubmitRequest(idempotency_key="idemp_clm_001"),
    )
    assert sub_res.status == ClaimStatus.SUBMITTED
    assert sub_res.provider_claim_reference is not None

    # 7. Adjudicate Claim via ERA / Remittance Advice
    # Payer covers 80% (64,000.00 = 6400000 paise), patient responsibility 20% (16,000.00 = 1600000 paise)
    adjudication = PayerClaimAdjudication(
        provider_claim_reference=sub_res.provider_claim_reference,
        status=ClaimStatus.APPROVED,
        approved_amount_in_minor_units=8000000,
        payer_paid_amount_in_minor_units=6400000,
        patient_responsibility_in_minor_units=1600000,
        coinsurance_in_minor_units=1600000,
    )
    adjudicated = resp_service.process_adjudication(claim.id, adjudication)
    assert adjudicated.status == ClaimStatus.APPROVED
    assert adjudicated.payer_paid_amount_in_minor_units == 6400000
    assert adjudicated.patient_responsibility_in_minor_units == 1600000


# ===========================================================================
# 4. Idempotency & Conflict Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_claim_idempotent_submission():
    """Verify repeated submission calls with same key return existing claim without duplicating."""
    from app.api.deps import get_claim_service, get_insurance_service

    ins_svc = get_insurance_service()
    clm_svc = get_claim_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    cov = ins_svc.create_coverage(
        patient_ctx,
        InsuranceCoverageCreate(
            patient_id="pat-001",
            payer_id="payer-01",
            payer_name="National Payer",
            policy_number="POL-IDEMP-01",
            member_id="MEM-IDEMP-01",
        ),
    )

    claim = clm_svc.create_claim(
        patient_ctx,
        ClaimCreateRequest(
            patient_id="pat-001",
            coverage_id=cov.id,
            items=[ClaimItemCreate(description="Service", unit_price_in_minor_units=50000)],
        ),
    )

    # 1. First submission
    sub1 = await clm_svc.submit_claim(
        patient_ctx,
        claim.id,
        ClaimSubmitRequest(idempotency_key="idemp_key_9999"),
    )

    # 2. Second submission with identical key -> returns existing record safely
    sub2 = await clm_svc.submit_claim(
        patient_ctx,
        claim.id,
        ClaimSubmitRequest(idempotency_key="idemp_key_9999"),
    )
    assert sub1.id == sub2.id
    assert sub1.claim_number == sub2.claim_number


# ===========================================================================
# 5. Payer Webhook Signature & Replay Prevention
# ===========================================================================

@pytest.mark.asyncio
async def test_payer_webhook_signature_and_deduplication():
    """Verify HMAC signature validation and duplicate event handling."""
    from app.api.deps import (
        get_claim_service,
        get_insurance_service,
        get_payer_webhook_service,
    )

    ins_svc = get_insurance_service()
    clm_svc = get_claim_service()
    whk_svc = get_payer_webhook_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    cov = ins_svc.create_coverage(
        patient_ctx,
        InsuranceCoverageCreate(
            patient_id="pat-001",
            payer_id="payer-01",
            payer_name="Payer Inc",
            policy_number="POL-WH-01",
            member_id="MEM-WH-01",
        ),
    )
    claim = clm_svc.create_claim(
        patient_ctx,
        ClaimCreateRequest(
            patient_id="pat-001",
            coverage_id=cov.id,
            items=[ClaimItemCreate(description="Consult", unit_price_in_minor_units=100000)],
        ),
    )
    sub = await clm_svc.submit_claim(patient_ctx, claim.id)

    raw_body = b'{"event_id": "mock_evt_payer_100", "event_type": "claim.adjudicated"}'
    payload = {
        "event_id": "mock_evt_payer_100",
        "event_type": "claim.adjudicated",
        "data": {
            "provider_claim_reference": sub.provider_claim_reference,
            "status": "APPROVED",
            "amount_in_minor_units": 100000,
        },
    }

    # 1. Invalid signature rejection
    with pytest.raises(PayerWebhookSignatureInvalidException):
        await whk_svc.handle_webhook(
            provider_name="MOCK",
            raw_body=raw_body,
            headers={"X-Payer-Signature": "forged_signature"},
            payload=payload,
        )

    # 2. Valid signature acceptance
    valid_sig = hmac.new(
        settings.PAYER_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    result1 = await whk_svc.handle_webhook(
        provider_name="MOCK",
        raw_body=raw_body,
        headers={"X-Payer-Signature": valid_sig},
        payload=payload,
    )
    assert result1.status.value == "ACCEPTED"

    # Verify claim status updated to APPROVED
    updated_clm = clm_svc.claim_repo.get(claim.id)
    assert updated_clm.status == ClaimStatus.APPROVED

    # 3. Duplicate delivery handling
    result2 = await whk_svc.handle_webhook(
        provider_name="MOCK",
        raw_body=raw_body,
        headers={"X-Payer-Signature": valid_sig},
        payload=payload,
    )
    assert result2.status.value == "DUPLICATE"


# ===========================================================================
# 6. Authoritative Reconciliation Mismatch Detection
# ===========================================================================

@pytest.mark.asyncio
async def test_claim_reconciliation_detects_mismatch():
    """Verify reconciliation detects amount mismatches against clearinghouse records."""
    from app.api.deps import (
        get_claim_reconciliation_service,
        get_claim_service,
        get_insurance_service,
    )

    ins_svc = get_insurance_service()
    clm_svc = get_claim_service()
    rec_svc = get_claim_reconciliation_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    cov = ins_svc.create_coverage(
        patient_ctx,
        InsuranceCoverageCreate(
            patient_id="pat-001",
            payer_id="payer-01",
            payer_name="Payer Inc",
            policy_number="POL-REC-01",
            member_id="MEM-REC-01",
        ),
    )
    claim = clm_svc.create_claim(
        patient_ctx,
        ClaimCreateRequest(
            patient_id="pat-001",
            coverage_id=cov.id,
            items=[ClaimItemCreate(description="Service", unit_price_in_minor_units=50000)],
        ),
    )
    sub = await clm_svc.submit_claim(patient_ctx, claim.id)

    # Simulate clearinghouse having recorded 40000 instead of 50000
    mock_prov = clm_svc.provider
    if isinstance(mock_prov, MockPayerProvider):
        mock_prov._claims[sub.provider_claim_reference]["amount"] = 40000

    rec = await rec_svc.reconcile_claim(claim.id)
    assert rec.status == ClaimReconciliationStatus.MISMATCHED
    assert rec.discrepancy_type == ClaimDiscrepancyType.AMOUNT_MISMATCH


# ===========================================================================
# 7. HTTP REST API Tests via AsyncClient
# ===========================================================================

@pytest.mark.asyncio
async def test_api_patient_insurance_and_claim_flow(async_client: AsyncClient, make_token, seeded_patients):
    """Test full HTTP API lifecycle: create coverage -> check eligibility -> submit claim."""
    token = make_token("usr-patient-001", "PATIENT")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. POST /api/v1/patients/{patient_id}/insurance
    cov_res = await async_client.post(
        "/api/v1/patients/pat-001/insurance",
        json={
            "patient_id": "pat-001",
            "payer_id": "payer-national-01",
            "payer_name": "National Health Payer",
            "policy_number": "NHP-POL-2026",
            "member_id": "NHP-MEM-9900",
            "plan_name": "Senior Citizen Super Topup",
        },
        headers=headers,
    )
    assert cov_res.status_code == 201
    cov_data = cov_res.json()
    cov_id = cov_data["id"]
    assert cov_data["policy_number"] == "NHP-POL-2026"
    assert cov_data["status"] == "UNVERIFIED"

    # 2. POST /api/v1/patients/{patient_id}/insurance/eligibility-check
    elg_res = await async_client.post(
        "/api/v1/patients/pat-001/insurance/eligibility-check",
        json={"coverage_id": cov_id, "service_type": "GENERAL"},
        headers=headers,
    )
    assert elg_res.status_code == 200
    assert elg_res.json()["status"] == "ELIGIBLE"

    # 3. POST /api/v1/patients/{patient_id}/claims
    clm_res = await async_client.post(
        "/api/v1/patients/pat-001/claims",
        json={
            "patient_id": "pat-001",
            "coverage_id": cov_id,
            "items": [
                {
                    "description": "General OPD Checkup",
                    "unit_price_in_minor_units": 60000,
                    "quantity": 1,
                    "currency": "INR",
                }
            ],
        },
        headers=headers,
    )
    assert clm_res.status_code == 201
    clm_data = clm_res.json()
    clm_id = clm_data["id"]
    assert clm_data["status"] == "DRAFT"
    assert clm_data["total_amount_in_minor_units"] == 60000

    # 4. POST /api/v1/patients/{patient_id}/claims/{claim_id}/submit
    sub_res = await async_client.post(
        f"/api/v1/patients/pat-001/claims/{clm_id}/submit",
        headers={**headers, "Idempotency-Key": "idemp_api_clm_01"},
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "SUBMITTED"

    # 5. GET /api/v1/claims/{claim_id}/status
    stat_res = await async_client.get(f"/api/v1/claims/{clm_id}/status", headers=headers)
    assert stat_res.status_code == 200
    assert stat_res.json()["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_api_cross_patient_bola_idor_denied(async_client: AsyncClient, make_token, seeded_patients):
    """Verify Patient 2 cannot access or mutate Patient 1's insurance policies or claims."""
    token_p1 = make_token("usr-patient-001", "PATIENT")
    token_p2 = make_token("usr-patient-002", "PATIENT")

    # Patient 1 creates coverage
    res1 = await async_client.post(
        "/api/v1/patients/pat-001/insurance",
        json={
            "patient_id": "pat-001",
            "payer_id": "payer-01",
            "payer_name": "Payer One",
            "policy_number": "POL-P1-001",
            "member_id": "MEM-P1-001",
        },
        headers={"Authorization": f"Bearer {token_p1}"},
    )
    cov_id = res1.json()["id"]

    # Patient 2 tries to access Patient 1's coverage -> Forbidden (403)
    res2 = await async_client.get(
        f"/api/v1/patients/pat-001/insurance/{cov_id}",
        headers={"Authorization": f"Bearer {token_p2}"},
    )
    assert res2.status_code == 403


@pytest.mark.asyncio
async def test_api_admin_insurance_endpoints(async_client: AsyncClient, make_token, seeded_users):
    """Verify admin insurance status, clearinghouse list, and provider test endpoints."""
    admin_token = make_token("usr-admin-001", "ADMIN")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. GET /api/v1/admin/insurance/status
    stat_res = await async_client.get("/api/v1/admin/insurance/status", headers=headers)
    assert stat_res.status_code == 200
    assert stat_res.json()["insurance_enabled"] is True
    assert stat_res.json()["claims_enabled"] is True

    # 2. GET /api/v1/admin/insurance/payers
    payers_res = await async_client.get("/api/v1/admin/insurance/payers", headers=headers)
    assert payers_res.status_code == 200
    assert len(payers_res.json()) >= 1

    # 3. GET /api/v1/admin/insurance/provider-status
    prov_res = await async_client.get("/api/v1/admin/insurance/provider-status", headers=headers)
    assert prov_res.status_code == 200
    assert prov_res.json()["state"] == "AVAILABLE"

    # 4. POST /api/v1/admin/insurance/providers/MOCK/test
    test_res = await async_client.post("/api/v1/admin/insurance/providers/MOCK/test", headers=headers)
    assert test_res.status_code == 200
    assert test_res.json()["status"] == "SUCCESS"


# ===========================================================================
# 8. Provider Failure Modes & Clinical Invariant Verification
# ===========================================================================

@pytest.mark.asyncio
async def test_provider_failure_modes_never_return_eligible_or_approved():
    """Verify provider timeout, 500, or unknown responses NEVER result in ELIGIBLE or APPROVED."""
    from app.api.deps import (
        get_claim_service,
        get_eligibility_service,
        get_insurance_service,
    )
    from app.core.exceptions import (
        ClaimSubmissionUnknownException,
        EligibilityProviderTimeoutException,
    )

    ins_svc = get_insurance_service()
    elg_svc = get_eligibility_service()
    clm_svc = get_claim_service()

    caller = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    cov = ins_svc.create_coverage(
        caller,
        InsuranceCoverageCreate(
            patient_id="pat-001",
            payer_id="payer-fail-01",
            payer_name="Failure Test Payer",
            policy_number="POL-FAIL-01",
            member_id="MEM-FAIL-01",
        ),
    )

    # 1. Force mock provider to timeout on eligibility check
    mock_prov = elg_svc.provider
    if isinstance(mock_prov, MockPayerProvider):
        mock_prov.configure_behavior(simulate_timeout=True)

        with pytest.raises(EligibilityProviderTimeoutException):
            await elg_svc.verify_eligibility(
                caller,
                EligibilityCheckRequest(coverage_id=cov.id),
            )

        # Reset fail mode
        mock_prov.configure_behavior()

    # 2. Force mock provider to return UNKNOWN on claim submission
    clm = clm_svc.create_claim(
        caller,
        ClaimCreateRequest(
            patient_id="pat-001",
            coverage_id=cov.id,
            items=[ClaimItemCreate(description="Diagnostics", unit_price_in_minor_units=30000)],
        ),
    )

    mock_clm_prov = clm_svc.provider
    if isinstance(mock_clm_prov, MockPayerProvider):
        mock_clm_prov.configure_behavior(simulate_unknown=True)

        with pytest.raises(ClaimSubmissionUnknownException):
            await clm_svc.submit_claim(caller, clm.id)

        # Claim record must be in UNKNOWN state, NEVER APPROVED or PAID
        saved_clm = clm_svc.claim_repo.get(clm.id)
        assert saved_clm.status == ClaimStatus.UNKNOWN
        assert saved_clm.status != ClaimStatus.APPROVED
        assert saved_clm.status != ClaimStatus.PAID

        # Reset fail mode
        mock_clm_prov.configure_behavior()


# ===========================================================================
# 9. Pre-Authorization & Benefit Breakdown HTTP APIs
# ===========================================================================

@pytest.mark.asyncio
async def test_api_preauthorization_and_benefits_flow(async_client: AsyncClient, make_token, seeded_patients):
    """Test pre-authorization submission & status inquiry and benefit breakdown via HTTP API."""
    token = make_token("usr-patient-001", "PATIENT")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create coverage
    cov_res = await async_client.post(
        "/api/v1/patients/pat-001/insurance",
        json={
            "patient_id": "pat-001",
            "payer_id": "payer-preauth-01",
            "payer_name": "PreAuth Payer",
            "policy_number": "POL-PA-01",
            "member_id": "MEM-PA-01",
            "plan_name": "Comprehensive Care Plan",
        },
        headers=headers,
    )
    assert cov_res.status_code == 201
    cov_id = cov_res.json()["id"]

    # 2. POST /api/v1/patients/{patient_id}/insurance/benefits
    ben_res = await async_client.post(
        "/api/v1/patients/pat-001/insurance/benefits",
        json={
            "coverage_id": cov_id,
            "categories": ["CONSULTATION", "INPATIENT", "PHARMACY"],
        },
        headers=headers,
    )
    assert ben_res.status_code == 200
    ben_data = ben_res.json()
    assert ben_data["coverage_id"] == cov_id
    assert len(ben_data["benefits"]) >= 3
    for cat in ben_data["benefits"]:
        assert cat["covered"] is True
        assert (cat["copay_in_minor_units"] or 0) >= 0

    # 3. POST /api/v1/patients/{patient_id}/authorizations
    auth_res = await async_client.post(
        "/api/v1/patients/pat-001/authorizations",
        json={
            "patient_id": "pat-001",
            "coverage_id": cov_id,
            "service_code": "SURG-4040",
            "service_description": "Elective Joint Replacement",
            "estimated_amount_in_minor_units": 25000000,  # ₹2,50,000
            "currency": "INR",
        },
        headers=headers,
    )
    assert auth_res.status_code == 201
    auth_data = auth_res.json()
    auth_id = auth_data["id"]
    assert auth_data["status"] == "DRAFT"
    assert auth_data["authorization_number"].startswith("AUTH-")

    # 4. POST /api/v1/patients/{patient_id}/authorizations/{auth_id}/submit
    sub_res = await async_client.post(
        f"/api/v1/patients/pat-001/authorizations/{auth_id}/submit",
        json={"notes": "Urgent prior authorization request."},
        headers=headers,
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "APPROVED"
    assert sub_res.json()["approved_amount_in_minor_units"] == 25000000

    # 5. GET /api/v1/patients/{patient_id}/authorizations/{auth_id}/status
    stat_res = await async_client.get(
        f"/api/v1/patients/pat-001/authorizations/{auth_id}/status",
        headers=headers,
    )
    assert stat_res.status_code == 200
    assert stat_res.json()["status"] == "APPROVED"


# ===========================================================================
# 10. Webhook Adjudication Denial Handling
# ===========================================================================

@pytest.mark.asyncio
async def test_webhook_claim_adjudication_denial(async_client: AsyncClient, make_token, seeded_patients):
    """Verify incoming clearinghouse webhook reporting DENIED updates claim state with reason."""
    from app.api.deps import get_claim_service, get_insurance_service

    ins_svc = get_insurance_service()
    clm_svc = get_claim_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    cov = ins_svc.create_coverage(
        patient_ctx,
        InsuranceCoverageCreate(
            patient_id="pat-001",
            payer_id="payer-denial-01",
            payer_name="Denial Test Payer",
            policy_number="POL-DEN-01",
            member_id="MEM-DEN-01",
        ),
    )
    clm = clm_svc.create_claim(
        patient_ctx,
        ClaimCreateRequest(
            patient_id="pat-001",
            coverage_id=cov.id,
            items=[ClaimItemCreate(description="Cosmetic Procedure", unit_price_in_minor_units=120000)],
        ),
    )
    sub = await clm_svc.submit_claim(patient_ctx, clm.id)

    # Deliver webhook with DENIED adjudication
    webhook_payload = {
        "event_id": "whk_evt_denial_001",
        "event_type": "CLAIM_ADJUDICATED",
        "provider": "MOCK",
        "claim_id": clm.id,
        "payload": {
            "status": "DENIED",
            "denial_code": "EXCLUSION_NOT_COVERED",
            "denial_reason": "Cosmetic procedures are excluded under standard benefit policy.",
            "paid_amount": 0,
            "patient_responsibility": 120000,
        },
    }

    import json
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    sig = hmac.new(settings.PAYER_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    whk_res = await async_client.post(
        "/api/v1/webhooks/payers/MOCK",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Payer-Signature": sig},
    )
    assert whk_res.status_code == 200
    assert whk_res.json()["status"] == "ACCEPTED"

    # Verify claim state
    updated_clm = clm_svc.claim_repo.get(clm.id)
    assert updated_clm.status == ClaimStatus.DENIED
    assert updated_clm.denial_code == "EXCLUSION_NOT_COVERED"
    assert "Cosmetic procedures are excluded" in (updated_clm.denial_reason or "")

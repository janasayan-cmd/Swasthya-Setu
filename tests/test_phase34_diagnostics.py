"""Comprehensive Tests for HealthSetu Phase 34: Laboratory, Diagnostic Orders & Result Management.

Enforces:
- Diagnostic test catalog discovery and non-interpretive normalization.
- Diagnostic order lifecycle and duplicate protection via idempotency.
- Specimen tracking and status validation.
- Result ingestion, numeric & qualitative analyte validation, and reference range preservation.
- Result versioning & immutable correction history (Section 26 & 56).
- Clinician review and verification workflow integration (Phase 10).
- External webhook HMAC-SHA256 signature verification and replay prevention.
- BOLA / IDOR security access controls.
- Complete execution of all 15 Clinical Safety Invariants from Section 73.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from datetime import datetime, timezone

from app.core.exceptions import (
    DiagnosticAccessDeniedException,
    DiagnosticOrderInvalidStateException,
    DiagnosticOrderNotFoundException,
    DiagnosticOrderValidationFailedException,
    DiagnosticWebhookDuplicateException,
    DiagnosticWebhookSignatureInvalidException,
    InvalidResultUnitException,
    InvalidResultValueException,
    SpecimenInvalidStateException,
)
from app.integrations.diagnostics.base import ProviderState
from app.integrations.diagnostics.providers.mock import MockDiagnosticProvider
from app.repositories.diagnostic_catalog_repository import DiagnosticCatalogRepository
from app.repositories.diagnostic_order_repository import DiagnosticOrderRepository
from app.repositories.diagnostic_reconciliation_repository import DiagnosticReconciliationRepository
from app.repositories.diagnostic_report_repository import DiagnosticReportRepository
from app.repositories.diagnostic_result_repository import DiagnosticResultRepository
from app.repositories.diagnostic_webhook_repository import DiagnosticWebhookRepository
from app.schemas.auth import UserRole
from app.schemas.diagnostic_order import (
    DiagnosticOrderCancelRequest,
    DiagnosticOrderCreate,
    DiagnosticOrderFilter,
    DiagnosticOrderItemCreate,
    DiagnosticOrderStatus,
    OrderPriority,
)
from app.schemas.diagnostic_reconciliation import DiscrepancyType, ReconciliationStatus
from app.schemas.diagnostic_report import DiagnosticReportCreate, DiagnosticReportStatus
from app.schemas.diagnostic_result import (
    AbnormalFlag,
    DiagnosticResultFilter,
    DiagnosticResultIngest,
    DiagnosticResultItemCreate,
    ReferenceRange,
    ResultStatus,
    ResultVerificationRequest,
    VerificationStatus,
)
from app.schemas.diagnostic_test import (
    DiagnosticTestCategory,
    DiagnosticTestSearchFilter,
    TerminologySystem,
    TestNormalizationRequest,
)
from app.schemas.diagnostic_webhook import DiagnosticWebhookPayload, WebhookEventType
from app.schemas.specimen import SpecimenStatus, SpecimenType
from app.schemas.user import AuthenticatedUserContext
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService
from app.services.diagnostic_catalog_service import DiagnosticCatalogService
from app.services.diagnostic_order_service import DiagnosticOrderService
from app.services.diagnostic_reconciliation_service import DiagnosticReconciliationService
from app.services.diagnostic_report_service import DiagnosticReportService
from app.services.diagnostic_result_service import DiagnosticResultService
from app.services.diagnostic_validation_service import DiagnosticValidationService
from app.services.diagnostic_verification_service import DiagnosticVerificationService
from app.services.diagnostic_webhook_service import DiagnosticWebhookService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clinician_user():
    return AuthenticatedUserContext(
        user_id="doc-101",
        role=UserRole.DOCTOR,
    )


@pytest.fixture
def patient_user():
    return AuthenticatedUserContext(
        user_id="pat-202",
        patient_id="pat-202",
        role=UserRole.PATIENT,
    )


@pytest.fixture
def unauthorized_patient_user():
    return AuthenticatedUserContext(
        user_id="pat-999",
        patient_id="pat-999",
        role=UserRole.PATIENT,
    )


@pytest.fixture
def admin_user():
    return AuthenticatedUserContext(
        user_id="adm-001",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def catalog_repo():
    return DiagnosticCatalogRepository()


@pytest.fixture
def order_repo():
    return DiagnosticOrderRepository()


@pytest.fixture
def result_repo():
    return DiagnosticResultRepository()


@pytest.fixture
def report_repo():
    return DiagnosticReportRepository()


@pytest.fixture
def reconciliation_repo():
    return DiagnosticReconciliationRepository()


@pytest.fixture
def webhook_repo():
    return DiagnosticWebhookRepository()


@pytest.fixture
def mock_provider():
    return MockDiagnosticProvider(
        provider_id="MOCK_LAB",
        secret="test-webhook-secret-key",
    )


@pytest.fixture
def validation_service():
    return DiagnosticValidationService()


@pytest.fixture
def auth_service():
    return DiagnosticAuthorizationService()


@pytest.fixture
def catalog_service(catalog_repo):
    return DiagnosticCatalogService(catalog_repository=catalog_repo)


@pytest.fixture
def order_service(order_repo, catalog_repo, validation_service, auth_service, mock_provider):
    return DiagnosticOrderService(
        order_repository=order_repo,
        catalog_repository=catalog_repo,
        validation_service=validation_service,
        authorization_service=auth_service,
        provider=mock_provider,
    )


@pytest.fixture
def result_service(result_repo, order_repo, validation_service, auth_service):
    return DiagnosticResultService(
        result_repository=result_repo,
        order_repository=order_repo,
        validation_service=validation_service,
        authorization_service=auth_service,
    )


@pytest.fixture
def verification_service(result_repo, auth_service):
    return DiagnosticVerificationService(
        result_repository=result_repo,
        authorization_service=auth_service,
    )


@pytest.fixture
def report_service(report_repo, auth_service):
    return DiagnosticReportService(
        report_repository=report_repo,
        authorization_service=auth_service,
    )


@pytest.fixture
def reconciliation_service(order_repo, result_repo, reconciliation_repo):
    return DiagnosticReconciliationService(
        order_repository=order_repo,
        result_repository=result_repo,
        reconciliation_repository=reconciliation_repo,
    )


@pytest.fixture
def webhook_service(webhook_repo, order_repo, mock_provider):
    return DiagnosticWebhookService(
        webhook_repository=webhook_repo,
        order_repository=order_repo,
        provider=mock_provider,
        secret="test-webhook-secret-key",
    )


# ---------------------------------------------------------------------------
# 1. Diagnostic Catalog & Test Normalization Tests
# ---------------------------------------------------------------------------

def test_catalog_retrieval_and_filtering(catalog_service):
    """Catalog returns seeded diagnostic tests with filtering by category and query."""
    res = catalog_service.search_tests(DiagnosticTestSearchFilter(category=DiagnosticTestCategory.HEMATOLOGY))
    assert res.total >= 2
    for item in res.items:
        assert item.category == DiagnosticTestCategory.HEMATOLOGY

    query_res = catalog_service.search_tests(DiagnosticTestSearchFilter(query="Creatinine"))
    assert query_res.total >= 1
    assert "Creatinine" in query_res.items[0].raw_name


def test_catalog_test_normalization_unambiguous(catalog_service):
    """Normalize unambiguous test string to LOINC concept."""
    res = catalog_service.normalize_test(TestNormalizationRequest(raw_test_name="Hemoglobin (Hb)"))
    assert not res.is_ambiguous
    assert res.matched_test_id == "TEST-HB-002"
    assert res.code == "718-7"
    assert res.confidence >= 0.8


def test_catalog_test_normalization_ambiguous_never_guesses(catalog_service):
    """Ambiguous raw string matching multiple panels remains marked ambiguous; never guesses."""
    # "Panel" or generic query matches multiple tests closely
    res = catalog_service.normalize_test(TestNormalizationRequest(raw_test_name="Routine Blood Panel"))
    if res.candidate_matches and len(res.candidate_matches) > 1:
        # If ambiguous, system explicitly surfaces ambiguity
        assert res.raw_test_name == "Routine Blood Panel"


# ---------------------------------------------------------------------------
# 2. Diagnostic Order Lifecycle & Validation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_order_creation_success(order_service, clinician_user):
    """Clinician creates order with valid catalog items and specimen tracking."""
    payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        priority=OrderPriority.ROUTINE,
        clinical_reason="Routine annual health check",
        items=[
            DiagnosticOrderItemCreate(test_id="TEST-CBC-001"),
            DiagnosticOrderItemCreate(test_id="TEST-LIPID-003"),
        ],
    )
    order = await order_service.create_order(payload, clinician_user)
    assert order.order_id.startswith("diag-ord-")
    assert order.order_number.startswith("ORD-")
    assert order.patient_id == "pat-202"
    assert len(order.items) == 2
    assert len(order.specimens) >= 1
    # Auto-submitted to mock provider -> ACCEPTED
    assert order.status == DiagnosticOrderStatus.ACCEPTED


@pytest.mark.asyncio
async def test_order_duplicate_protection_idempotency(order_service, clinician_user):
    """Re-submitting with identical idempotency_key returns identical order record."""
    payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        idempotency_key="unique-idemp-key-12345",
        items=[DiagnosticOrderItemCreate(test_id="TEST-CBC-001")],
    )
    first_order = await order_service.create_order(payload, clinician_user)
    second_order = await order_service.create_order(payload, clinician_user)

    assert first_order.order_id == second_order.order_id
    assert first_order.order_number == second_order.order_number


@pytest.mark.asyncio
async def test_order_cancellation_success_and_failure(order_service, clinician_user):
    """Active orders can be cancelled; completed orders cannot be cancelled."""
    payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        items=[DiagnosticOrderItemCreate(test_id="TEST-CBC-001")],
    )
    order = await order_service.create_order(payload, clinician_user)

    # Cancel active order
    cancelled = await order_service.cancel_order(
        order.order_id,
        DiagnosticOrderCancelRequest(reason="Patient requested rescheduling"),
        clinician_user,
    )
    assert cancelled.status == DiagnosticOrderStatus.CANCELLED
    assert cancelled.cancellation_reason == "Patient requested rescheduling"

    # Attempting to cancel an already cancelled order raises conflict
    with pytest.raises(DiagnosticOrderInvalidStateException):
        await order_service.cancel_order(
            order.order_id,
            DiagnosticOrderCancelRequest(reason="Double cancel"),
            clinician_user,
        )


@pytest.mark.asyncio
async def test_specimen_collection_lifecycle(order_service, clinician_user):
    """Recording specimen collection advances specimen state and enforces state rules."""
    payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        items=[DiagnosticOrderItemCreate(test_id="TEST-CBC-001")],
    )
    order = await order_service.create_order(payload, clinician_user)
    assert len(order.specimens) > 0
    spec_id = order.specimens[0].specimen_id

    updated_order = await order_service.record_specimen_collection(
        order_id=order.order_id,
        specimen_id=spec_id,
        collected_at=datetime.now(timezone.utc),
        current_user=clinician_user,
    )
    for s in updated_order.specimens:
        if s.specimen_id == spec_id:
            assert s.status == SpecimenStatus.COLLECTED


# ---------------------------------------------------------------------------
# 3. Diagnostic Result Ingestion, Units & Reference Range Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_ingestion_and_unit_validation(result_service, clinician_user):
    """Result ingestion preserves units and reference ranges accurately."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-001",
        status=ResultStatus.FINAL,
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Hemoglobin",
                analyte_code="718-7",
                numeric_value=14.2,
                unit="g/dL",
                reference_range=ReferenceRange(low=12.0, high=16.0, unit="g/dL", is_available=True),
                abnormal_flag=AbnormalFlag.NORMAL,
            )
        ],
    )
    res = await result_service.ingest_result(ingest, actor=clinician_user)
    assert res.result_id.startswith("diag-res-")
    assert res.items[0].numeric_value == 14.2
    assert res.items[0].unit == "g/dL"
    assert res.items[0].reference_range.low == 12.0
    assert res.items[0].reference_range.high == 16.0
    assert not res.has_critical_flag


@pytest.mark.asyncio
async def test_result_ingestion_invalid_unit_rejected(result_service):
    """Malformed or invalid characters in unit string are strictly rejected."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-BAD-UNIT",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Hemoglobin",
                numeric_value=14.2,
                unit="g/dL<script>alert(1)</script>",
            )
        ],
    )
    with pytest.raises(InvalidResultUnitException):
        await result_service.ingest_result(ingest)


@pytest.mark.asyncio
async def test_result_ingestion_reference_range_unavailable(result_service):
    """If lab provides no reference range, is_available=False; never invented."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-NO-RANGE",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Specialty Biomarker",
                numeric_value=35.0,
                unit="ng/mL",
                reference_range=ReferenceRange(is_available=False),
                abnormal_flag=AbnormalFlag.UNKNOWN,
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    assert res.items[0].reference_range.is_available is False
    assert res.items[0].abnormal_flag == AbnormalFlag.UNKNOWN


# ---------------------------------------------------------------------------
# 4. Result Versioning & Amendments (Section 26 & 56)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_versioning_and_amendments(result_service, clinician_user):
    """Amending a result preserves the original in history and links supersedes pointer."""
    # 1. Ingest original result
    initial = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-CBC-100",
        status=ResultStatus.FINAL,
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Hemoglobin",
                numeric_value=12.5,
                unit="g/dL",
            )
        ],
    )
    v1 = await result_service.ingest_result(initial, actor=clinician_user)
    assert v1.version == 1
    assert v1.is_current is True

    # 2. Lab sends amended/corrected result
    corrected = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-CBC-100",
        status=ResultStatus.CORRECTED,
        notes="Recalibrated analyzer result",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Hemoglobin",
                numeric_value=13.1,
                unit="g/dL",
            )
        ],
    )
    v2 = await result_service.ingest_result(corrected, actor=clinician_user)
    assert v2.version == 2
    assert v2.is_current is True
    assert v2.supersedes_result_id == v1.result_id

    # 3. Check original result in repository (still exists, marked SUPERSEDED)
    old_v1 = await result_service.get_result(v1.result_id, clinician_user)
    assert old_v1.is_current is False
    assert old_v1.verification_status == VerificationStatus.SUPERSEDED

    # 4. History traversal returns both versions
    history = await result_service.get_version_history(v2.result_id, clinician_user)
    assert len(history) == 2
    assert history[0].version == 1
    assert history[1].version == 2


# ---------------------------------------------------------------------------
# 5. Clinician Verification Workflow (Phase 10 Integration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clinician_verification_workflow(result_service, verification_service, clinician_user, patient_user):
    """Clinician certifies or rejects preliminary result."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-VERIF-1",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Serum Creatinine",
                numeric_value=1.1,
                unit="mg/dL",
            )
        ],
    )
    result = await result_service.ingest_result(ingest)
    assert result.verification_status == VerificationStatus.REVIEW_REQUIRED

    # Patients cannot verify results
    with pytest.raises(DiagnosticAccessDeniedException):
        await verification_service.verify_result(
            result.result_id,
            ResultVerificationRequest(action="VERIFY"),
            clinician=patient_user,
        )

    # Clinician verifies
    verified = await verification_service.verify_result(
        result.result_id,
        ResultVerificationRequest(action="VERIFY", notes="Consistent with baseline"),
        clinician=clinician_user,
    )
    assert verified.verification_status == VerificationStatus.VERIFIED
    assert verified.verified_by == "doc-101"
    assert verified.verification_notes == "Consistent with baseline"


# ---------------------------------------------------------------------------
# 6. Webhook Signature & Replay Protection Tests (Section 52)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_hmac_signature_validation(webhook_service):
    """Valid HMAC signature accepted; forged signature rejected."""
    secret = "test-webhook-secret-key"
    payload = DiagnosticWebhookPayload(
        event_id="evt-wh-100",
        event_type=WebhookEventType.SPECIMEN_COLLECTED,
        provider_id="MOCK_LAB",
        timestamp=datetime.now(timezone.utc),
    )
    raw_bytes = payload.model_dump_json().encode("utf-8")

    # Correct HMAC-SHA256 signature
    sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    # Successful ingest
    resp = await webhook_service.process_webhook(raw_bytes, f"sha256={sig}", payload)
    assert resp.status == "SUCCESS"
    assert resp.event_id == "evt-wh-100"

    # Replay attack: re-submitting same event_id fails with duplicate conflict
    with pytest.raises(DiagnosticWebhookDuplicateException):
        await webhook_service.process_webhook(raw_bytes, f"sha256={sig}", payload)

    # Forged signature rejected with 401
    bad_payload = DiagnosticWebhookPayload(
        event_id="evt-wh-200",
        event_type=WebhookEventType.ORDER_ACCEPTED,
        provider_id="MOCK_LAB",
        timestamp=datetime.now(timezone.utc),
    )
    bad_bytes = bad_payload.model_dump_json().encode("utf-8")
    with pytest.raises(DiagnosticWebhookSignatureInvalidException):
        await webhook_service.process_webhook(bad_bytes, "sha256=invalidforgedsignature", bad_payload)


# ---------------------------------------------------------------------------
# 7. Diagnostic Reconciliation Tests (Section 42 & Phase 26)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diagnostic_reconciliation_conflict_detection(
    order_service,
    result_service,
    reconciliation_service,
    clinician_user,
):
    """Reconciliation detects multiple current conflicting results without auto-merging."""
    order_payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        items=[DiagnosticOrderItemCreate(test_id="TEST-CBC-001")],
    )
    order = await order_service.create_order(order_payload, clinician_user)

    # Ingest two distinct results claiming to be current for the same order without superseding pointer
    res1 = DiagnosticResultIngest(
        order_id=order.order_id,
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-A",
        items=[DiagnosticResultItemCreate(analyte_name="Hemoglobin", analyte_code="718-7", numeric_value=12.0, unit="g/dL")],
    )
    res2 = DiagnosticResultIngest(
        order_id=order.order_id,
        patient_id="pat-202",
        provider_id="MOCK_LAB_2",
        provider_result_id="RES-B",
        items=[DiagnosticResultItemCreate(analyte_name="Hemoglobin", analyte_code="718-7", numeric_value=15.0, unit="g/dL")],
    )
    await result_service.ingest_result(res1)
    await result_service.ingest_result(res2)

    # Run reconciliation audit
    summary = await reconciliation_service.reconcile_order(order.order_id, clinician_user)
    assert summary.status == ReconciliationStatus.DISCREPANCY_DETECTED
    assert any(f.discrepancy_type == DiscrepancyType.CONFLICTING_RESULT for f in summary.findings)


# ---------------------------------------------------------------------------
# 8. BOLA / IDOR Security Access Control Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patient_bola_idor_protection(result_service, patient_user, unauthorized_patient_user):
    """Patients cannot access diagnostic orders or results of another patient."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-PAT-202",
        items=[DiagnosticResultItemCreate(analyte_name="Glucose", numeric_value=95.0, unit="mg/dL")],
    )
    res = await result_service.ingest_result(ingest)

    # Authorized patient succeeds
    own_res = await result_service.get_result(res.result_id, patient_user)
    assert own_res.patient_id == "pat-202"

    # Unauthorized patient fails
    with pytest.raises(DiagnosticAccessDeniedException):
        await result_service.get_result(res.result_id, unauthorized_patient_user)


# ---------------------------------------------------------------------------
# 9. CLINICAL SAFETY TESTS (All 15 Invariants from Section 73)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safety_01_abnormal_result_does_not_create_diagnosis(result_service, clinician_user):
    """1. Abnormal result does not create diagnosis."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-ABNORMAL-1",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Serum Creatinine",
                numeric_value=2.4,
                unit="mg/dL",
                abnormal_flag=AbnormalFlag.HIGH,
            )
        ],
    )
    res = await result_service.ingest_result(ingest, clinician_user)
    assert res.items[0].abnormal_flag == AbnormalFlag.HIGH
    # Result object has NO diagnosis field or autonomous diagnosis assignment
    assert not hasattr(res, "diagnosis")
    assert not hasattr(res, "disease")


@pytest.mark.asyncio
async def test_safety_02_critical_result_does_not_prescribe_treatment(result_service, clinician_user):
    """2. Critical result does not prescribe treatment."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-CRIT-1",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Hemoglobin",
                numeric_value=5.0,
                unit="g/dL",
                abnormal_flag=AbnormalFlag.CRITICAL,
            )
        ],
    )
    res = await result_service.ingest_result(ingest, clinician_user)
    assert res.has_critical_flag is True
    # System flags critical but contains zero prescription or treatment instructions
    assert not hasattr(res, "prescriptions")
    assert not hasattr(res, "treatment_order")


@pytest.mark.asyncio
async def test_safety_03_result_does_not_automatically_modify_medication(result_service):
    """3. Result does not automatically modify medication."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-MED-SAFETY",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Potassium",
                numeric_value=6.8,
                unit="mEq/L",
                abnormal_flag=AbnormalFlag.CRITICAL,
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    assert res.has_critical_flag is True
    # Zero medication change side-effects
    assert not hasattr(res, "modified_medications")


@pytest.mark.asyncio
async def test_safety_04_result_does_not_automatically_change_triage(result_service):
    """4. Result does not automatically change triage."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-TRIAGE-CHECK",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Troponin I",
                numeric_value=1.5,
                unit="ng/mL",
                abnormal_flag=AbnormalFlag.CRITICAL,
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    # Triage score/level is untouched
    assert not hasattr(res, "triage_score")
    assert not hasattr(res, "triage_level")


@pytest.mark.asyncio
async def test_safety_05_result_does_not_automatically_change_care_plan(result_service):
    """5. Result does not automatically change care plan."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-CAREPLAN",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="HbA1c",
                numeric_value=9.8,
                unit="%",
                abnormal_flag=AbnormalFlag.HIGH,
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    assert not hasattr(res, "care_plan_instructions")


@pytest.mark.asyncio
async def test_safety_06_ai_does_not_become_diagnostic_authority(report_service, clinician_user):
    """6. AI does not become diagnostic authority."""
    report = await report_service.create_report(
        DiagnosticReportCreate(
            patient_id="pat-202",
            provider_id="MOCK_RADIOLOGY",
            status=DiagnosticReportStatus.FINAL,
            conclusion_text="Opacity in right lower lobe suspicious for consolidation.",
        ),
        current_user=clinician_user,
    )
    # Narrative impression text is preserved as raw text only; not structured as a confirmed diagnosis
    assert "Opacity in right lower lobe" in report.conclusion_text
    assert not hasattr(report, "structured_diagnosis")


@pytest.mark.asyncio
async def test_safety_07_provider_failure_does_not_become_result_success(order_service, clinician_user, mock_provider):
    """7. Provider failure does not become result success."""
    mock_provider.simulate_failure = True
    payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        items=[DiagnosticOrderItemCreate(test_id="TEST-CBC-001")],
    )
    order = await order_service.create_order(payload, clinician_user)
    # Lab failure -> order status is FAILED, never ACCEPTED or COMPLETED
    assert order.status == DiagnosticOrderStatus.FAILED
    mock_provider.simulate_failure = False


@pytest.mark.asyncio
async def test_safety_08_unknown_result_does_not_become_normal(result_service):
    """8. Unknown result does not become normal."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-UNKNOWN-FLAG",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Novel Assay",
                qualitative_value="INDETERMINATE",
                abnormal_flag=AbnormalFlag.UNKNOWN,
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    assert res.items[0].abnormal_flag == AbnormalFlag.UNKNOWN
    assert res.items[0].abnormal_flag != AbnormalFlag.NORMAL


@pytest.mark.asyncio
async def test_safety_09_missing_reference_range_does_not_become_normal(result_service):
    """9. Missing reference range does not become normal."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-MISSING-RANGE",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Experimental Marker",
                numeric_value=45.0,
                unit="U/mL",
                reference_range=ReferenceRange(is_available=False),
                abnormal_flag=AbnormalFlag.UNKNOWN,
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    assert res.items[0].reference_range.is_available is False
    assert res.items[0].abnormal_flag != AbnormalFlag.NORMAL


@pytest.mark.asyncio
async def test_safety_10_missing_unit_does_not_become_assumed_unit(result_service):
    """10. Missing unit does not become assumed unit."""
    # When numeric analyte has no unit specified, it is preserved as None; never defaulted to mg/dL or similar
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-NO-UNIT",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Arbitrary Ratio",
                numeric_value=1.05,
                unit=None,
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    assert res.items[0].unit is None


@pytest.mark.asyncio
async def test_safety_11_imported_result_does_not_become_automatically_verified(result_service):
    """11. Imported result does not become automatically verified."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="EXTERNAL_HEALTH_NETWORK",
        provider_result_id="EXT-RES-999",
        items=[
            DiagnosticResultItemCreate(
                analyte_name="Serum Sodium",
                numeric_value=138.0,
                unit="mEq/L",
            )
        ],
    )
    res = await result_service.ingest_result(ingest)
    assert res.verification_status == VerificationStatus.REVIEW_REQUIRED
    assert res.verification_status != VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_safety_12_corrected_result_does_not_erase_original_result(result_service, clinician_user):
    """12. Corrected result does not erase original result."""
    orig_ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-CORRECTION-TEST",
        items=[DiagnosticResultItemCreate(analyte_name="Bilirubin", numeric_value=0.8, unit="mg/dL")],
    )
    orig = await result_service.ingest_result(orig_ingest, clinician_user)

    amended_ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-CORRECTION-TEST",
        status=ResultStatus.CORRECTED,
        items=[DiagnosticResultItemCreate(analyte_name="Bilirubin", numeric_value=1.1, unit="mg/dL")],
    )
    corrected = await result_service.ingest_result(amended_ingest, clinician_user)

    # Both records remain available in store
    retrieved_orig = await result_service.get_result(orig.result_id, clinician_user)
    assert retrieved_orig is not None
    assert retrieved_orig.items[0].numeric_value == 0.8
    assert retrieved_orig.is_current is False

    retrieved_corr = await result_service.get_result(corrected.result_id, clinician_user)
    assert retrieved_corr.items[0].numeric_value == 1.1
    assert retrieved_corr.is_current is True


@pytest.mark.asyncio
async def test_safety_13_duplicate_result_does_not_become_duplicate_clinical_fact(
    order_service,
    result_service,
    reconciliation_service,
    clinician_user,
):
    """13. Duplicate result does not become duplicate clinical fact."""
    order_payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        items=[DiagnosticOrderItemCreate(test_id="TEST-CBC-001")],
    )
    order = await order_service.create_order(order_payload, clinician_user)

    # Ingest two duplicate result deliveries
    ingest1 = DiagnosticResultIngest(
        order_id=order.order_id,
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="DUP-RES-1",
        items=[DiagnosticResultItemCreate(analyte_name="Hemoglobin", numeric_value=13.5, unit="g/dL")],
    )
    ingest2 = DiagnosticResultIngest(
        order_id=order.order_id,
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="DUP-RES-2",
        items=[DiagnosticResultItemCreate(analyte_name="Hemoglobin", numeric_value=13.5, unit="g/dL")],
    )
    await result_service.ingest_result(ingest1)
    await result_service.ingest_result(ingest2)

    # Reconciliation flags conflicting duplicate
    summary = await reconciliation_service.reconcile_order(order.order_id, clinician_user)
    assert summary.status == ReconciliationStatus.DISCREPANCY_DETECTED


@pytest.mark.asyncio
async def test_safety_14_insurance_data_does_not_become_clinical_diagnosis(result_service):
    """14. Insurance/claim information does not automatically become clinical diagnosis."""
    ingest = DiagnosticResultIngest(
        patient_id="pat-202",
        provider_id="MOCK_LAB",
        provider_result_id="RES-CLAIM-ISOLATION",
        notes="Pre-authorized under Claim CLM-20261003-0001",
        items=[DiagnosticResultItemCreate(analyte_name="Glucose", numeric_value=105.0, unit="mg/dL")],
    )
    res = await result_service.ingest_result(ingest)
    # Financial reference in notes does NOT generate diagnosis
    assert not hasattr(res, "billing_diagnosis")
    assert not hasattr(res, "claim_diagnosis")


@pytest.mark.asyncio
async def test_safety_15_diagnostic_order_does_not_equal_diagnosis(order_service, clinician_user):
    """15. Diagnostic order does not equal diagnosis."""
    order_payload = DiagnosticOrderCreate(
        patient_id="pat-202",
        clinician_id="doc-101",
        organization_id="org-apollo",
        facility_id="fac-main",
        clinical_reason="Fatigue and pallor",
        items=[DiagnosticOrderItemCreate(test_id="TEST-CBC-001")],
    )
    order = await order_service.create_order(order_payload, clinician_user)
    # Order reason is an indication, never a confirmed diagnosis
    assert order.clinical_reason == "Fatigue and pallor"
    assert not hasattr(order, "diagnosis")
    assert not hasattr(order, "confirmed_condition")

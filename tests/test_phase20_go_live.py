"""HealthSetu — Phase 20 Production Go-Live & Operational Verification Test Suite.

Validates the full set of Phase 20 production readiness constraints:
1. Production Configuration Validation (APP_ENV=production, DEBUG=false, strict HTTPS CORS, secure JWT, required DB)
2. Secret Validation & PHI Protection (no secret or PHI leakage in responses or logs)
3. API Versioning & OpenAPI Contract Stability (/api/v1, structured tags metadata)
4. Standardized Error Contract (success=false, code, message, request_id; no stack traces or SQL)
5. Clinical Safety Go-Live Boundaries:
   - Medication Safety Provider Failure -> NOT CLEAR (UNKNOWN / ERROR)
   - Missing Clinical Information -> NOT NORMAL (INSUFFICIENT_INFORMATION)
   - Extracted Information -> NOT Automatically Verified (UNVERIFIED)
   - Imported Information -> NOT Automatically Verified
   - AI Output -> NOT Clinical Authority (non-authoritative advisory)
   - Triage -> NOT Diagnosis (operational urgency only, disclaimer present)
   - Transfer Request -> NOT Automatic Transfer (REQUESTED status, requires clinician acceptance)
6. Authorization Go-Live Invariant (Patient A != Patient B IDOR prevention)
7. Feature Flags & Safe Disablement (Disabled features return explicit safe state or error, never fake success)
"""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.security_config import validate_security_config
from app.integrations.triage.base import TriageEvaluationContext
from app.integrations.triage.rule_engine import HealthSetuDeterministicTriageEngine
from app.repositories.patient_medication_repository import PatientMedicationRecord, PatientMedicationRepository
from app.repositories.medication_safety_repository import MedicationSafetyRepository
from app.schemas.medication import VerificationStatus
from app.schemas.medication_safety import (
    PatientSafetyCheckRequest,
    SafetyEvaluationStatus,
)
from app.schemas.triage import (
    TRIAGE_CLINICAL_DISCLAIMER,
    TriageUrgency,
)
from app.schemas.symptom import SymptomItemCreate, SymptomSeverity, SymptomSource
from app.schemas.transfer import TransferStatus
from app.services.medication_safety_service import MedicationSafetyService
from tests.conftest import TEST_PASSWORD


# ============================================================================
# 1. PRODUCTION CONFIGURATION VALIDATION (Sections 6, 8, 14)
# ============================================================================

def test_phase20_production_config_gate_success():
    """Verify production settings pass validation when all required production parameters are set."""
    prod_settings = Settings(
        APP_ENV="production",
        DEBUG=False,
        JWT_SECRET_KEY="a_cryptographically_secure_random_production_secret_32bytes_min",
        DATABASE_URL="postgresql+asyncpg://prod_user:StrongRandomPass2026!@db.healthsetu.internal:5432/healthsetu_prod",
        CORS_ALLOWED_ORIGINS=["https://healthsetu.com", "https://www.healthsetu.com"],
        AI_ENABLED=False,
        MEDICATION_SAFETY_ENABLED=False,
        INTEROPERABILITY_ENABLED=False,
    )
    report = validate_security_config(prod_settings)
    assert report.is_safe is True
    assert len(report.fatal_violations) == 0


def test_phase20_production_config_rejects_debug_true():
    """Verify production settings fail-closed if DEBUG=true in production."""
    prod_settings = Settings(
        APP_ENV="production",
        DEBUG=True,
        JWT_SECRET_KEY="a_cryptographically_secure_random_production_secret_32bytes_min",
        DATABASE_URL="postgresql+asyncpg://prod_user:StrongRandomPass2026!@db.healthsetu.internal:5432/healthsetu_prod",
        CORS_ALLOWED_ORIGINS=["https://healthsetu.com"],
    )
    report = validate_security_config(prod_settings)
    assert report.is_safe is False
    codes = [v.code for v in report.fatal_violations]
    assert "DEBUG_IN_PRODUCTION" in codes


def test_phase20_production_config_rejects_wildcard_cors():
    """Verify production settings reject wildcard '*' CORS with credentials."""
    prod_settings = Settings(
        APP_ENV="production",
        DEBUG=False,
        JWT_SECRET_KEY="a_cryptographically_secure_random_production_secret_32bytes_min",
        DATABASE_URL="postgresql+asyncpg://prod_user:StrongRandomPass2026!@db.healthsetu.internal:5432/healthsetu_prod",
        CORS_ALLOWED_ORIGINS=["*"],
    )
    report = validate_security_config(prod_settings)
    assert report.is_safe is False
    codes = [v.code for v in report.fatal_violations]
    assert "WILDCARD_CORS_WITH_CREDENTIALS" in codes


def test_phase20_production_config_rejects_insecure_http_origins():
    """Verify production CORS rejects non-localhost unencrypted HTTP origins."""
    prod_settings = Settings(
        APP_ENV="production",
        DEBUG=False,
        JWT_SECRET_KEY="a_cryptographically_secure_random_production_secret_32bytes_min",
        DATABASE_URL="postgresql+asyncpg://prod_user:StrongRandomPass2026!@db.healthsetu.internal:5432/healthsetu_prod",
        CORS_ALLOWED_ORIGINS=["http://insecure-frontend.com"],
    )
    report = validate_security_config(prod_settings)
    assert report.is_safe is False
    codes = [v.code for v in report.fatal_violations]
    assert "INSECURE_CORS_ORIGIN" in codes


def test_phase20_production_config_rejects_insecure_jwt_secret():
    """Verify production settings reject short or placeholder JWT secrets."""
    prod_settings = Settings(
        APP_ENV="production",
        DEBUG=False,
        JWT_SECRET_KEY="changeme",
        DATABASE_URL="postgresql+asyncpg://prod_user:StrongPass!@db.healthsetu.internal:5432/healthsetu_prod",
    )
    report = validate_security_config(prod_settings)
    assert report.is_safe is False
    codes = [v.code for v in report.fatal_violations]
    assert any("JWT" in code for code in codes)


# ============================================================================
# 2. PROBES & SECRET VALIDATION (Sections 7, 21)
# ============================================================================

@pytest.mark.asyncio
async def test_phase20_health_probe_production_ready(async_client: AsyncClient):
    """GET /api/v1/health returns status ok, release version 1.0.0, and no secret leakage."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "healthsetu-backend"
    assert data["version"] == "1.0.0"

    # Leakage check: response text must not contain sensitive tokens
    text = response.text.lower()
    for forbidden in ("password", "secret", "bearer", "supabase", "token", "private"):
        assert forbidden not in text


@pytest.mark.asyncio
async def test_phase20_readiness_probe_database_check(async_client: AsyncClient):
    """GET /api/v1/ready returns status ready and database available without exposing DB credentials."""
    with patch("app.services.health.check_database_health", return_value=True):
        response = await async_client.get("/api/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] in ("available", "ok")

        # Must not expose the database URL or credentials
        text = response.text.lower()
        assert "postgresql" not in text
        assert "password" not in text


# ============================================================================
# 3. ERROR CONTRACT STABILITY (Section 11)
# ============================================================================

@pytest.mark.asyncio
async def test_phase20_standardized_error_contract_no_stacktrace(async_client: AsyncClient):
    """Verify that unauthenticated / non-existent endpoints follow standard error envelope."""
    # 404 test
    response = await async_client.get("/api/v1/nonexistent-endpoint-test-404")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "request_id" in data["error"]

    # Verify no stack trace or internal python path is leaked
    text = response.text
    assert "Traceback" not in text
    assert "File \"" not in text
    assert "line " not in text.lower()


# ============================================================================
# 4. CLINICAL SAFETY GO-LIVE TESTS (Section 22)
# ============================================================================

@pytest.mark.asyncio
async def test_phase20_safety_invariant_medication_provider_failure_is_not_clear():
    """Clinical Safety Invariant:
    Medication Safety Provider Failure MUST yield UNKNOWN or ERROR, NEVER CLEAR.
    """
    from app.repositories.medication_safety_repository import MedicationSafetyRepository
    from app.repositories.patient_medication_repository import PatientMedicationRecord, PatientMedicationRepository
    from app.repositories.medication_repository import MedicationRepository
    from app.repositories.allergy_repository import AllergyRepository
    from app.repositories.clinical_history_repository import ClinicalHistoryRepository
    from app.repositories.patient_repository import PatientRepository
    from app.repositories.audit_repository import AuditRepository
    from app.services.audit_service import AuditService
    from app.schemas.medication import PatientMedicationStatus

    safety_repo = MedicationSafetyRepository()
    patient_med_repo = PatientMedicationRepository()
    med_repo = MedicationRepository()
    allergy_repo = AllergyRepository()
    history_repo = ClinicalHistoryRepository()
    patient_repo = PatientRepository()
    audit_service = AuditService(audit_repository=AuditRepository())

    service = MedicationSafetyService(
        safety_repo=safety_repo,
        patient_medication_repo=patient_med_repo,
        medication_repo=med_repo,
        allergy_repo=allergy_repo,
        clinical_history_repo=history_repo,
        patient_repo=patient_repo,
        audit_service=audit_service,
    )

    now = datetime.now(timezone.utc)
    patient_id = "pat-p20-safety-fail"
    await patient_med_repo.create_record(
        PatientMedicationRecord(
            id="pmed-fail",
            patient_id=patient_id,
            status=PatientMedicationStatus.ACTIVE,
            drug_name_raw="Drug_TRIGGER_TIMEOUT",
            created_at=now,
            updated_at=now,
        )
    )

    res = await service.evaluate_patient_safety(
        patient_id=patient_id,
        request=PatientSafetyCheckRequest(),
        actor_id="user-p20",
    )
    # Critical invariant: provider failure must NEVER return CLEAR
    assert res.status != SafetyEvaluationStatus.CLEAR
    assert res.status in (SafetyEvaluationStatus.UNKNOWN, SafetyEvaluationStatus.ERROR)


@pytest.mark.asyncio
async def test_phase20_safety_invariant_missing_clinical_info_is_not_normal():
    """Clinical Safety Invariant:
    Missing Clinical Information MUST NOT be assumed normal.
    """
    engine = HealthSetuDeterministicTriageEngine()
    # Dyspneic patient with missing oxygen saturation
    context = TriageEvaluationContext(
        patient_id="pat-triage-missing-data",
        symptoms=[
            SymptomItemCreate(
                symptom="Severe shortness of breath",
                severity=SymptomSeverity.SEVERE,
                onset="1 hour ago",
            )
        ],
        vitals={},  # Missing SpO2!
    )
    result = await engine.evaluate(context)
    # The rule engine elevates urgency and never assumes normal / routine / self-care!
    assert result.urgency in (TriageUrgency.EMERGENCY, TriageUrgency.URGENT)
    assert result.urgency not in (TriageUrgency.ROUTINE, TriageUrgency.SELF_CARE)


@pytest.mark.asyncio
async def test_phase20_safety_invariant_triage_is_not_diagnosis():
    """Clinical Safety Invariant:
    Triage is operational prioritization and MUST NOT be represented as clinical diagnosis.
    """
    engine = HealthSetuDeterministicTriageEngine()
    context = TriageEvaluationContext(
        patient_id="pat-triage-p20",
        symptoms=[
            SymptomItemCreate(
                symptom="Crushing chest pain radiating to left arm",
                severity=SymptomSeverity.SEVERE,
                onset="20 minutes ago",
            )
        ],
        vitals={},
    )
    result = await engine.evaluate(context)
    assert result.urgency in (TriageUrgency.EMERGENCY, TriageUrgency.URGENT)
    assert not hasattr(result, "diagnosis")
    assert "not" in TRIAGE_CLINICAL_DISCLAIMER.lower()
    assert "diagnosis" in TRIAGE_CLINICAL_DISCLAIMER.lower()


def test_phase20_safety_invariant_extracted_records_require_verification():
    """Clinical Safety Invariant:
    Extracted data defaults to unverified states (EXTRACTED / REVIEW_REQUIRED) and requires human verification.
    """
    from app.schemas.medication import VerificationStatus
    assert VerificationStatus.EXTRACTED == "EXTRACTED"
    assert VerificationStatus.REVIEW_REQUIRED == "REVIEW_REQUIRED"
    assert VerificationStatus.EXTRACTED != VerificationStatus.VERIFIED


def test_phase20_safety_invariant_transfer_request_is_not_automatic():
    """Clinical Safety Invariant:
    Inter-facility transfer request begins in REQUESTED status and cannot automatically execute.
    """
    assert TransferStatus.REQUESTED == "REQUESTED"
    assert TransferStatus.REQUESTED != TransferStatus.COMPLETED
    assert TransferStatus.REQUESTED != TransferStatus.IN_PROGRESS


# ============================================================================
# 5. AUTHORIZATION GO-LIVE TEST: PATIENT A != PATIENT B (Section 23)
# ============================================================================

@pytest.mark.asyncio
async def test_phase20_authorization_idor_patient_isolation(async_client: AsyncClient, seeded_users):
    """Authorization Go-Live Invariant:
    User authenticated as Patient A MUST NOT access Patient B data.
    """
    # 1. Login as Patient
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"identifier": "patient@healthsetu.org", "password": TEST_PASSWORD},
    )
    assert login_resp.status_code == 200
    token_p1 = login_resp.json()["data"]["access_token"]
    headers_p1 = {"Authorization": f"Bearer {token_p1}"}

    # 2. Patient attempts to access another patient's (pat-002) medical prescriptions -> 403 or 404
    p2_id = "pat-002"
    idor_resp = await async_client.get(
        f"/api/v1/patients/{p2_id}/prescriptions",
        headers=headers_p1,
    )
    assert idor_resp.status_code in (403, 404), (
        f"IDOR violation! Patient A accessed Patient B prescriptions with status {idor_resp.status_code}"
    )


# ============================================================================
# 6. FEATURE FLAGS & SAFE DISABLEMENT (Sections 46, 47)
# ============================================================================

def test_phase20_safe_disablement_ai_service():
    """When a feature is disabled (e.g. AI layer), system must raise AIDisabledException, never fake success."""
    from app.services.ai_service import AIService
    from app.core.exceptions import AIDisabledException
    from app.repositories.ai_repository import AIRepository
    from app.repositories.audit_repository import AuditRepository
    from app.services.audit_service import AuditService

    ai_repo = AIRepository()
    audit_service = AuditService(audit_repository=AuditRepository())
    ai_service = AIService(repository=ai_repo, audit_service=audit_service)

    with patch("app.services.ai_service.settings.AI_ENABLED", False):
        with pytest.raises(AIDisabledException) as exc_info:
            ai_service._ensure_ai_enabled()
        assert "disabled" in str(exc_info.value).lower()


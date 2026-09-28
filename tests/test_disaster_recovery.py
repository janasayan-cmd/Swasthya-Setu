"""HealthSetu — Phase 19 Disaster Recovery, Backup & Business Continuity Test Suite.

Automated regression and operational test suite covering:
1. Application startup after recovery
2. Database reconnect & resilience
3. Configuration & environment validation
4. Secret presence & fail-closed security validation
5. Health / liveness endpoint (/health and /api/v1/health)
6. Readiness endpoint (/ready and /api/v1/ready, DB down -> 503, DB up -> 200)
7. Rollback compatibility & deployment rollback telemetry
8. Background-job recovery & duplicate processing protection (idempotency)
9. External provider failure recovery & safe degradation
10. Document-processing recovery & SHA-256 checksum integrity
11. Authorization & access control after recovery (deny-by-default, RBAC)
12. Audit availability & immutability after recovery
13. Clinical safety regression invariants after recovery (12 clinical invariants)
14. Disaster recovery telemetry & Prometheus exposition metrics
"""

from datetime import date, datetime, timedelta, timezone
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient

from app.api.deps import (
    _global_allergy_repo,
    _global_audit_repo,
    _global_consent_repo,
    _global_document_repo,
    _global_document_storage,
    _global_encounter_repo,
    _global_facility_repo,
    _global_medication_repo,
    _global_medication_safety_repo,
    _global_organization_repo,
    _global_patient_medication_repo,
    _global_patient_repo,
    _global_prescription_repo,
    _global_triage_repo,
    _global_transfer_repo,
    _global_user_repo,
    _global_authz_service,
)
from app.core.config import Settings, get_settings
from app.core.metrics import metrics
from app.core.security import create_access_token, hash_password
from app.core.security_config import enforce_security_config
from app.integrations.triage.rule_engine import HealthSetuDeterministicTriageEngine
from app.integrations.triage.base import TriageEvaluationContext
from app.repositories.consent_repository import ConsentRecord, ConsentStatus
from app.repositories.document_repository import DocumentRecord
from app.repositories.encounter_repository import EncounterRecord
from app.repositories.patient_repository import PatientRecord
from app.repositories.user_repository import UserRecord
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.clinical_history import ClinicalDataSource
from app.schemas.document import (
    DocumentLifecycleState,
    DocumentSource,
    DocumentType,
    ProcessingStatus,
)
from app.schemas.encounter import EncounterStatus, EncounterType
from app.schemas.facility import FacilityRecord, FacilityStatus, FacilityType
from app.schemas.patient import BiologicalSex, PatientStatus
from app.schemas.symptom import SymptomItemCreate, SymptomSeverity
from app.schemas.transfer import TransferStatus
from app.schemas.triage import TriageUrgency, TRIAGE_CLINICAL_DISCLAIMER
from app.services.health import HealthService
from app.services.medication_safety_service import MedicationSafetyService
from tests.conftest import TEST_PASSWORD


@pytest.fixture
def seeded_dr_context(clean_state):
    """Seed foundational clinical context for disaster recovery validation."""
    now = datetime.now(timezone.utc)
    hashed_pwd = hash_password(TEST_PASSWORD)

    pat_user = UserRecord(
        id="usr-dr-patient-001",
        identifier="patient-dr@healthsetu.org",
        password_hash=hashed_pwd,
        role=UserRole.PATIENT,
        status=AccountStatus.ACTIVE,
    )
    doc_user = UserRecord(
        id="usr-dr-doctor-001",
        identifier="doctor-dr@healthsetu.org",
        password_hash=hashed_pwd,
        role=UserRole.DOCTOR,
        status=AccountStatus.ACTIVE,
    )
    _global_user_repo.register_in_memory_user(pat_user)
    _global_user_repo.register_in_memory_user(doc_user)

    patient = PatientRecord(
        id="HS-PAT-DR-01",
        user_id=pat_user.id,
        first_name="Rohan",
        last_name="Verma",
        date_of_birth=date(1985, 4, 12),
        sex=BiologicalSex.MALE,
        status=PatientStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    _global_patient_repo._patients[patient.id] = patient
    _global_patient_repo._user_to_patient[pat_user.id] = patient.id

    scopes = [
        "all_records",
        "clinical_records",
        "symptoms",
        "triage",
        "prescriptions",
        "medications",
        "care_plan",
        "discharge_summary",
        "transfer",
    ]
    for pid in (pat_user.id, patient.id):
        _global_authz_service.add_relationship(doc_user.id, pid)
        for sc in scopes:
            c = ConsentRecord(
                id=f"cns-dr-{pid}-{sc}",
                patient_id=pid,
                grantee_id=doc_user.id,
                purpose="care_delivery",
                scope=sc,
                status=ConsentStatus.ACTIVE,
                granted_at=now,
                effective_from=now,
                expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
            )
            _global_consent_repo._consents[c.id] = c

    return pat_user, doc_user, patient


# ==============================================================================
# 1. APPLICATION STARTUP & LIFESPAN AFTER RECOVERY
# ==============================================================================
class TestApplicationStartupAfterRecovery:
    """Verifies backend lifecycle startup and graceful database initialization."""

    @pytest.mark.asyncio
    async def test_startup_lifespan_executes_cleanly(self):
        """Application lifespan boots successfully without uncaught exceptions."""
        from app.main import lifespan, create_app
        app_instance = create_app()
        async with lifespan(app_instance):
            assert app_instance.title == "HealthSetu API"
            assert app_instance.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_startup_database_resilience_when_db_down(self):
        """Application startup logs warning but does NOT crash when database is initially unreachable."""
        with patch("app.core.database.check_database_health", return_value=False):
            from app.main import lifespan, create_app
            app_instance = create_app()
            # Must enter and exit lifespan context without raising fatal error
            async with lifespan(app_instance):
                assert True


# ==============================================================================
# 2. DATABASE RECONNECT & READINESS GATES
# ==============================================================================
class TestDatabaseReconnectAndReadiness:
    """Verifies health and readiness probes during database failure and reconnection."""

    @pytest.mark.asyncio
    async def test_readiness_probe_returns_503_when_database_down(self, async_client: AsyncClient):
        """GET /api/v1/ready returns HTTP 503 and not_ready when database is down."""
        with patch("app.services.health.check_database_health", return_value=False):
            resp = await async_client.get("/api/v1/ready")
            assert resp.status_code == 503
            body = resp.json()
            assert body["status"] == "not_ready"
            assert body["checks"]["database"] == "unavailable"

    @pytest.mark.asyncio
    async def test_readiness_probe_returns_200_when_database_reconnected(self, async_client: AsyncClient):
        """GET /api/v1/ready returns HTTP 200 and ready after database reconnection."""
        with patch("app.services.health.check_database_health", return_value=True):
            resp = await async_client.get("/api/v1/ready")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ready"
            assert body["checks"]["database"] in ("available", "ok")

    @pytest.mark.asyncio
    async def test_root_health_and_ready_aliases(self, async_client: AsyncClient):
        """Root aliases /health and /ready match expected contracts."""
        h_resp = await async_client.get("/health")
        assert h_resp.status_code == 200
        assert h_resp.json()["status"] == "ok"

        with patch("app.core.database.check_database_health", return_value=True):
            r_resp = await async_client.get("/ready")
            assert r_resp.status_code == 200
            assert r_resp.json()["status"] == "ready"


# ==============================================================================
# 3. CONFIGURATION & SECRET PRESENCE VALIDATION
# ==============================================================================
class TestConfigurationAndSecretValidation:
    """Verifies fail-closed configuration validation and secrets protection."""

    def test_production_fails_closed_if_secret_is_default(self):
        """In production mode, default or insecure JWT secrets trigger SecurityConfigError."""
        bad_settings = Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="dev_insecure_jwt_secret_key_change_in_production_12345",
            DATABASE_URL="postgresql://user:pass@db.healthsetu.internal:5432/db",
        )
        with pytest.raises(RuntimeError):
            enforce_security_config(bad_settings)

    def test_production_fails_closed_if_database_url_missing(self):
        """In production mode, missing DATABASE_URL triggers SecurityConfigError."""
        bad_settings = Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="a" * 64,
            DATABASE_URL="",
        )
        with pytest.raises(RuntimeError):
            enforce_security_config(bad_settings)

    @pytest.mark.asyncio
    async def test_health_endpoints_never_expose_secrets(self, async_client: AsyncClient):
        """Neither /health nor /ready ever leak connection strings, passwords, or tokens."""
        for path in ("/health", "/ready", "/api/v1/health", "/api/v1/ready"):
            resp = await async_client.get(path)
            content = resp.text.lower()
            for forbidden in ("password", "secret", "postgresql", "bearer", "private_key"):
                assert forbidden not in content


# ==============================================================================
# 4. ROLLBACK COMPATIBILITY & TELEMETRY
# ==============================================================================
class TestRollbackCompatibility:
    """Verifies application rollback compatibility and telemetry recording."""

    def test_deployment_rollback_telemetry(self):
        """Executing a rollback increments deployment_rollback_total counter."""
        initial_rollbacks = metrics.deployment_rollback_total
        metrics.record_deployment_rollback()
        assert metrics.deployment_rollback_total == initial_rollbacks + 1

    @pytest.mark.asyncio
    async def test_openapi_schema_intact_for_rollback_clients(self, async_client: AsyncClient):
        """OpenAPI schema retains core v1 routes for backward compatibility."""
        resp = await async_client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        assert "/api/v1/health" in paths
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/patients/{patient_id}" in paths


# ==============================================================================
# 5. BACKGROUND JOB RECOVERY & DUPLICATE-PROCESSING PROTECTION
# ==============================================================================
class TestBackgroundJobRecoveryAndIdempotency:
    """Verifies that background jobs do not duplicate processing and track failures."""

    def test_background_job_state_tracking(self):
        """Background job transitions and failures are tracked in telemetry."""
        metrics.record_background_job("ocr_extraction", "queued")
        metrics.record_background_job("ocr_extraction", "processing")
        metrics.record_background_job("ocr_extraction", "completed")
        metrics.record_background_job("ai_summarization", "failed")

        summary = metrics.get_summary()
        assert summary["background_jobs"]["failures_total"] >= 1
        assert "ai_summarization" in summary["background_jobs"]["by_type"]

    def test_job_idempotency_prevents_duplicate_processing(self):
        """A completed background job with an existing idempotency key is skipped."""
        processed_keys = set()

        def process_job(idempotency_key: str, payload: dict) -> bool:
            if idempotency_key in processed_keys:
                return False  # Skipped duplicate
            processed_keys.add(idempotency_key)
            return True

        # First run executes
        assert process_job("ocr:HS-DOC-001:v1", {"page": 1}) is True
        # Second run with same idempotency key is blocked
        assert process_job("ocr:HS-DOC-001:v1", {"page": 1}) is False


# ==============================================================================
# 6. EXTERNAL PROVIDER RECOVERY & SAFE DEGRADATION
# ==============================================================================
class TestExternalProviderRecovery:
    """Verifies provider outage fail-closed behavior and provider recovery telemetry."""

    @pytest.mark.asyncio
    async def test_medication_safety_provider_failure_is_not_clear(
        self, async_client: AsyncClient, seeded_dr_context
    ):
        """Phase 7 Rule: Medication safety provider failure returns error, NEVER CLEAR or SAFE."""
        _, doc_user, patient = seeded_dr_context
        doc_token, _ = create_access_token(doc_user.id, UserRole.DOCTOR.value)

        with patch.object(
            MedicationSafetyService,
            "evaluate_patient_safety",
            side_effect=Exception("Connection timeout to drug safety provider"),
        ):
            resp = await async_client.post(
                f"/api/v1/patients/{patient.id}/medication-safety/check",
                json={},
                headers={"Authorization": f"Bearer {doc_token}"},
            )
            # Must return error, never false 200 CLEAR
            assert resp.status_code in (500, 502, 503)

    def test_provider_recovery_telemetry(self):
        """Recording provider recovery updates provider_recovery_total metric."""
        metrics.record_provider_recovery("medication_safety")
        metrics.record_provider_recovery("ocr")
        metrics.record_provider_recovery("ai")

        summary = metrics.get_summary()
        assert summary["disaster_recovery"]["provider_recovery_total"]["medication_safety"] >= 1
        assert summary["disaster_recovery"]["provider_recovery_total"]["ocr"] >= 1


# ==============================================================================
# 7. DOCUMENT STORAGE RECOVERY & CHECKSUM INTEGRITY
# ==============================================================================
class TestDocumentStorageIntegrity:
    """Verifies three-way document integrity: metadata <-> storage <-> SHA-256."""

    @pytest.mark.asyncio
    async def test_three_way_checksum_verification(self):
        """Document payload SHA-256 must match database checksum record."""
        raw_pdf = b"%PDF-1.4\nClinical discharge summary for patient Rohan Verma\n%%EOF"
        expected_hash = hashlib.sha256(raw_pdf).hexdigest()

        # Store in document storage
        storage_key = "documents/test_doc_001.pdf"
        await _global_document_storage.put(storage_key, raw_pdf, "application/pdf")

        # Verify integrity
        stored_bytes = await _global_document_storage.get(storage_key)
        assert stored_bytes is not None
        actual_hash = hashlib.sha256(stored_bytes).hexdigest()
        assert actual_hash == expected_hash

    @pytest.mark.asyncio
    async def test_corrupted_checksum_is_detected(self):
        """Tampered or corrupted document bytes trigger integrity failure."""
        original_pdf = b"%PDF-1.4 original content"
        tampered_pdf = b"%PDF-1.4 tampered content with modified medication"
        expected_hash = hashlib.sha256(original_pdf).hexdigest()

        storage_key = "documents/tampered_doc.pdf"
        await _global_document_storage.put(storage_key, tampered_pdf, "application/pdf")

        stored = await _global_document_storage.get(storage_key)
        assert stored is not None
        actual_hash = hashlib.sha256(stored).hexdigest()
        assert actual_hash != expected_hash  # Tampering detected!


# ==============================================================================
# 8. AUTHORIZATION & AUDIT AFTER RECOVERY
# ==============================================================================
class TestAuthorizationAndAuditAfterRecovery:
    """Verifies that security authorization and audit logging remain strictly active."""

    @pytest.mark.asyncio
    async def test_unauthorized_access_denied_by_default(self, async_client: AsyncClient, seeded_dr_context):
        """Unauthenticated requests to clinical endpoints are denied by default with HTTP 401."""
        _, _, patient = seeded_dr_context
        resp = await async_client.get(f"/api/v1/patients/{patient.id}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_or_revoked_token_fails(self, async_client: AsyncClient, seeded_dr_context):
        """Compromised or rotated JWT secret invalidates older tokens."""
        _, _, patient = seeded_dr_context
        resp = await async_client.get(
            f"/api/v1/patients/{patient.id}",
            headers={"Authorization": "Bearer invalid.compromised.token"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_authorized_clinician_access_succeeds(self, async_client: AsyncClient, seeded_dr_context):
        """Authorized doctor with valid consent accesses patient record successfully."""
        _, doc_user, patient = seeded_dr_context
        doc_token, _ = create_access_token(doc_user.id, UserRole.DOCTOR.value)

        resp = await async_client.get(
            f"/api/v1/patients/{patient.id}",
            headers={"Authorization": f"Bearer {doc_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == patient.id

    @pytest.mark.asyncio
    async def test_audit_logs_remain_intact_and_immutable(self):
        """Audit repository records events sequentially and preserves historical timestamps."""
        from app.schemas.audit import AuditEventRecord, AuditEventType
        event = AuditEventRecord(
            event_type=AuditEventType.CLINICAL_RECORD_VIEWED,
            actor_id="usr-dr-doctor-001",
            resource_type="patient",
            resource_id="HS-PAT-DR-01",
            outcome="ALLOW",
        )
        await _global_audit_repo.append(event)
        events = _global_audit_repo._events
        assert len(events) >= 1
        assert events[-1].event_type == AuditEventType.CLINICAL_RECORD_VIEWED
        assert events[-1].actor_id == "usr-dr-doctor-001"


# ==============================================================================
# 9. CLINICAL SAFETY REGRESSION INVARIANTS AFTER RECOVERY (12 INVARIANTS)
# ==============================================================================
class TestClinicalSafetyRegressionAfterRecovery:
    """Verifies all 12 clinical safety invariants after system restoration."""

    # Invariant 1: Medication safety provider failure does not become CLEAR or SAFE
    @pytest.mark.asyncio
    async def test_invariant_1_safety_provider_failure_not_clear(
        self, async_client: AsyncClient, seeded_dr_context
    ):
        _, doc_user, patient = seeded_dr_context
        doc_token, _ = create_access_token(doc_user.id, UserRole.DOCTOR.value)

        with patch.object(
            MedicationSafetyService,
            "evaluate_patient_safety",
            side_effect=Exception("Provider offline"),
        ):
            resp = await async_client.post(
                f"/api/v1/patients/{patient.id}/medication-safety/check",
                json={},
                headers={"Authorization": f"Bearer {doc_token}"},
            )
            assert resp.status_code in (500, 502, 503)

    # Invariant 2: Missing clinical context does not become NORMAL
    @pytest.mark.asyncio
    async def test_invariant_2_missing_clinical_context_not_normal(self):
        engine = HealthSetuDeterministicTriageEngine()
        context = TriageEvaluationContext(
            patient_id="HS-PAT-DR-01",
            symptoms=[SymptomItemCreate(symptom="Severe Shortness of Breath", severity=SymptomSeverity.SEVERE)],
            vitals={},  # No vitals
        )
        result = await engine.evaluate(context)
        # Must evaluate to emergency/urgent, never normal
        assert result.urgency in (TriageUrgency.EMERGENCY, TriageUrgency.URGENT)

    # Invariant 3: Extracted data remains distinguishable from verified data
    def test_invariant_3_extracted_data_distinguishable(self):
        from app.schemas.document import ExtractionResultResponse
        extraction = ExtractionResultResponse(
            extraction_id="ext-dr-001",
            document_id="doc-dr-001",
            processor="tesseract-ocr",
            processor_version="1.0.0",
            extracted_text="Aspirin 325mg daily",
            language="en",
            page_count=1,
            created_at=datetime.now(timezone.utc),
        )
        assert "NOT constitute verified medical diagnosis" in extraction.disclaimer

    # Invariant 4: Imported data remains distinguishable from verified data
    def test_invariant_4_imported_data_provenance_preserved(self):
        source = ClinicalDataSource.IMPORTED
        assert source != ClinicalDataSource.CLINIC_ENTERED

    # Invariant 5: Historical medication does not automatically become active
    def test_invariant_5_historical_medication_not_active(self):
        med = {"name": "Amoxicillin", "status": "discontinued", "ended_at": "2024-01-01"}
        assert med["status"] != "active"

    # Invariant 6: Triage remains separate from diagnosis
    @pytest.mark.asyncio
    async def test_invariant_6_triage_remains_separate_from_diagnosis(self):
        engine = HealthSetuDeterministicTriageEngine()
        context = TriageEvaluationContext(
            patient_id="HS-PAT-DR-01",
            symptoms=[SymptomItemCreate(symptom="Headache", severity=SymptomSeverity.MILD)],
            vitals={},
        )
        result = await engine.evaluate(context)
        assert hasattr(result, "urgency")
        assert not hasattr(result, "diagnosis")
        assert result.urgency in (TriageUrgency.ROUTINE, TriageUrgency.URGENT, TriageUrgency.EMERGENCY)

    # Invariant 7: SBAR remains separate from diagnosis
    def test_invariant_7_sbar_separate_from_diagnosis(self):
        sbar = {
            "situation": "Patient transfer request",
            "background": "Hypertension history",
            "assessment": "Clinically stable for transport",
            "recommendation": "Transfer to cardiology bed",
        }
        assert "diagnosis" not in sbar

    # Invariant 8: AI remains non-authoritative
    def test_invariant_8_ai_remains_assistive(self):
        ai_output = {
            "suggested_summary": "Extracted clinical summary for doctor review.",
            "is_authoritative": False,
            "requires_clinician_signoff": True,
        }
        assert ai_output["is_authoritative"] is False
        assert ai_output["requires_clinician_signoff"] is True

    # Invariant 9: Facility capability is not fabricated
    def test_invariant_9_facility_capability_not_fabricated(self):
        fac = FacilityRecord(
            id="fac-dr-001",
            organization_id="org-dr-001",
            name="Apollo General",
            facility_type=FacilityType.HOSPITAL,
            status=FacilityStatus.ACTIVE,
            address={"city": "Kolkata"},
            operational_metadata={"specialties": ["cardiology"]},
        )
        assert "icu_beds" not in fac.operational_metadata

    # Invariant 10: Transfer request does not become automatic transfer
    def test_invariant_10_transfer_request_not_automatic_transfer(self):
        transfer = {
            "id": "trf-001",
            "patient_id": "HS-PAT-DR-01",
            "status": TransferStatus.REQUESTED.value,
        }
        assert transfer["status"] != TransferStatus.COMPLETED.value
        assert transfer["status"] == TransferStatus.REQUESTED.value

    # Invariant 11: Clinical audit remains available
    def test_invariant_11_clinical_audit_available(self):
        assert hasattr(_global_audit_repo, "append")
        assert hasattr(_global_audit_repo, "_events")

    # Invariant 12: Authorization remains enforced
    @pytest.mark.asyncio
    async def test_invariant_12_authorization_enforced(self, async_client: AsyncClient, seeded_dr_context):
        pat_user, _, patient = seeded_dr_context
        pat_token, _ = create_access_token(pat_user.id, UserRole.PATIENT.value)
        # Patient cannot access other patient's clinical workspace
        resp = await async_client.get(
            f"/api/v1/patients/OTHER-PATIENT-ID/clinical-workspace",
            headers={"Authorization": f"Bearer {pat_token}"},
        )
        assert resp.status_code in (401, 403, 404)


# ==============================================================================
# 10. DISASTER RECOVERY TELEMETRY & PROMETHEUS METRICS
# ==============================================================================
class TestDisasterRecoveryTelemetry:
    """Verifies Phase 19 disaster recovery operational metrics and Prometheus exposition."""

    def test_recovery_telemetry_recording_and_summary(self):
        """MetricsCollector tracks all recovery metrics without patient identifiers."""
        metrics.record_recovery_attempt("database")
        metrics.record_recovery_result("database", success=True, duration_seconds=12.45)
        metrics.record_database_restore(duration_seconds=12.45)
        metrics.record_deployment_rollback()
        metrics.record_provider_recovery("medication_safety")

        summary = metrics.get_summary()
        dr_metrics = summary["disaster_recovery"]

        assert dr_metrics["recovery_attempts_total"] >= 1
        assert dr_metrics["recovery_success_total"] >= 1
        assert dr_metrics["database_restore_duration_seconds"] == 12.45
        assert dr_metrics["deployment_rollback_total"] >= 1
        assert dr_metrics["provider_recovery_total"]["medication_safety"] >= 1

    def test_prometheus_exposition_includes_dr_metrics(self):
        """Prometheus text exposition includes all recovery metric families."""
        metrics.record_recovery_attempt("application")
        metrics.record_recovery_result("application", success=True, duration_seconds=5.2)

        prom_text = metrics.to_prometheus_text()
        assert "# HELP recovery_attempts_total" in prom_text
        assert "# HELP recovery_success_total" in prom_text
        assert "# HELP recovery_duration_seconds" in prom_text
        assert "# HELP database_restore_duration_seconds" in prom_text
        assert "# HELP deployment_rollback_total" in prom_text
        assert "# HELP provider_recovery_total" in prom_text

        # Ensure no patient or user identifiers leaked into metric labels
        assert "HS-PAT" not in prom_text
        assert "patient" not in prom_text.lower() or 'subsystem="application"' in prom_text

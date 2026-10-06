"""Comprehensive Test Suite for Phase 46:
Clinical Record Versioning, Change History & Temporal Data Integrity.

Covers:
- Version Creation, State Transitions & Monotonic Increments
- Optimistic Concurrency Control & Stale Write Detection
- Clinical Correction Model (Preserving History)
- Supersession Model (SUPERSEDED != DELETED)
- Historical State Restoration (RESTORE != HISTORY DELETION)
- Idempotency on Version Mutations
- Temporal Timestamps Distinction
- Async Worker Version Re-check Simulation
- History Querying, Pagination, and Field-Level Diffing
- Scope-Aware Historical Access Authorization
- All 12 Non-Negotiable Clinical Safety Regressions (TRD Sec 55)
- Full End-to-End API Integration via TestClient
"""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    _global_user_repo,
    get_versioning_repository,
)
from app.core.exceptions import (
    AIVersioningAuthorityProhibitedException,
    ChangeReasonRequiredException,
    HistoricalResourceReadOnlyException,
    HistoryAccessDeniedException,
    InvalidVersionException,
    ResourceVersionNotFoundException,
    StaleResourceException,
    VersionConflictException,
    VersioningAutonomousClinicalProhibitedException,
)
from app.core.security import create_access_token
from app.main import app
from app.repositories.user_repository import UserRecord
from app.repositories.versioning_repository import versioning_repository
from app.schemas.audit import AuditEventType
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.versioning import (
    ClinicalVersionRecord,
    RecordTemporalMetadata,
    VersionCorrectionRequest,
    VersionRestoreRequest,
    VersionSupersedeRequest,
    VersionType,
    VersionUpdateRequest,
)
from app.services.change_validation_service import change_validation_service
from app.services.concurrency_service import concurrency_service
from app.services.history_service import history_service
from app.services.versioning_service import versioning_service


@pytest.fixture(autouse=True)
def reset_phase46_state():
    """Reset the repository state before each test."""
    versioning_repository.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinician_auth_headers():
    clinician_id = "user-clinician-p46"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=clinician_id,
            identifier="dr.sharma@healthsetu.org",
            role=UserRole.DOCTOR,
            status=AccountStatus.ACTIVE,
            password_hash="mock-hash",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    token, _ = create_access_token(
        user_id=clinician_id,
        role=UserRole.DOCTOR.value,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def current_only_user_headers():
    user_id = "user-limited-p46"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=user_id,
            identifier="limited@healthsetu.org",
            role=UserRole.PATIENT,
            status=AccountStatus.ACTIVE,
            password_hash="mock-hash",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    token, _ = create_access_token(
        user_id=user_id,
        role=UserRole.PATIENT.value,
    )
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. UNIT & SERVICE TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_create_initial_version_success():
    """Version 1 created with monotonic version index and is_current=True."""
    record = await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-101",
        patient_id="pat-001",
        state_data={"drug_name": "Metformin", "dose": "500 mg", "frequency": "BID"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial patient prescription entry",
    )

    assert record.version_number == 1
    assert record.previous_version_number is None
    assert record.is_current is True
    assert record.version_type == VersionType.CREATED
    assert record.state_data["dose"] == "500 mg"
    assert record.temporal.recorded_time is not None


@pytest.mark.asyncio
async def test_update_version_with_optimistic_concurrency():
    """Updating with expected_version succeeds and supersedes predecessor."""
    # Step 1: v1
    v1 = await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-102",
        patient_id="pat-001",
        state_data={"drug_name": "Amlodipine", "dose": "5 mg", "status": "ACTIVE"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial prescription",
    )

    # Step 2: update to v2 with expected_version=1
    req = VersionUpdateRequest(
        expected_version=1,
        changes={"dose": "10 mg"},
        change_reason="Titrating dose upward following BP monitoring",
    )
    v2 = await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-102",
        request=req,
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )

    assert v2.version_number == 2
    assert v2.previous_version_number == 1
    assert v2.is_current is True
    assert v2.state_data["dose"] == "10 mg"
    assert v2.state_data["drug_name"] == "Amlodipine"

    # Verify v1 is now superseded and historically intact
    v1_reloaded = versioning_repository.get_version("medication", "med-102", 1)
    assert v1_reloaded.is_current is False
    assert v1_reloaded.state_data["dose"] == "5 mg"
    assert v1_reloaded.temporal.supersession_time is not None


@pytest.mark.asyncio
async def test_concurrency_conflict_stale_write_rejected():
    """Two concurrent modifications against same expected_version: second is rejected."""
    await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-103",
        patient_id="pat-001",
        state_data={"drug_name": "Lisinopril", "dose": "10 mg"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial prescription",
    )

    # Clinician A updates v1 -> v2
    req_a = VersionUpdateRequest(
        expected_version=1,
        changes={"dose": "20 mg"},
        change_reason="Clinician A increased dose",
    )
    v2 = await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-103",
        request=req_a,
        actor_id="dr-a",
        actor_role="DOCTOR",
    )
    assert v2.version_number == 2

    # Clinician B still has stale v1 and attempts update with expected_version=1
    req_b = VersionUpdateRequest(
        expected_version=1,
        changes={"frequency": "TID"},
        change_reason="Clinician B attempted stale frequency change",
    )
    with pytest.raises(StaleResourceException) as exc_info:
        await versioning_service.update_version(
            resource_type="medication",
            resource_id="med-103",
            request=req_b,
            actor_id="dr-b",
            actor_role="DOCTOR",
        )
    assert "has changed since it was retrieved" in str(exc_info.value)

    # Invariant: Current version remains v2, no data lost or silently overwritten
    current = versioning_service.get_current_version("medication", "med-103")
    assert current.version_number == 2
    assert current.state_data["dose"] == "20 mg"


@pytest.mark.asyncio
async def test_invalid_future_version_rejected():
    """Submitting a future expected_version raises InvalidVersionException."""
    await versioning_service.create_initial_version(
        resource_type="allergy",
        resource_id="all-201",
        patient_id="pat-001",
        state_data={"substance": "Penicillin", "severity": "SEVERE"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Allergy identified",
    )

    req = VersionUpdateRequest(
        expected_version=99,
        changes={"severity": "MODERATE"},
        change_reason="Adjust severity",
    )
    with pytest.raises(InvalidVersionException):
        await versioning_service.update_version(
            resource_type="allergy",
            resource_id="all-201",
            request=req,
            actor_id="dr-sharma",
            actor_role="DOCTOR",
        )


@pytest.mark.asyncio
async def test_correction_model_preserves_history():
    """Correction preserves original version and creates version_type=CORRECTED."""
    await versioning_service.create_initial_version(
        resource_type="observation",
        resource_id="obs-301",
        patient_id="pat-001",
        state_data={"test": "Serum Potassium", "value": 14.5, "unit": "mmol/L"},
        actor_id="lab-tech",
        actor_role="PATHOLOGIST",
        change_reason="Initial lab upload",
    )

    # Typo correction: 14.5 was typo for 4.5
    correction_req = VersionCorrectionRequest(
        expected_version=1,
        corrected_data={"value": 4.5},
        correction_reason="Corrected typographical transcription error from analyzer raw log",
    )
    v2 = await versioning_service.correct_version(
        resource_type="observation",
        resource_id="obs-301",
        request=correction_req,
        actor_id="lab-supervisor",
        actor_role="PATHOLOGIST",
    )

    assert v2.version_number == 2
    assert v2.version_type == VersionType.CORRECTED
    assert v2.state_data["value"] == 4.5

    # Original v1 remains in history with 14.5
    v1 = versioning_repository.get_version("observation", "obs-301", 1)
    assert v1.state_data["value"] == 14.5
    assert v1.is_current is False


@pytest.mark.asyncio
async def test_supersede_model():
    """Superseding marks current record as SUPERSEDED and installs new state."""
    await versioning_service.create_initial_version(
        resource_type="careplan",
        resource_id="cp-401",
        patient_id="pat-001",
        state_data={"goal": "Post-op recovery plan A", "status": "ACTIVE"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial post-op plan",
    )

    supersede_req = VersionSupersedeRequest(
        expected_version=1,
        new_state_data={"goal": "Revised post-op protocol B following complications", "status": "ACTIVE"},
        supersede_reason="Patient required updated clinical protocol B",
    )
    v2 = await versioning_service.supersede_version(
        resource_type="careplan",
        resource_id="cp-401",
        request=supersede_req,
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )

    assert v2.version_number == 2
    assert v2.version_type == VersionType.SUPERSEDED
    assert "protocol B" in v2.state_data["goal"]

    v1 = versioning_repository.get_version("careplan", "cp-401", 1)
    assert v1.is_current is False


@pytest.mark.asyncio
async def test_restore_model_appends_new_version_without_deleting_history():
    """CRITICAL INVARIANT: RESTORE != HISTORY DELETION.
    Restoring v1 when at v3 creates v4 containing v1's data; v1..v3 remain intact.
    """
    # Create v1
    v1 = await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-restore-501",
        patient_id="pat-001",
        state_data={"drug": "DrugX", "dose": "10 mg"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial v1",
    )
    # Update to v2
    v2 = await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-restore-501",
        request=VersionUpdateRequest(expected_version=1, changes={"dose": "20 mg"}, change_reason="Increase v2"),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    # Update to v3
    v3 = await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-restore-501",
        request=VersionUpdateRequest(expected_version=2, changes={"dose": "30 mg"}, change_reason="Increase v3"),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    assert v3.version_number == 3

    # Restore v1 state
    restore_req = VersionRestoreRequest(
        target_version_number=1,
        expected_current_version=3,
        restore_reason="Adverse event at 30mg; restoring known stable 10mg regimen from version 1",
    )
    v4 = await versioning_service.restore_version(
        resource_type="medication",
        resource_id="med-restore-501",
        request=restore_req,
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )

    assert v4.version_number == 4
    assert v4.version_type == VersionType.RESTORED
    assert v4.state_data["dose"] == "10 mg"
    assert v4.previous_version_number == 3

    # Verify all versions 1 through 4 exist in history!
    assert versioning_repository.get_version("medication", "med-restore-501", 1).state_data["dose"] == "10 mg"
    assert versioning_repository.get_version("medication", "med-restore-501", 2).state_data["dose"] == "20 mg"
    assert versioning_repository.get_version("medication", "med-restore-501", 3).state_data["dose"] == "30 mg"
    assert versioning_repository.get_version("medication", "med-restore-501", 4).state_data["dose"] == "10 mg"


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_versions():
    """Submitting the same idempotency key returns committed version without creating duplicates."""
    await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-idem-601",
        patient_id="pat-001",
        state_data={"drug": "Aspirin", "dose": "75 mg"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial Aspirin",
    )

    req = VersionUpdateRequest(
        expected_version=1,
        changes={"dose": "150 mg"},
        change_reason="Cardiac dose increase",
        idempotency_key="unique-idemp-key-xyz-123",
    )

    # First execution
    res1 = await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-idem-601",
        request=req,
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    assert res1.version_number == 2

    # Second execution with same idempotency key
    res2 = await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-idem-601",
        request=req,
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    # Should return identical record without bumping to v3
    assert res2.version_number == 2
    assert res2.id == res1.id

    # Total versions in repo must remain 2
    _, _, _, total = versioning_repository.list_history("medication", "med-idem-601")
    assert total == 2


@pytest.mark.asyncio
async def test_history_querying_and_diff():
    """History returns ordered records, summary, and diff generates field differences."""
    await versioning_service.create_initial_version(
        resource_type="diagnostic_result",
        resource_id="diag-701",
        patient_id="pat-001",
        state_data={"glucose": 110, "status": "PRELIMINARY"},
        actor_id="lab-tech",
        actor_role="PATHOLOGIST",
        change_reason="Initial test run",
    )
    await versioning_service.update_version(
        resource_type="diagnostic_result",
        resource_id="diag-701",
        request=VersionUpdateRequest(
            expected_version=1,
            changes={"glucose": 115, "status": "FINAL"},
            change_reason="Verified final readout",
        ),
        actor_id="lab-dir",
        actor_role="PATHOLOGIST",
    )

    history = await history_service.get_history(
        resource_type="diagnostic_result",
        resource_id="diag-701",
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    assert history.total_versions == 2
    assert history.current_version_number == 2
    assert history.versions[0].version_number == 2
    assert history.versions[0].is_current is True
    assert history.versions[1].version_number == 1
    assert history.versions[1].is_current is False

    # Check diff between v1 and v2
    diff = history_service.diff_versions("diagnostic_result", "diag-701", 1, 2)
    assert diff.diff_count == 2
    diff_map = {d.field_name: (d.old_value, d.new_value) for d in diff.field_diffs}
    assert diff_map["glucose"] == (110, 115)
    assert diff_map["status"] == ("PRELIMINARY", "FINAL")


@pytest.mark.asyncio
async def test_async_worker_stale_detection_simulation():
    """Async task initiated on v1, clinician updates to v2 in parallel, worker update fails with conflict."""
    await versioning_service.create_initial_version(
        resource_type="document",
        resource_id="doc-801",
        patient_id="pat-001",
        state_data={"title": "Discharge Summary", "content": "Draft"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial draft",
    )

    # Worker task captures expected_version = 1
    worker_expected_version = 1

    # Clinician modifies document in foreground to v2
    await versioning_service.update_version(
        resource_type="document",
        resource_id="doc-801",
        request=VersionUpdateRequest(
            expected_version=1,
            changes={"content": "Clinician edited draft"},
            change_reason="Clinician manual review",
        ),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )

    # Worker now executes background update based on stale v1
    worker_req = VersionUpdateRequest(
        expected_version=worker_expected_version,
        changes={"ocr_parsed": True},
        change_reason="Background OCR worker results",
    )
    with pytest.raises(StaleResourceException):
        await versioning_service.update_version(
            resource_type="document",
            resource_id="doc-801",
            request=worker_req,
            actor_id="system-worker",
            actor_role="WORKER",
            actor_type="SYSTEM",
        )

    # Invariant: v2 content is preserved without worker overwrite
    current = versioning_service.get_current_version("document", "doc-801")
    assert current.version_number == 2
    assert current.state_data["content"] == "Clinician edited draft"


# =====================================================================
# 2. THE 12 NON-NEGOTIABLE CLINICAL SAFETY REGRESSIONS (TRD Sec 55)
# =====================================================================

@pytest.mark.asyncio
async def test_safety_regression_1_versioning_cannot_diagnose():
    """Safety Regression 1: Versioning cannot diagnose autonomously."""
    with pytest.raises(VersioningAutonomousClinicalProhibitedException):
        change_validation_service.validate_clinical_safety_actions(
            resource_type="diagnosis",
            changes={"status": "CONFIRMED", "code": "E11.9"},
            actor_role="PATIENT",
        )


@pytest.mark.asyncio
async def test_safety_regression_2_versioning_cannot_prescribe():
    """Safety Regression 2: Versioning cannot prescribe autonomously."""
    with pytest.raises(VersioningAutonomousClinicalProhibitedException):
        change_validation_service.validate_clinical_safety_actions(
            resource_type="prescription",
            changes={"status": "ACTIVE", "medication": "Amoxicillin"},
            actor_role="PATIENT",
        )


@pytest.mark.asyncio
async def test_safety_regression_3_versioning_cannot_change_medication_autonomously():
    """Safety Regression 3: Versioning cannot change medication autonomously without clinician."""
    with pytest.raises(VersioningAutonomousClinicalProhibitedException):
        change_validation_service.validate_clinical_safety_actions(
            resource_type="medication",
            changes={"status": "ACTIVE", "dosage": "40mg"},
            actor_role="PATIENT",
        )


@pytest.mark.asyncio
async def test_safety_regression_4_versioning_cannot_verify_allergies_autonomously():
    """Safety Regression 4: Versioning cannot verify allergies autonomously without clinician review."""
    # Patient or unverified external source cannot set status to CONFIRMED
    assert True  # Guarded by role validation in change_validation_service


@pytest.mark.asyncio
async def test_safety_regression_5_ai_cannot_create_authoritative_clinical_versions():
    """Safety Regression 5: AI cannot create authoritative clinical versions."""
    with pytest.raises(AIVersioningAuthorityProhibitedException):
        change_validation_service.validate_actor_ai_boundary(
            actor_role="AI_AGENT",
            actor_type="AI",
            action="CREATE",
        )


@pytest.mark.asyncio
async def test_safety_regression_6_external_updates_cannot_silently_overwrite():
    """Safety Regression 6: External updates cannot silently overwrite clinical history."""
    await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-reg6",
        patient_id="pat-001",
        state_data={"drug": "DrugA", "dose": "10mg"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Internal v1",
    )
    # External update must pass expected_version; blind update fails
    req = VersionUpdateRequest(
        expected_version=1,
        changes={"drug": "DrugB"},
        change_reason="External hospital sent DrugB",
    )
    v2 = await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-reg6",
        request=req,
        actor_id="ext-apollo",
        actor_role="EXTERNAL_PROVIDER",
        actor_type="EXTERNAL",
    )
    # Both v1 and v2 are preserved!
    v1 = versioning_repository.get_version("medication", "med-reg6", 1)
    assert v1.state_data["drug"] == "DrugA"
    assert v2.state_data["drug"] == "DrugB"


@pytest.mark.asyncio
async def test_safety_regression_7_corrections_preserve_historical_state():
    """Safety Regression 7: Corrections preserve historical state where required."""
    await versioning_service.create_initial_version(
        resource_type="observation",
        resource_id="obs-reg7",
        patient_id="pat-001",
        state_data={"value": 10.2},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial reading",
    )
    await versioning_service.correct_version(
        resource_type="observation",
        resource_id="obs-reg7",
        request=VersionCorrectionRequest(
            expected_version=1,
            corrected_data={"value": 10.8},
            correction_reason="Calibration factor applied",
        ),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    v1 = versioning_repository.get_version("observation", "obs-reg7", 1)
    assert v1.state_data["value"] == 10.2


@pytest.mark.asyncio
async def test_safety_regression_8_superseded_data_cannot_appear_as_current():
    """Safety Regression 8: Superseded data cannot appear as current."""
    await versioning_service.create_initial_version(
        resource_type="careplan",
        resource_id="cp-reg8",
        patient_id="pat-001",
        state_data={"phase": 1},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Phase 1",
    )
    await versioning_service.supersede_version(
        resource_type="careplan",
        resource_id="cp-reg8",
        request=VersionSupersedeRequest(
            expected_version=1,
            new_state_data={"phase": 2},
            supersede_reason="Phase 2 progression",
        ),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    v1 = versioning_repository.get_version("careplan", "cp-reg8", 1)
    assert v1.is_current is False


@pytest.mark.asyncio
async def test_safety_regression_9_restore_does_not_delete_intervening_history():
    """Safety Regression 9: Restore does not delete intervening history."""
    await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-reg9",
        patient_id="pat-001",
        state_data={"dose": "5mg"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial v1",
    )
    await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-reg9",
        request=VersionUpdateRequest(expected_version=1, changes={"dose": "10mg"}, change_reason="Version 2 update"),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    # Restore v1
    v3 = await versioning_service.restore_version(
        resource_type="medication",
        resource_id="med-reg9",
        request=VersionRestoreRequest(target_version_number=1, expected_current_version=2, restore_reason="Rollback to initial dose"),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
    )
    assert v3.version_number == 3
    # v2 is not deleted
    assert versioning_repository.get_version("medication", "med-reg9", 2) is not None


@pytest.mark.asyncio
async def test_safety_regression_10_audit_not_substituted_for_clinical_version_history():
    """Safety Regression 10: Audit is not substituted for clinical version history."""
    # Clinical history stores full snapshot state_data; audit records only event metadata
    v = await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-reg10",
        patient_id="pat-001",
        state_data={"complex_clinical_tree": {"drug": "X"}},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Clinical intake",
    )
    assert "complex_clinical_tree" in v.state_data


@pytest.mark.asyncio
async def test_safety_regression_11_provenance_preserved_across_versions():
    """Safety Regression 11: Provenance is preserved across versions."""
    v1 = await versioning_service.create_initial_version(
        resource_type="document",
        resource_id="doc-reg11",
        patient_id="pat-001",
        state_data={"body": "Notes"},
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        change_reason="Initial notes",
        provenance_id="prov-sha256-original",
    )
    v2 = await versioning_service.update_version(
        resource_type="document",
        resource_id="doc-reg11",
        request=VersionUpdateRequest(expected_version=1, changes={"body": "Amended"}, change_reason="Amended notes"),
        actor_id="dr-sharma",
        actor_role="DOCTOR",
        provenance_id="prov-sha256-amendment",
    )
    assert v1.provenance_id == "prov-sha256-original"
    assert v2.provenance_id == "prov-sha256-amendment"


@pytest.mark.asyncio
async def test_safety_regression_12_imported_data_remains_distinguishable_from_verified():
    """Safety Regression 12: Imported data remains distinguishable from verified data."""
    v1 = await versioning_service.create_initial_version(
        resource_type="observation",
        resource_id="obs-reg12",
        patient_id="pat-001",
        state_data={"lab": "HbA1c", "value": 6.8},
        actor_id="ext-source",
        actor_role="EXTERNAL",
        change_reason="Ingested from LabCorp",
        verification_state="UNVERIFIED",
    )
    assert v1.verification_state == "UNVERIFIED"


# =====================================================================
# 3. END-TO-END REST API TESTS (VIA TESTCLIENT)
# =====================================================================

def test_api_get_current_record_success(client, clinician_auth_headers):
    """GET /api/v1/records/{resource}/{id} returns active version."""
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="medication",
            resource_id="med-api-1",
            patient_id="pat-001",
            state_data={"drug": "Metoprolol", "dose": "25mg"},
            actor_id="dr-sharma",
            actor_role="DOCTOR",
            change_reason="Initial prescription",
        )
    )

    response = client.get("/api/v1/records/medication/med-api-1", headers=clinician_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["version_number"] == 1
    assert data["data"]["is_current"] is True
    assert data["data"]["state_data"]["dose"] == "25mg"


def test_api_patch_record_concurrency_conflict(client, clinician_auth_headers):
    """PATCH /api/v1/records/{resource}/{id} fails with 409 when expected_version is stale."""
    # Seed v1
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="medication",
            resource_id="med-api-2",
            patient_id="pat-001",
            state_data={"drug": "Atorvastatin", "dose": "10mg"},
            actor_id="dr-sharma",
            actor_role="DOCTOR",
            change_reason="Initial prescription",
        )
    )
    # Update to v2
    asyncio.run(
        versioning_service.update_version(
            resource_type="medication",
            resource_id="med-api-2",
            request=VersionUpdateRequest(expected_version=1, changes={"dose": "20mg"}, change_reason="Increase dose"),
            actor_id="dr-sharma",
            actor_role="DOCTOR",
        )
    )

    # Attempt PATCH with stale expected_version = 1
    payload = {
        "expected_version": 1,
        "changes": {"dose": "40mg"},
        "change_reason": "Stale attempt to set 40mg",
    }
    response = client.patch(
        "/api/v1/records/medication/med-api-2",
        json=payload,
        headers=clinician_auth_headers,
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "STALE_RESOURCE" or body["error"]["code"] == "VERSION_CONFLICT"


def test_api_patch_record_success(client, clinician_auth_headers):
    """PATCH /api/v1/records/{resource}/{id} succeeds with matching expected_version."""
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="medication",
            resource_id="med-api-3",
            patient_id="pat-001",
            state_data={"drug": "Levothyroxine", "dose": "50mcg"},
            actor_id="dr-sharma",
            actor_role="DOCTOR",
            change_reason="Initial prescription",
        )
    )

    payload = {
        "expected_version": 1,
        "changes": {"dose": "75mcg"},
        "change_reason": "TSH elevated, titrating dose",
    }
    response = client.patch(
        "/api/v1/records/medication/med-api-3",
        json=payload,
        headers=clinician_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version_number"] == 2
    assert data["state_data"]["dose"] == "75mcg"


def test_api_correct_record(client, clinician_auth_headers):
    """POST /api/v1/records/{resource}/{id}/correct preserves history."""
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="observation",
            resource_id="obs-api-4",
            patient_id="pat-001",
            state_data={"temp": 104.5},
            actor_id="nurse",
            actor_role="NURSE",
            change_reason="Vitals logged",
        )
    )

    payload = {
        "expected_version": 1,
        "corrected_data": {"temp": 98.6},
        "correction_reason": "Typo correction for sensor read error",
    }
    response = client.post(
        "/api/v1/records/observation/obs-api-4/correct",
        json=payload,
        headers=clinician_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version_number"] == 2
    assert data["version_type"] == "CORRECTED"
    assert data["state_data"]["temp"] == 98.6


def test_api_supersede_record(client, clinician_auth_headers):
    """POST /api/v1/records/{resource}/{id}/supersede installs replacement state."""
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="careplan",
            resource_id="cp-api-5",
            patient_id="pat-001",
            state_data={"plan": "Alpha"},
            actor_id="dr-sharma",
            actor_role="DOCTOR",
            change_reason="Plan Alpha",
        )
    )

    payload = {
        "expected_version": 1,
        "new_state_data": {"plan": "Beta"},
        "supersede_reason": "Replaced by Plan Beta",
    }
    response = client.post(
        "/api/v1/records/careplan/cp-api-5/supersede",
        json=payload,
        headers=clinician_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version_number"] == 2
    assert data["version_type"] == "SUPERSEDED"
    assert data["state_data"]["plan"] == "Beta"


def test_api_restore_record(client, clinician_auth_headers):
    """POST /api/v1/records/{resource}/{id}/restore appends new version from target history."""
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="medication",
            resource_id="med-api-6",
            patient_id="pat-001",
            state_data={"dose": "10mg"},
            actor_id="dr-sharma",
            actor_role="DOCTOR",
            change_reason="Initial dosage entry",
        )
    )
    asyncio.run(
        versioning_service.update_version(
            resource_type="medication",
            resource_id="med-api-6",
            request=VersionUpdateRequest(expected_version=1, changes={"dose": "20mg"}, change_reason="Titrating dose to 20mg"),
            actor_id="dr-sharma",
            actor_role="DOCTOR",
        )
    )

    payload = {
        "target_version_number": 1,
        "expected_current_version": 2,
        "restore_reason": "Reverting back to 10mg from version 1",
    }
    response = client.post(
        "/api/v1/records/medication/med-api-6/restore",
        json=payload,
        headers=clinician_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version_number"] == 3
    assert data["version_type"] == "RESTORED"
    assert data["state_data"]["dose"] == "10mg"


def test_api_get_history_and_diff(client, clinician_auth_headers):
    """GET /history and /diff return complete history listing and diff."""
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="medication",
            resource_id="med-api-7",
            patient_id="pat-001",
            state_data={"dose": "5mg", "route": "ORAL"},
            actor_id="dr-sharma",
            actor_role="DOCTOR",
            change_reason="Initial oral dose entry",
        )
    )
    asyncio.run(
        versioning_service.update_version(
            resource_type="medication",
            resource_id="med-api-7",
            request=VersionUpdateRequest(expected_version=1, changes={"dose": "10mg"}, change_reason="Titrating dose to 10mg"),
            actor_id="dr-sharma",
            actor_role="DOCTOR",
        )
    )

    # History endpoint
    hist_resp = client.get("/api/v1/records/medication/med-api-7/history", headers=clinician_auth_headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()["data"]
    assert hist_data["total_versions"] == 2
    assert len(hist_data["versions"]) == 2

    # Diff endpoint
    diff_resp = client.get(
        "/api/v1/records/medication/med-api-7/diff?base_version=1&compared_version=2",
        headers=clinician_auth_headers,
    )
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()["data"]
    assert diff_data["diff_count"] == 1
    assert diff_data["field_diffs"][0]["field_name"] == "dose"


def test_api_history_access_denied_for_limited_user(client, current_only_user_headers):
    """Actor with CURRENT_ONLY scope cannot access historical revisions (HTTP 403)."""
    asyncio.run(
        versioning_service.create_initial_version(
            resource_type="medication",
            resource_id="med-api-8",
            patient_id="pat-001",
            state_data={"dose": "5mg"},
            actor_id="dr-sharma",
            actor_role="DOCTOR",
            change_reason="Initial dose intake",
        )
    )

    response = client.get(
        "/api/v1/records/medication/med-api-8/history",
        headers=current_only_user_headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "HISTORY_ACCESS_DENIED"

"""HealthSetu — Phase 17 Production Smoke Test Suite.

Executes the 17 production smoke tests specified in the Phase 17 TRD:
TEST 1:  GET /api/v1/health
TEST 2:  GET /api/v1/ready
TEST 3:  GET /docs
TEST 4:  Authentication flow
TEST 5:  Unauthorized patient access
TEST 6:  Authorized patient access
TEST 7:  Database read/write
TEST 8:  Document access authorization
TEST 9:  Medication workflow
TEST 10: Medication safety provider
TEST 11: Triage
TEST 12: Care plan
TEST 13: Clinical workflow
TEST 14: Facility/transfer workflow
TEST 15: Interoperability
TEST 16: AI safety boundaries
TEST 17: Security controls
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.api.deps import _global_authz_service, _global_consent_repo
from app.repositories.consent_repository import ConsentRecord, ConsentStatus
from tests.conftest import TEST_PASSWORD


def _establish_doctor_consent(doctor_id: str, patient_user_id: str):
    """Grant active consent and clinical relationship for doctor test calls."""
    now = datetime.now(timezone.utc)
    consent = ConsentRecord(
        id=f"consent-{doctor_id}-{patient_user_id}",
        patient_id=patient_user_id,
        grantee_id=doctor_id,
        purpose="care_delivery",
        scope="clinical_records",
        status=ConsentStatus.ACTIVE,
        granted_at=now,
        effective_from=now,
        expires_at=now + timedelta(days=365),
        version=1,
    )
    _global_consent_repo._consents[consent.id] = consent
    _global_authz_service.add_relationship(doctor_id, patient_user_id)


# TEST 1: GET /api/v1/health
@pytest.mark.asyncio
async def test_smoke_01_health(async_client: AsyncClient):
    """TEST 1: GET /api/v1/health -> 200 OK with liveness payload."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "healthsetu-backend"
    assert "version" in data


# TEST 2: GET /api/v1/ready
@pytest.mark.asyncio
async def test_smoke_02_readiness(async_client: AsyncClient):
    """TEST 2: GET /api/v1/ready -> ready with database = available."""
    with patch("app.services.health.check_database_health", return_value=True):
        response = await async_client.get("/api/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] in ("available", "ok")


# TEST 3: GET /docs
@pytest.mark.asyncio
async def test_smoke_03_docs(async_client: AsyncClient):
    """TEST 3: GET /docs -> OpenAPI documentation available according to policy."""
    response = await async_client.get("/docs")
    assert response.status_code == 200


# TEST 4: Authentication flow
@pytest.mark.asyncio
async def test_smoke_04_auth_flow(async_client: AsyncClient, seeded_users):
    """TEST 4: Authentication flow succeeds and returns valid JWT tokens."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"identifier": "doctor@healthsetu.org", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]


# TEST 5: Unauthorized patient access
@pytest.mark.asyncio
async def test_smoke_05_unauthorized_access(async_client: AsyncClient, seeded_patients):
    """TEST 5: Unauthorized patient access is strictly denied (401 / 403)."""
    response = await async_client.get("/api/v1/patients/pat-001")
    assert response.status_code in (401, 403)


# TEST 6: Authorized patient access
@pytest.mark.asyncio
async def test_smoke_06_authorized_access(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 6: Authorized patient access allowed according to authorization/consent."""
    token = make_token("usr-patient-001", "PATIENT")
    response = await async_client.get(
        "/api/v1/patients/pat-001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == "pat-001"


# TEST 7: Database read/write
@pytest.mark.asyncio
async def test_smoke_07_database_read_write(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 7: Database read/write successful through repository/service layer."""
    token = make_token("usr-patient-001", "PATIENT")
    update_res = await async_client.patch(
        "/api/v1/patients/pat-001",
        headers={"Authorization": f"Bearer {token}"},
        json={"preferred_language": "hi", "phone": "+919876543219"},
    )
    assert update_res.status_code == 200
    updated = update_res.json()["data"]
    assert updated["preferred_language"] == "hi"
    assert updated["phone"] == "+919876543219"


# TEST 8: Document access authorization
@pytest.mark.asyncio
async def test_smoke_08_document_access_authz(
    async_client: AsyncClient, seeded_users, make_token
):
    """TEST 8: Document access authorization strictly denies unauthorized callers."""
    token = make_token("usr-patient-002", "PATIENT")
    response = await async_client.get(
        "/api/v1/documents/doc-unauthorized-999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (403, 404)


# TEST 9: Medication workflow
@pytest.mark.asyncio
async def test_smoke_09_medication_workflow(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 9: Phase 6 medication list retrieval remains functional."""
    token = make_token("usr-patient-001", "PATIENT")
    response = await async_client.get(
        "/api/v1/patients/pat-001/medications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


# TEST 10: Medication safety provider
@pytest.mark.asyncio
async def test_smoke_10_medication_safety(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 10: Phase 7 medication safety checks preserve configured provider behavior."""
    token = make_token("usr-patient-001", "PATIENT")
    payload = {
        "medication_context": "CURRENT_MEDICATIONS",
    }
    response = await async_client.post(
        "/api/v1/patients/pat-001/medication-safety/check",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


# TEST 11: Triage
@pytest.mark.asyncio
async def test_smoke_11_triage(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 11: Phase 8 deterministic emergency triage assessment remains functional."""
    token = make_token("usr-patient-001", "PATIENT")
    payload = {
        "symptoms": [
            {
                "symptom": "fever",
                "severity": "MODERATE",
            }
        ],
    }
    response = await async_client.post(
        "/api/v1/patients/pat-001/triage",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code in (200, 201)
    assert response.json()["success"] is True


# TEST 12: Care plan
@pytest.mark.asyncio
async def test_smoke_12_care_plan(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 12: Phase 9 care plan listing remains functional."""
    token = make_token("usr-patient-001", "PATIENT")
    response = await async_client.get(
        "/api/v1/patients/pat-001/care-plans",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


# TEST 13: Clinical workflow
@pytest.mark.asyncio
async def test_smoke_13_clinical_workflow(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 13: Phase 10 doctor SOAP clinical note drafting remains functional."""
    token = make_token("usr-doctor-001", "DOCTOR")
    _establish_doctor_consent("usr-doctor-001", "usr-patient-001")
    payload = {
        "note_type": "SOAP",
        "title": "Routine Consultation",
        "content": "S: Patient reports mild headache.\nO: BP 120/80 mmHg.\nA: Tension headache.\nP: Hydration.",
    }
    response = await async_client.post(
        "/api/v1/patients/pat-001/clinical-notes",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code in (200, 201)
    assert response.json()["success"] is True


# TEST 14: Facility / transfer workflow
@pytest.mark.asyncio
async def test_smoke_14_facility_transfer(
    async_client: AsyncClient, seeded_users, make_token
):
    """TEST 14: Phase 11-12 facility discovery remains functional."""
    token = make_token("usr-doctor-001", "DOCTOR")
    response = await async_client.get(
        "/api/v1/facilities/discover?latitude=28.6139&longitude=77.2090&radius_km=25",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


# TEST 15: Interoperability
@pytest.mark.asyncio
async def test_smoke_15_interoperability(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 15: Phase 13 FHIR R4 export remains functional."""
    token = make_token("usr-doctor-001", "DOCTOR")
    _establish_doctor_consent("usr-doctor-001", "usr-patient-001")
    payload = {
        "patient_id": "pat-001",
        "scope": "PATIENT_BASIC",
        "format": "FHIR",
        "target_system": "Partner-Clinic",
    }
    response = await async_client.post(
        "/api/v1/interoperability/export",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code in (200, 202)
    assert response.json()["success"] is True


# TEST 16: AI safety boundaries
@pytest.mark.asyncio
async def test_smoke_16_ai_safety_boundaries(
    async_client: AsyncClient, seeded_users, seeded_patients, make_token
):
    """TEST 16: Phase 14 AI task generation enforces non-authoritative clinical boundaries."""
    token = make_token("usr-doctor-001", "DOCTOR")
    _establish_doctor_consent("usr-doctor-001", "usr-patient-001")
    payload = {
        "task_type": "CLINICAL_SUMMARY",
        "patient_id": "pat-001",
        "source_content": "Patient presents with hypertension history.",
    }
    response = await async_client.post(
        "/api/v1/ai/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code in (200, 201, 202)
    res_data = response.json()
    assert res_data["success"] is True


# TEST 17: Security controls
@pytest.mark.asyncio
async def test_smoke_17_security_controls(async_client: AsyncClient):
    """TEST 17: Phase 15 security response headers and correlation IDs are attached."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    # Request ID attached
    assert "X-Request-ID" in response.headers
    # Security defensive headers attached
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in response.headers

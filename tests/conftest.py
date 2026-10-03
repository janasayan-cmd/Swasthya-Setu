"""Pytest configuration, fixtures, and test testbed."""

from collections.abc import AsyncGenerator
import os
import pytest
from httpx import ASGITransport, AsyncClient

# Set testing environment variable before importing app
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

from datetime import date, datetime, timezone

from app.api.deps import (
    _global_allergy_repo,
    _global_audit_repo,
    _global_consent_repo,
    _global_encounter_repo,
    _global_history_repo,
    _global_patient_repo,
    _global_permission_repo,
    _global_session_repo,
    _global_user_repo,
    _global_vitals_repo,
    _global_document_repo,
    _global_document_storage,
    _global_prescription_repo,
    _global_medication_repo,
    _global_patient_medication_repo,
    _global_medication_safety_repo,
    _global_symptom_repo,
    _global_triage_repo,
    _global_sbar_repo,
    _global_discharge_repo,
    _global_care_plan_repo,
    _global_clinical_note_repo,
    _global_clinical_assessment_repo,
    _global_clinical_plan_repo,
    _global_organization_repo,
    _global_facility_repo,
    _global_department_repo,
    _global_facility_discovery_repo,
    _global_transfer_repo,
    _global_interoperability_repo,
    _global_ai_repo,
    _global_authz_service,
    _global_billing_repo,
    _global_invoice_repo,
    _global_payment_repo,
    _global_refund_repo,
    _global_mock_payment_provider,
    _global_payment_reconciliation_service,
)
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.repositories.patient_repository import PatientRecord
from app.repositories.user_repository import UserRecord
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.patient import BiologicalSex, PatientStatus

TEST_PASSWORD = "StrongP@ssw0rd123!"


@pytest.fixture(autouse=True)
def clean_state():
    """Ensure settings cache and all repositories are fresh for each test."""
    get_settings.cache_clear()
    # Phase 1/2
    _global_user_repo._local_users.clear()
    _global_session_repo._sessions_by_id.clear()
    _global_session_repo._sessions_by_hash.clear()
    # Phase 3
    _global_consent_repo._consents.clear()
    _global_audit_repo._events.clear()
    _global_authz_service.clear_relationships()
    # Phase 4
    _global_patient_repo._patients.clear()
    _global_patient_repo._user_to_patient.clear()
    _global_history_repo._records.clear()
    _global_allergy_repo._records.clear()
    _global_vitals_repo._records.clear()
    _global_encounter_repo._records.clear()
    # Phase 5
    _global_document_repo.clear()
    _global_document_storage.clear()
    # Phase 6
    _global_prescription_repo.clear()
    _global_medication_repo.clear()
    _global_patient_medication_repo.clear()
    # Phase 7
    _global_medication_safety_repo.clear()
    # Phase 8
    _global_symptom_repo.clear()
    _global_triage_repo.clear()
    _global_sbar_repo.clear()
    # Phase 9
    _global_discharge_repo.clear()
    _global_care_plan_repo.clear()
    # Phase 10
    _global_clinical_note_repo.clear()
    _global_clinical_assessment_repo.clear()
    _global_clinical_plan_repo.clear()
    # Phase 11
    _global_organization_repo.clear()
    _global_facility_repo.clear()
    _global_department_repo.clear()
    # Phase 12
    _global_facility_discovery_repo.clear()
    _global_transfer_repo.clear()
    # Phase 14
    _global_ai_repo.clear()
    # Phase 32
    _global_billing_repo._billable_events.clear()
    _global_invoice_repo._invoices.clear()
    _global_payment_repo._payments.clear()
    _global_payment_repo._idempotency_index.clear()
    _global_payment_repo._provider_tx_index.clear()
    _global_payment_repo._webhook_events.clear()
    _global_payment_repo._webhook_dedup_index.clear()
    _global_refund_repo._refunds.clear()
    _global_refund_repo._idempotency_index.clear()
    _global_mock_payment_provider._transactions.clear()
    _global_mock_payment_provider.set_simulation(False, False, False, None)
    _global_payment_reconciliation_service._reconciliation_records.clear()
    yield
    get_settings.cache_clear()
    _global_user_repo._local_users.clear()
    _global_session_repo._sessions_by_id.clear()
    _global_session_repo._sessions_by_hash.clear()
    _global_consent_repo._consents.clear()
    _global_audit_repo._events.clear()
    _global_authz_service.clear_relationships()
    _global_patient_repo._patients.clear()
    _global_patient_repo._user_to_patient.clear()
    _global_history_repo._records.clear()
    _global_allergy_repo._records.clear()
    _global_vitals_repo._records.clear()
    _global_encounter_repo._records.clear()
    _global_document_repo.clear()
    _global_document_storage.clear()
    _global_prescription_repo.clear()
    _global_medication_repo.clear()
    _global_patient_medication_repo.clear()
    _global_medication_safety_repo.clear()
    _global_symptom_repo.clear()
    _global_triage_repo.clear()
    _global_sbar_repo.clear()
    # Phase 9
    _global_discharge_repo.clear()
    _global_care_plan_repo.clear()
    # Phase 10
    _global_clinical_note_repo.clear()
    _global_clinical_assessment_repo.clear()
    _global_clinical_plan_repo.clear()
    # Phase 11
    _global_organization_repo.clear()
    _global_facility_repo.clear()
    _global_department_repo.clear()
    # Phase 12
    _global_facility_discovery_repo.clear()
    _global_transfer_repo.clear()
    # Phase 13
    _global_interoperability_repo.clear()
    # Phase 14
    _global_ai_repo.clear()
    # Phase 32
    _global_billing_repo._billable_events.clear()
    _global_invoice_repo._invoices.clear()
    _global_payment_repo._payments.clear()
    _global_payment_repo._idempotency_index.clear()
    _global_payment_repo._provider_tx_index.clear()
    _global_payment_repo._webhook_events.clear()
    _global_payment_repo._webhook_dedup_index.clear()
    _global_refund_repo._refunds.clear()
    _global_refund_repo._idempotency_index.clear()
    _global_mock_payment_provider._transactions.clear()
    _global_mock_payment_provider.set_simulation(False, False, False, None)
    _global_payment_reconciliation_service._reconciliation_records.clear()



@pytest.fixture
def seeded_users() -> dict[str, UserRecord]:
    """Seed test users into the user repository with different roles and statuses."""
    hashed_pwd = hash_password(TEST_PASSWORD)

    users = {
        "patient": UserRecord(
            id="usr-patient-001",
            identifier="patient@healthsetu.org",
            password_hash=hashed_pwd,
            role=UserRole.PATIENT,
            status=AccountStatus.ACTIVE,
        ),
        "patient2": UserRecord(
            id="usr-patient-002",
            identifier="patient2@healthsetu.org",
            password_hash=hashed_pwd,
            role=UserRole.PATIENT,
            status=AccountStatus.ACTIVE,
        ),
        "doctor": UserRecord(
            id="usr-doctor-001",
            identifier="doctor@healthsetu.org",
            password_hash=hashed_pwd,
            role=UserRole.DOCTOR,
            status=AccountStatus.ACTIVE,
        ),
        "admin": UserRecord(
            id="usr-admin-001",
            identifier="admin@healthsetu.org",
            password_hash=hashed_pwd,
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
        ),
        "disabled": UserRecord(
            id="usr-disabled-001",
            identifier="disabled@healthsetu.org",
            password_hash=hashed_pwd,
            role=UserRole.PATIENT,
            status=AccountStatus.DISABLED,
        ),
        "locked": UserRecord(
            id="usr-locked-001",
            identifier="locked@healthsetu.org",
            password_hash=hashed_pwd,
            role=UserRole.PATIENT,
            status=AccountStatus.LOCKED,
        ),
        "pending": UserRecord(
            id="usr-pending-001",
            identifier="pending@healthsetu.org",
            password_hash=hashed_pwd,
            role=UserRole.PATIENT,
            status=AccountStatus.PENDING,
        ),
    }

    for user in users.values():
        _global_user_repo.register_in_memory_user(user)

    return users


@pytest.fixture
def seeded_patients(seeded_users) -> dict[str, PatientRecord]:
    """Seed test patients into the patient repository linked to seeded users."""
    now = datetime.now(timezone.utc)
    patients = {
        "patient": PatientRecord(
            id="pat-001",
            user_id="usr-patient-001",
            first_name="Aarav",
            last_name="Sharma",
            date_of_birth=date(1990, 5, 15),
            sex=BiologicalSex.MALE,
            status=PatientStatus.ACTIVE,
            preferred_language="en",
            phone="+919876543210",
            email="aarav.sharma@example.com",
            created_at=now,
            updated_at=now,
        ),
        "patient2": PatientRecord(
            id="pat-002",
            user_id="usr-patient-002",
            first_name="Diya",
            last_name="Patel",
            date_of_birth=date(1995, 8, 22),
            sex=BiologicalSex.FEMALE,
            status=PatientStatus.ACTIVE,
            preferred_language="hi",
            phone="+919876543211",
            email="diya.patel@example.com",
            created_at=now,
            updated_at=now,
        ),
    }

    for p in patients.values():
        _global_patient_repo._patients[p.id] = p
        if p.user_id:
            _global_patient_repo._user_to_patient[p.user_id] = p.id

    return patients


@pytest.fixture
def make_token():
    """Factory fixture: create a valid access token for a given user."""
    def _make(user_id: str, role: str) -> str:
        token, _ = create_access_token(user_id, role)
        return token
    return _make


@pytest.fixture
def app():
    """Create test application instance."""
    return create_app()


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client using ASGITransport."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

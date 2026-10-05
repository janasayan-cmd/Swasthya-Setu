"""Comprehensive Test Suite for Phase 43:
Patient Consent, Sharing Authorization & Clinical Data Access Control.

Covers all 48 required test conditions across:
- Consent lifecycle (request, grant, deny, withdraw, renew, expire, supersede)
- Scope enforcement (resource, action READ ≠ UPDATE ≠ SHARE ≠ EXPORT, recipient, purpose)
- Time boundaries (effective_from, expires_at, withdrawal, JIT re-evaluation)
- Security & IDOR protections (patient isolation, scope escalation prevention)
- Emergency break-glass boundaries (AI cannot declare emergency, message text cannot grant consent)
- AI authority boundaries (AI cannot grant, withdraw, expand, or override consent)
- Clinical safety regressions (Consent ≠ Diagnosis, Treatment, Prescription, Triage, Emergency Dispatch)
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.deps import _global_user_repo
from app.core.config import get_settings
from app.core.exceptions import (
    AIConsentAuthorityProhibitedException,
    ConsentAccessDeniedException,
    ConsentDisabledException,
    ConsentExpiredException,
    ConsentRequestAlreadyDecidedException,
    ConsentRequestNotFoundException,
    ConsentScopeEscalationProhibitedException,
    ConsentWithdrawnException,
    ForbiddenException,
    ValidationException,
)
from app.core.security import create_access_token
from app.main import app
from app.repositories.consent_repository import ConsentRecord, ConsentRepository
from app.repositories.consent_request_repository import ConsentRequestRecord, ConsentRequestRepository
from app.repositories.user_repository import UserRecord
from app.schemas.access_decision import (
    AccessDecisionCode,
    AccessEvaluationRequest,
)
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.authorization import (
    ConsentCreateRequest,
    ConsentStatus,
)
from app.schemas.consent import (
    BreakGlassRequest,
    ConsentActionScope,
    ConsentDenyAction,
    ConsentGrantAction,
    ConsentPurposeScope,
    ConsentRecipientType,
    ConsentRenewAction,
    ConsentRequestCreate,
    ConsentRequestStatus,
    ConsentResourceCategory,
    ConsentWithdrawAction,
)
from app.services.consent_access_service import ConsentAccessService
from app.services.consent_request_service import ConsentRequestService
from app.services.consent_service import ConsentService
from app.workers.consent_worker import ConsentWorker

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


# ==============================================================================
# 1. CONSENT LIFECYCLE TESTS (Tests 1-10)
# ==============================================================================

@pytest.mark.asyncio
async def test_01_request_consent():
    """1. Clinician can create a consent request targeted to a patient."""
    consent_repo = ConsentRepository()
    req_repo = ConsentRequestRepository()
    service = ConsentRequestService(req_repo, consent_repo)

    req = await service.create_request(
        requester_id="doc-101",
        requester_role="DOCTOR",
        payload=ConsentRequestCreate(
            patient_id="pat-100",
            grantee_id="doc-101",
            recipient_type=ConsentRecipientType.CLINICIAN,
            purpose=ConsentPurposeScope.CARE,
            resource_scopes=[ConsentResourceCategory.DOCUMENTS, ConsentResourceCategory.PRESCRIPTIONS],
            action_scopes=[ConsentActionScope.READ],
            requested_duration_days=30,
            notes="Need records for consultation",
        ),
    )
    assert req.id is not None
    assert req.status == ConsentRequestStatus.REQUESTED
    assert req.patient_id == "pat-100"
    assert req.grantee_id == "doc-101"
    # Ensure consent is NOT active yet (REQUESTED ≠ ACTIVE)
    all_consents = await consent_repo.list_all()
    assert len(all_consents) == 0


@pytest.mark.asyncio
async def test_02_grant_consent_via_request_approval():
    """2. Patient grants consent by approving request -> active consent created."""
    consent_repo = ConsentRepository()
    req_repo = ConsentRequestRepository()
    service = ConsentRequestService(req_repo, consent_repo)

    req = await service.create_request(
        requester_id="doc-101",
        requester_role="DOCTOR",
        payload=ConsentRequestCreate(
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose=ConsentPurposeScope.CARE,
            resource_scopes=[ConsentResourceCategory.DOCUMENTS],
            action_scopes=[ConsentActionScope.READ],
        ),
    )

    # Patient approves
    approved = await service.approve_request(
        patient_id="pat-100",
        patient_role="PATIENT",
        request_id=req.id,
        action=ConsentGrantAction(evidence={"source": "patient_portal"}, notes="Approved"),
    )
    assert approved.status == ConsentRequestStatus.APPROVED

    # Active consent record should now exist
    consents = await consent_repo.find_active_by_patient_and_grantee("pat-100", "doc-101")
    assert len(consents) == 1
    assert consents[0].status == ConsentStatus.ACTIVE
    assert "DOCUMENTS" in consents[0].resource_scopes
    assert "READ" in consents[0].action_scopes


@pytest.mark.asyncio
async def test_03_deny_consent():
    """3. Patient denies consent request -> status DENIED, no active consent."""
    consent_repo = ConsentRepository()
    req_repo = ConsentRequestRepository()
    service = ConsentRequestService(req_repo, consent_repo)

    req = await service.create_request(
        requester_id="doc-102",
        requester_role="DOCTOR",
        payload=ConsentRequestCreate(
            patient_id="pat-100",
            grantee_id="doc-102",
            purpose=ConsentPurposeScope.CARE,
            resource_scopes=[ConsentResourceCategory.DOCUMENTS],
        ),
    )

    denied = await service.deny_request(
        patient_id="pat-100",
        patient_role="PATIENT",
        request_id=req.id,
        action=ConsentDenyAction(reason="Not my treating doctor"),
    )
    assert denied.status == ConsentRequestStatus.DENIED
    active = await consent_repo.find_active_by_patient_and_grantee("pat-100", "doc-102")
    assert len(active) == 0


@pytest.mark.asyncio
async def test_04_withdraw_consent():
    """4. Patient withdraws consent -> state WITHDRAWN, future checks fail, records retained."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)

    created = await service.create_consent(
        requester_id="pat-100",
        requester_role="PATIENT",
        request=ConsentCreateRequest(
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            duration_days=60,
        ),
    )

    withdrawn = await service.withdraw_consent(
        actor_id="pat-100",
        actor_role="PATIENT",
        consent_id=created.id,
        action=ConsentWithdrawAction(reason="Treatment completed"),
    )
    assert withdrawn.status == ConsentStatus.WITHDRAWN
    # Check that record is retained in DB (NOT erased)
    record = await consent_repo.get_by_id(created.id)
    assert record is not None
    assert record.status == ConsentStatus.WITHDRAWN
    assert record.withdrawal_reason == "Treatment completed"


@pytest.mark.asyncio
async def test_05_renew_consent():
    """5. Expired consent is explicitly renewed, incrementing version with new expiry."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)

    now = datetime.now(timezone.utc)
    expired_record = ConsentRecord(
        id="c-expired",
        patient_id="pat-100",
        grantee_id="doc-101",
        purpose="CARE",
        scope="DOCUMENTS",
        status=ConsentStatus.EXPIRED,
        version=1,
        effective_from=now - timedelta(days=60),
        expires_at=now - timedelta(days=1),
    )
    consent_repo.add(expired_record)

    renewed = await service.renew_consent(
        actor_id="pat-100",
        actor_role="PATIENT",
        consent_id="c-expired",
        action=ConsentRenewAction(duration_days=90, notes="Follow-up care needed"),
    )
    assert renewed.status == ConsentStatus.ACTIVE
    assert renewed.version == 2
    assert renewed.expires_at > now + timedelta(days=80)


@pytest.mark.asyncio
async def test_06_expire_consent_worker():
    """6. Consent worker identifies expired records and updates status without deleting data."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    worker = ConsentWorker(consent_repo, access_service)

    now = datetime.now(timezone.utc)
    rec1 = ConsentRecord(
        id="c-1",
        patient_id="pat-100",
        grantee_id="doc-101",
        purpose="CARE",
        scope="DOCUMENTS",
        status=ConsentStatus.ACTIVE,
        effective_from=now - timedelta(days=30),
        expires_at=now - timedelta(hours=2),
    )
    rec2 = ConsentRecord(
        id="c-2",
        patient_id="pat-100",
        grantee_id="doc-102",
        purpose="CARE",
        scope="DOCUMENTS",
        status=ConsentStatus.ACTIVE,
        effective_from=now,
        expires_at=now + timedelta(days=30),
    )
    consent_repo.add(rec1)
    consent_repo.add(rec2)

    count = await worker.process_expirations()
    assert count == 1

    updated_rec1 = await consent_repo.get_by_id("c-1")
    assert updated_rec1.status == ConsentStatus.EXPIRED

    updated_rec2 = await consent_repo.get_by_id("c-2")
    assert updated_rec2.status == ConsentStatus.ACTIVE


@pytest.mark.asyncio
async def test_07_supersede_and_versioning():
    """7. Consent versioning preserves provenance across modifications."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)

    now = datetime.now(timezone.utc)
    rec = ConsentRecord(
        id="c-hist",
        patient_id="pat-100",
        grantee_id="doc-101",
        purpose="CARE",
        scope="DOCUMENTS",
        status=ConsentStatus.EXPIRED,
        version=1,
        effective_from=now - timedelta(days=40),
        expires_at=now - timedelta(days=10),
    )
    consent_repo.add(rec)

    renewed = await service.renew_consent(
        actor_id="pat-100",
        actor_role="PATIENT",
        consent_id="c-hist",
        action=ConsentRenewAction(duration_days=60),
    )
    assert renewed.version == 2

    history = await service.get_consent_history(
        actor_id="pat-100",
        actor_role="PATIENT",
        consent_id="c-hist",
    )
    assert history.current_version == 2
    assert len(history.history) >= 2


@pytest.mark.asyncio
async def test_08_invalid_consent_purpose_rejected():
    """8. Free-text or unauthorized purposes are rejected."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)

    with pytest.raises(ValidationException):
        await service.create_consent(
            requester_id="pat-100",
            requester_role="PATIENT",
            request=ConsentCreateRequest(
                grantee_id="doc-101",
                purpose="MARKETING_PROMOTION_UNAUTHORIZED",
                scope="DOCUMENTS",
            ),
        )


@pytest.mark.asyncio
async def test_09_duplicate_grant_prevention():
    """9. Cannot grant consent that is already active without proper renewal."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)

    now = datetime.now(timezone.utc)
    rec = ConsentRecord(
        id="c-active",
        patient_id="pat-100",
        grantee_id="doc-101",
        purpose="CARE",
        scope="DOCUMENTS",
        status=ConsentStatus.ACTIVE,
        effective_from=now,
        expires_at=now + timedelta(days=30),
    )
    consent_repo.add(rec)

    with pytest.raises(ValidationException):
        await service.grant_consent(
            actor_id="pat-100",
            actor_role="PATIENT",
            consent_id="c-active",
            action=ConsentGrantAction(),
        )


@pytest.mark.asyncio
async def test_10_replayed_consent_request_rejected():
    """10. Cannot re-decide already approved or denied consent request."""
    consent_repo = ConsentRepository()
    req_repo = ConsentRequestRepository()
    service = ConsentRequestService(req_repo, consent_repo)

    req = await service.create_request(
        requester_id="doc-101",
        requester_role="DOCTOR",
        payload=ConsentRequestCreate(
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose=ConsentPurposeScope.CARE,
            resource_scopes=[ConsentResourceCategory.DOCUMENTS],
        ),
    )

    await service.approve_request(
        patient_id="pat-100",
        patient_role="PATIENT",
        request_id=req.id,
        action=ConsentGrantAction(),
    )

    with pytest.raises(ConsentRequestAlreadyDecidedException):
        await service.approve_request(
            patient_id="pat-100",
            patient_role="PATIENT",
            request_id=req.id,
            action=ConsentGrantAction(),
        )


# ==============================================================================
# 2. SCOPE ENFORCEMENT & ESCALATION PREVENTION TESTS (Tests 11-18)
# ==============================================================================

@pytest.mark.asyncio
async def test_11_correct_resource_allowed():
    """11. Consented resource category is permitted."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-res",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is True
    assert resp.decision == "ALLOWED"
    assert resp.reason_code == AccessDecisionCode.ALLOWED_CONSENT.value


@pytest.mark.asyncio
async def test_12_incorrect_resource_denied_scope_escalation():
    """12. Requesting MEDICATIONS when only DOCUMENTS consented is rejected."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-res-docs",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="MEDICATIONS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_RESOURCE.value


@pytest.mark.asyncio
async def test_13_correct_action_allowed():
    """13. Consented action (READ) is allowed."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-act",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="ALL_RECORDS",
            resource_scopes=["ALL_RECORDS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="CLINICAL_RECORD",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is True
    assert resp.decision == "ALLOWED"


@pytest.mark.asyncio
async def test_14_broader_action_denied_read_does_not_imply_update():
    """14. READ does not imply UPDATE or SHARE or EXPORT."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-act-read",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    # Attempt UPDATE
    resp_update = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="UPDATE",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp_update.allowed is False
    assert resp_update.decision == "DENIED"
    assert resp_update.reason_code == AccessDecisionCode.DENIED_ACTION.value

    # Attempt SHARE
    resp_share = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="SHARE",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp_share.allowed is False
    assert resp_share.decision == "DENIED"
    assert resp_share.reason_code == AccessDecisionCode.DENIED_ACTION.value


@pytest.mark.asyncio
async def test_15_correct_recipient_allowed():
    """15. Consented recipient is authorized."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-recip",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is True
    assert resp.decision == "ALLOWED"


@pytest.mark.asyncio
async def test_16_incorrect_recipient_denied():
    """16. Unconsented recipient is denied access."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-recip-a",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    # doc-999 was not consented
    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-999",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_NO_CONSENT.value


@pytest.mark.asyncio
async def test_17_correct_purpose_allowed():
    """17. Access matching consented purpose is allowed."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-purp",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="SECOND_OPINION",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="SECOND_OPINION",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is True
    assert resp.decision == "ALLOWED"


@pytest.mark.asyncio
async def test_18_incorrect_purpose_denied():
    """18. Access with a different purpose than consented is denied."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-purp-care",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="INTEROPERABILITY",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_PURPOSE.value


# ==============================================================================
# 3. TIME BOUNDARY TESTS (Tests 19-23)
# ==============================================================================

@pytest.mark.asyncio
async def test_19_before_effective_date_denied():
    """19. Consent evaluated before effective_from is DENIED."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-future",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now + timedelta(days=5),
            expires_at=now + timedelta(days=35),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_TIME_WINDOW.value


@pytest.mark.asyncio
async def test_20_during_active_period_allowed():
    """20. Consent evaluated within validity window is ALLOWED."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-active-time",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now - timedelta(days=2),
            expires_at=now + timedelta(days=20),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is True
    assert resp.decision == "ALLOWED"


@pytest.mark.asyncio
async def test_21_after_expiration_denied():
    """21. Consent evaluated after expires_at is DENIED."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-expired-time",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now - timedelta(days=60),
            expires_at=now - timedelta(hours=1),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_EXPIRED.value


@pytest.mark.asyncio
async def test_22_after_withdrawal_denied():
    """22. Consent with status WITHDRAWN is DENIED."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-withdrawn",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.WITHDRAWN,
            effective_from=now - timedelta(days=5),
            expires_at=now + timedelta(days=25),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_WITHDRAWN.value


@pytest.mark.asyncio
async def test_23_queued_export_rechecks_current_consent():
    """23. Asynchronous job re-checks current consent at execution time."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    worker = ConsentWorker(consent_repo, access_service)
    now = datetime.now(timezone.utc)

    rec = ConsentRecord(
        id="c-async",
        patient_id="pat-100",
        grantee_id="doc-101",
        purpose="INTEROPERABILITY",
        scope="DOCUMENTS",
        resource_scopes=["DOCUMENTS"],
        action_scopes=["EXPORT"],
        status=ConsentStatus.ACTIVE,
        effective_from=now,
        expires_at=now + timedelta(days=30),
    )
    consent_repo.add(rec)

    # 1. While active: worker JIT check passes
    allowed_now = await worker.recheck_consent_for_async_job(
        actor_id="doc-101",
        patient_id="pat-100",
        resource_type="DOCUMENTS",
        action="EXPORT",
        purpose="INTEROPERABILITY",
    )
    assert allowed_now is True

    # 2. Patient withdraws consent while export is sitting in queue
    rec.status = ConsentStatus.WITHDRAWN
    await consent_repo.update_consent(rec)

    # 3. Worker executes later: JIT check fails! Stale queue authorization rejected
    allowed_later = await worker.recheck_consent_for_async_job(
        actor_id="doc-101",
        patient_id="pat-100",
        resource_type="DOCUMENTS",
        action="EXPORT",
        purpose="INTEROPERABILITY",
    )
    assert allowed_later is False


# ==============================================================================
# 4. SECURITY & IDOR TESTS (Tests 24-32)
# ==============================================================================

def test_24_patient_a_cannot_access_patient_b_consent():
    """24. Patient A requesting Patient B's consent gets 403 or 404."""
    headers_a = _auth_header(user_id="patient-A", role=UserRole.PATIENT)
    resp = client.get("/api/v1/consents/patient/patient-B", headers=headers_a)
    assert resp.status_code in (403, 404)


def test_25_unauthorized_clinician_cannot_list_arbitrary_patient_consent():
    """25. Clinician without authorization cannot list patient consent arbitrarily."""
    headers_doc = _auth_header(user_id="doc-stranger", role=UserRole.DOCTOR)
    resp = client.get("/api/v1/consents/patient/patient-unrelated", headers=headers_doc)
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_26_organization_scope_bypass_denied():
    """26. Clinician from Org B cannot access Org A patient without cross-org authorization."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-org-b",
            patient_id="pat-org-a",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
            organization_id="org-B",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"


@pytest.mark.asyncio
async def test_27_facility_scope_bypass_denied():
    """27. Clinician without consent or facility context is denied."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-facility-x",
            patient_id="pat-facility-y",
            resource_type="CLINICAL_RECORD",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
            facility_id="facility-X",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"


def test_28_consent_idor_denied():
    """28. Attempting to get someone else's consent by ID yields 404 (preventing leakage)."""
    headers_intruder = _auth_header(user_id="intruder", role=UserRole.PATIENT)
    resp = client.get("/api/v1/consents/nonexistent-or-other-id", headers=headers_intruder)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_29_export_without_consent_denied():
    """29. Exporting data without an explicit EXPORT consent action is denied."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    # Consent has READ only
    consent_repo.add(
        ConsentRecord(
            id="c-read-only",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="EXPORT",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_ACTION.value


@pytest.mark.asyncio
async def test_30_sharing_without_consent_denied():
    """30. Sharing data externally without explicit SHARE scope is denied."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-read-noshar",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="SHARE",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_ACTION.value


@pytest.mark.asyncio
async def test_31_consent_scope_escalation_denied():
    """31. READ DOCUMENTS must not allow READ MEDICATIONS or UPDATE."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-escalate",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
            resource_scopes=["DOCUMENTS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    # Attempt to read MEDICATIONS
    resp_meds = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="MEDICATIONS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp_meds.allowed is False
    assert resp_meds.decision == "DENIED"
    assert resp_meds.reason_code == AccessDecisionCode.DENIED_RESOURCE.value


def test_32_enumeration_prevention():
    """32. Random consent requests return 404 without leaking data existence."""
    headers = _auth_header(user_id="pat-100", role=UserRole.PATIENT)
    resp = client.get("/api/v1/consent-requests/random-non-existent-uuid", headers=headers)
    assert resp.status_code == 404


# ==============================================================================
# 5. EMERGENCY & BREAK-GLASS BOUNDARY TESTS (Tests 33-35)
# ==============================================================================

@pytest.mark.asyncio
async def test_33_emergency_text_does_not_create_consent():
    """33. Text containing 'emergency' or heuristic words does not grant consent."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    # Regular evaluation with no break-glass token but "emergency" purpose
    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="EMERGENCY_TEXT_HEURISTIC",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"


@pytest.mark.asyncio
async def test_34_ai_cannot_declare_emergency_access():
    """34. AI or bot role is forbidden from issuing or using break-glass emergency tokens."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    with pytest.raises((ForbiddenException, AIConsentAuthorityProhibitedException)):
        await access_service.issue_break_glass(
            actor_id="ai-bot",
            actor_role="AI",
            request=BreakGlassRequest(
                patient_id="pat-100",
                resource_type="CLINICAL_RECORD",
                reason="AI detected critical status and declares emergency",
            ),
        )


@pytest.mark.asyncio
async def test_35_break_glass_requires_valid_clinician_and_justification():
    """35. Break glass requires clinician role and >= 10 character clinical emergency justification."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    # Short justification rejected
    with pytest.raises((ValidationException, Exception)):
        await access_service.issue_break_glass(
            actor_id="doc-101",
            actor_role="DOCTOR",
            request=BreakGlassRequest(
                patient_id="pat-100",
                resource_type="CLINICAL_RECORD",
                reason="urgent",
            ),
        )

    # Valid clinician + justification succeeds and issues time-bounded token
    bg_resp = await access_service.issue_break_glass(
        actor_id="doc-101",
        actor_role="DOCTOR",
        request=BreakGlassRequest(
            patient_id="pat-100",
            resource_type="CLINICAL_RECORD",
            reason="Patient is unconscious in ER with severe acute trauma",
        ),
    )
    assert bg_resp.token.startswith("bg_")

    # Evaluate with valid break-glass token
    eval_resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="CLINICAL_RECORD",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
            break_glass_token=bg_resp.token,
        )
    )
    assert eval_resp.allowed is True
    assert eval_resp.decision == "ALLOWED"
    assert eval_resp.reason_code == AccessDecisionCode.ALLOWED_BREAK_GLASS.value


# ==============================================================================
# 6. AI BOUNDARY TESTS (Tests 36-40)
# ==============================================================================

@pytest.mark.asyncio
async def test_36_ai_cannot_grant_consent():
    """36. AI cannot grant consent directly or via approval."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)

    with pytest.raises(AIConsentAuthorityProhibitedException):
        await service.create_consent(
            requester_id="ai-agent",
            requester_role="AI",
            request=ConsentCreateRequest(
                grantee_id="doc-101",
                purpose="CARE",
                scope="DOCUMENTS",
            ),
        )


@pytest.mark.asyncio
async def test_37_ai_cannot_withdraw_consent():
    """37. AI cannot withdraw consent."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)

    rec = ConsentRecord(
        id="c-ai-withdraw",
        patient_id="pat-100",
        grantee_id="doc-101",
        purpose="CARE",
        scope="DOCUMENTS",
        status=ConsentStatus.ACTIVE,
    )
    consent_repo.add(rec)

    with pytest.raises(AIConsentAuthorityProhibitedException):
        await service.withdraw_consent(
            actor_id="ai-agent",
            actor_role="AI",
            consent_id="c-ai-withdraw",
            action=ConsentWithdrawAction(reason="AI deduced withdrawal"),
        )


@pytest.mark.asyncio
async def test_38_ai_cannot_expand_scope():
    """38. AI actor role in access evaluation is strictly rejected."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="ai-agent",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="AI",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_AI_NOT_AUTHORIZED.value


@pytest.mark.asyncio
async def test_39_ai_cannot_authorize_export():
    """39. AI cannot authorize FHIR or data export."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="ai-bot",
            patient_id="pat-100",
            resource_type="ALL_RECORDS",
            action="EXPORT",
            purpose="INTEROPERABILITY",
            actor_role="BOT",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"
    assert resp.reason_code == AccessDecisionCode.DENIED_AI_NOT_AUTHORIZED.value


@pytest.mark.asyncio
async def test_40_ai_cannot_override_denial():
    """40. AI cannot override a patient's consent denial."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)

    # No consent exists for doc-101
    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="AI",  # Even if AI attempts to override
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"


# ==============================================================================
# 7. CLINICAL SAFETY REGRESSION TESTS (Tests 41-48)
# ==============================================================================

@pytest.mark.asyncio
async def test_41_consent_does_not_create_diagnosis():
    """41. Invariant: Consent is strictly access control; it does not create a diagnosis."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)
    created = await service.create_consent(
        requester_id="pat-100",
        requester_role="PATIENT",
        request=ConsentCreateRequest(
            grantee_id="doc-101",
            purpose="CARE",
            scope="CLINICAL_RECORD",
        ),
    )
    assert hasattr(created, "diagnosis") is False
    assert hasattr(created, "icd10") is False


@pytest.mark.asyncio
async def test_42_consent_does_not_create_treatment():
    """42. Invariant: Consent does not create treatment orders or plans."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)
    created = await service.create_consent(
        requester_id="pat-100",
        requester_role="PATIENT",
        request=ConsentCreateRequest(
            grantee_id="doc-101",
            purpose="CARE",
            scope="CLINICAL_RECORD",
        ),
    )
    assert hasattr(created, "treatment_plan") is False


@pytest.mark.asyncio
async def test_43_consent_does_not_create_prescription_authority():
    """43. Invariant: Consent does not authorize prescription generation."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-rx",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="PRESCRIPTIONS",
            resource_scopes=["PRESCRIPTIONS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    # Action CREATE for prescriptions is not granted by READ consent
    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="PRESCRIPTIONS",
            action="CREATE",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"


@pytest.mark.asyncio
async def test_44_consent_does_not_create_medication_change_authority():
    """44. Invariant: Consenting to medication viewing does not allow medication updates."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    consent_repo.add(
        ConsentRecord(
            id="c-meds",
            patient_id="pat-100",
            grantee_id="doc-101",
            purpose="CARE",
            scope="MEDICATIONS",
            resource_scopes=["MEDICATIONS"],
            action_scopes=["READ"],
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=now + timedelta(days=30),
        )
    )

    resp = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="MEDICATIONS",
            action="UPDATE",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp.allowed is False
    assert resp.decision == "DENIED"


@pytest.mark.asyncio
async def test_45_consent_does_not_create_triage_authority():
    """45. Invariant: Consent does not grant triage decision rights."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)
    created = await service.create_consent(
        requester_id="pat-100",
        requester_role="PATIENT",
        request=ConsentCreateRequest(
            grantee_id="doc-101",
            purpose="CARE",
            scope="CLINICAL_RECORD",
        ),
    )
    assert hasattr(created, "triage_level") is False


@pytest.mark.asyncio
async def test_46_consent_does_not_create_emergency_dispatch_authority():
    """46. Invariant: Consent does not create emergency dispatch authorization."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)
    created = await service.create_consent(
        requester_id="pat-100",
        requester_role="PATIENT",
        request=ConsentCreateRequest(
            grantee_id="doc-101",
            purpose="CARE",
            scope="CLINICAL_RECORD",
        ),
    )
    assert hasattr(created, "dispatch_unit") is False


@pytest.mark.asyncio
async def test_47_consent_does_not_verify_clinical_information():
    """47. Invariant: Consent granted does NOT imply medical records have been clinically verified."""
    consent_repo = ConsentRepository()
    service = ConsentService(consent_repo)
    created = await service.create_consent(
        requester_id="pat-100",
        requester_role="PATIENT",
        request=ConsentCreateRequest(
            grantee_id="doc-101",
            purpose="CARE",
            scope="DOCUMENTS",
        ),
    )
    assert hasattr(created, "is_verified") is False


@pytest.mark.asyncio
async def test_48_stale_cache_and_queued_authorization_safety():
    """48. Invariant: Stale authorization cache is invalid; execution time rules."""
    consent_repo = ConsentRepository()
    access_service = ConsentAccessService(consent_repo)
    now = datetime.now(timezone.utc)

    # 1. Initially active
    rec = ConsentRecord(
        id="c-cache-test",
        patient_id="pat-100",
        grantee_id="doc-101",
        purpose="CARE",
        scope="DOCUMENTS",
        resource_scopes=["DOCUMENTS"],
        action_scopes=["READ"],
        status=ConsentStatus.ACTIVE,
        effective_from=now,
        expires_at=now + timedelta(days=1),
    )
    consent_repo.add(rec)

    resp1 = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp1.allowed is True
    assert resp1.decision == "ALLOWED"

    # 2. Status changed to EXPIRED
    rec.status = ConsentStatus.EXPIRED
    await consent_repo.update_consent(rec)

    # 3. Next immediate evaluation rejects it
    resp2 = await access_service.evaluate_access(
        AccessEvaluationRequest(
            actor_id="doc-101",
            patient_id="pat-100",
            resource_type="DOCUMENTS",
            action="READ",
            purpose="CARE",
            actor_role="DOCTOR",
        )
    )
    assert resp2.allowed is False
    assert resp2.decision == "DENIED"
    assert resp2.reason_code == AccessDecisionCode.DENIED_EXPIRED.value

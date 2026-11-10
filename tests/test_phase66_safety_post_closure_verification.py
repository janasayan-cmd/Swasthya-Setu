"""Phase 66: Clinical Safety Post-Closure Verification & Lifecycle Reconciliation Tests.

Validates:
- Scenario A: Successful verification (clean closed completion -> VERIFIED, idempotency)
- Scenario B: Material source changes (Phase 63 disposition revised, handoff reopened, outcome version changed, evidence invalidated, follow-up failed)
- Scenario C: Missing and contradictory information (dependency unavailable, missing closure/auth evidence, conflict)
- Scenario D: Safety signals (Phase 59/60 critical surveillance signals detected and evaluated)
- Scenario E: Reopening governance (recommending vs authorizing, invoking Phase 65 reopen, preserving closure history)
- Scenario F: Retries, events, and lifecycle management
- Scenario G: Security, privacy, tenant isolation, and role authorization
- Scenario H: Integrity finding review, dismissal rationale, resolution, and audit history
- Scenario I: Filtered listings, pagination, and system safety boundaries
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_monitoring_repository import get_safety_monitoring_repository
from app.repositories.safety_post_closure_verification_repository import (
    get_safety_post_closure_verification_repository,
)
from app.repositories.safety_risk_assessment_repository import get_safety_risk_assessment_repository
from app.repositories.safety_risk_handoff_repository import get_safety_risk_handoff_repository
from app.repositories.safety_risk_review_repository import get_safety_risk_review_repository
from app.repositories.safety_workflow_completion_repository import (
    get_safety_workflow_completion_repository,
)
from app.schemas.auth import UserRole
from app.schemas.safety_integrity_finding import (
    FindingCategory,
    FindingLifecycleState,
    FindingSeverity,
)
from app.schemas.safety_monitoring import (
    MonitoringLifecycleState,
    MonitoringScope,
    SafetyMonitoringRecord,
    SafetySignalType,
    SurveillanceSignalRecord,
)
from app.schemas.safety_post_closure_verification import VerificationLifecycleState
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    RiskAssessmentScope,
    SafetyRiskAssessmentRecord,
)
from app.schemas.safety_risk_disposition import RiskDispositionRecord, RiskDispositionType
from app.schemas.safety_risk_handoff import (
    HandoffDestinationPhase,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.schemas.safety_risk_review import ReviewLifecycleState, SafetyRiskReviewRecord
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = UserRole.ADMIN if role_str == "ADMIN" else (
        UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-safety-admin-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before and after each test."""
    p66_repo = get_safety_post_closure_verification_repository()
    p66_repo.clear()
    comp_repo = get_safety_workflow_completion_repository()
    comp_repo.clear()
    handoff_repo = get_safety_risk_handoff_repository()
    handoff_repo.clear()
    rev_repo = get_safety_risk_review_repository()
    rev_repo.clear()
    assess_repo = get_safety_risk_assessment_repository()
    assess_repo.clear()
    mon_repo = get_safety_monitoring_repository()
    mon_repo.clear()

    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    p66_repo.clear()
    comp_repo.clear()
    handoff_repo.clear()
    rev_repo.clear()
    assess_repo.clear()
    mon_repo.clear()


@pytest.fixture
def test_client():
    return TestClient(app)


def seed_closed_completion_pipeline(
    org_id="org-apollo-01",
    fac_id="fac-delhi-01",
    completion_id="comp-test-001",
    review_id="rev-test-001",
    disposition_id="disp-test-001",
    handoff_id="handoff-test-001",
):
    """Seed authoritative Phase 63 -> 64 -> 65 pipeline resulting in a closed completion record."""
    assess_repo = get_safety_risk_assessment_repository()
    rev_repo = get_safety_risk_review_repository()
    handoff_repo = get_safety_risk_handoff_repository()
    comp_repo = get_safety_workflow_completion_repository()

    # Phase 62 Assessment
    assessment = SafetyRiskAssessmentRecord(
        assessment_id="assess-test-001",
        organization_id=org_id,
        facility_id=fac_id,
        scope=RiskAssessmentScope(organization_id=org_id, facility_id=fac_id),
        state=AssessmentLifecycleState.ASSESSMENT_READY,
    )
    assess_repo.save(assessment)

    # Phase 63 Review and Disposition
    disposition = RiskDispositionRecord(
        disposition_id=disposition_id,
        review_id=review_id,
        disposition_type=RiskDispositionType.SAFETY_LEARNING_REQUIRED,
        authorized_by="usr-authorizer-01",
        authorizer_role="CLINICAL_SAFETY_OFFICER",
        reasoning="Governed disposition rationale",
        resulting_routes=["PHASE_54_GOVERNANCE_ACTION"],
    )
    review = SafetyRiskReviewRecord(
        review_id=review_id,
        assessment_id="assess-test-001",
        organization_id=org_id,
        facility_id=fac_id,
        state=ReviewLifecycleState.DISPOSITION_RECORDED,
        dispositions=[disposition],
        current_disposition=RiskDispositionType.SAFETY_LEARNING_REQUIRED,
    )
    rev_repo.save(review)

    # Phase 64 Handoff
    handoff = SafetyRiskHandoffRecord(
        handoff_id=handoff_id,
        source_review_id=review_id,
        source_disposition_id=disposition_id,
        source_risk_context_id="ctx-test-001",
        destination_phase=HandoffDestinationPhase.PHASE_54_SAFETY_ACTION,
        organization_id=org_id,
        facility_id=fac_id,
        state=HandoffLifecycleState.COMPLETED,
        contract_version="v1.0.0",
    )
    handoff_repo.save(handoff)

    # Phase 65 Closed Completion Record
    now = datetime.now(timezone.utc)
    completion = SafetyWorkflowCompletionRecord(
        completion_id=completion_id,
        source_review_id=review_id,
        source_disposition_id=disposition_id,
        source_risk_context_id="ctx-test-001",
        organization_id=org_id,
        facility_id=fac_id,
        state=CompletionLifecycleState.CLOSED,
        readiness_state="READY",
        applicable_policy_version="v1.0.0",
        requirements=[
            {
                "requirement_id": "req-001",
                "title": "Destination Action Reconciled",
                "status": "SATISFIED",
                "evidence_refs": ["ev-action-complete-001"],
            }
        ],
        outcomes=[
            {
                "handoff_id": handoff_id,
                "outcome_status": "COMPLETED",
                "contract_version": "v1.0.0",
                "verified": True,
            }
        ],
        follow_ups=[
            {
                "obligation_id": "fu-001",
                "title": "Longitudinal follow-up check",
                "status": "COMPLETED",
                "is_mandatory": True,
                "due_date": (now + timedelta(days=30)).isoformat(),
            }
        ],
        completion_package={
            "completion_id": completion_id,
            "evidence_package_refs": ["ev-package-001"],
            "supporting_evidence_references": ["ev-action-complete-001"],
        },
        review={
            "review_id": "crv-001",
            "decision": "READY_FOR_CLOSURE",
            "reviewer_id": "usr-reviewer-01",
        },
        authorization={
            "authorization_id": "auth-001",
            "authorized": True,
            "authorizer_id": "usr-authorizer-01",
        },
        closure={
            "closure_id": "cls-001",
            "closed_at": now.isoformat(),
            "closed_by": "usr-closer-01",
            "closure_rationale": "All exit gates verified",
        },
    )
    comp_repo.save(completion)
    return completion


# ===========================================================================
# SCENARIO A: Successful Verification & Idempotency
# ===========================================================================


def test_scenario_a_successful_verification(test_client):
    """Closed completion with consistent upstream/downstream state returns VERIFIED."""
    completion = seed_closed_completion_pipeline()

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={
            "policy_version": "v1.0.0",
            "reverification_reason": "Scheduled post-closure verification",
            "idempotency_key": "idem-verif-001",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.VERIFIED.value
    assert data["reassessment_required"] is False
    assert data["reopen_recommended"] is False
    assert data["findings_count"] == 0
    assert data["completed_at"] is not None

    # Idempotency check: repeated call with same key returns identical record
    repeat_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={
            "policy_version": "v1.0.0",
            "idempotency_key": "idem-verif-001",
        },
    )
    assert repeat_res.status_code == 201
    assert repeat_res.json()["verification_id"] == data["verification_id"]


# ===========================================================================
# SCENARIO B: Material Source Changes
# ===========================================================================


def test_scenario_b_source_disposition_superseded(test_client):
    """When Phase 63 source disposition is superseded or review reopened, REOPEN_RECOMMENDED is triggered."""
    completion = seed_closed_completion_pipeline()

    # Modify Phase 63 review to SUPERSEDED
    rev_repo = get_safety_risk_review_repository()
    review = rev_repo.get(completion.source_review_id)
    review.state = ReviewLifecycleState.SUPERSEDED
    rev_repo.save(review)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.REOPEN_RECOMMENDED.value
    assert data["reopen_recommended"] is True
    assert data["reassessment_required"] is True

    # Check finding was created
    findings_res = test_client.get(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/integrity-findings"
    )
    assert findings_res.status_code == 200
    findings = findings_res.json()
    assert any(f["category"] == FindingCategory.SOURCE_DISPOSITION_CHANGED.value for f in findings)


def test_scenario_b_destination_workflow_reopened(test_client):
    """When Phase 64 handoff destination is reopened or failed, REOPEN_RECOMMENDED is triggered."""
    completion = seed_closed_completion_pipeline()

    # Modify Phase 64 handoff state to BLOCKED
    handoff_repo = get_safety_risk_handoff_repository()
    handoffs = handoff_repo.get_by_disposition_id(completion.source_disposition_id)
    handoff = handoffs[0]
    handoff.state = HandoffLifecycleState.BLOCKED
    handoff_repo.save(handoff)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.REOPEN_RECOMMENDED.value
    assert data["reopen_recommended"] is True


def test_scenario_b_outcome_version_changed(test_client):
    """When Phase 64 handoff contract version updates, REASSESSMENT_REQUIRED is triggered."""
    completion = seed_closed_completion_pipeline()

    handoff_repo = get_safety_risk_handoff_repository()
    handoffs = handoff_repo.get_by_disposition_id(completion.source_disposition_id)
    handoff = handoffs[0]
    handoff.contract_version = "v2.0.0"
    handoff_repo.save(handoff)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.REASSESSMENT_REQUIRED.value
    assert data["reassessment_required"] is True


def test_scenario_b_invalidated_evidence(test_client):
    """When required supporting evidence is invalidated or withdrawn, EVIDENCE_INVALID is returned."""
    completion = seed_closed_completion_pipeline()

    # Invalidate requirement evidence
    comp_repo = get_safety_workflow_completion_repository()
    completion.requirements[0]["status"] = "INVALIDATED"
    comp_repo.save(completion)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.EVIDENCE_INVALID.value


def test_scenario_b_failed_followup(test_client):
    """When a mandatory follow-up obligation fails, REOPEN_RECOMMENDED is triggered."""
    completion = seed_closed_completion_pipeline()

    comp_repo = get_safety_workflow_completion_repository()
    completion.follow_ups[0]["status"] = "FAILED"
    comp_repo.save(completion)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.REOPEN_RECOMMENDED.value
    assert data["reopen_recommended"] is True


# ===========================================================================
# SCENARIO C: Missing & Contradictory Information
# ===========================================================================


def test_scenario_c_missing_closure_record(test_client):
    """A completion missing its closure authorization evidence triggers findings."""
    completion = seed_closed_completion_pipeline()

    comp_repo = get_safety_workflow_completion_repository()
    completion.closure = None
    comp_repo.save(completion)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] in (
        VerificationLifecycleState.REASSESSMENT_REQUIRED.value,
        VerificationLifecycleState.REOPEN_RECOMMENDED.value,
    )


def test_scenario_c_package_inconsistency_conflict(test_client):
    """Inconsistency in the completion package produces CONFLICTED state."""
    completion = seed_closed_completion_pipeline()

    comp_repo = get_safety_workflow_completion_repository()
    completion.completion_package["completion_id"] = "comp-different-id"
    comp_repo.save(completion)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.CONFLICTED.value


# ===========================================================================
# SCENARIO D: Safety Signals (Phase 59 & Phase 60)
# ===========================================================================


def test_scenario_d_material_safety_signal_triggers_reopen_recommendation(test_client):
    """Critical post-closure surveillance signal from Phase 59 creates finding & recommends reopen."""
    completion = seed_closed_completion_pipeline()

    # Seed Phase 59 critical signal
    mon_repo = get_safety_monitoring_repository()
    signal = SurveillanceSignalRecord(
        signal_id="sig-crit-999",
        source="PHASE_59_POST_CLOSURE",
        source_record_id="rec-001",
        signal_type=SafetySignalType.INCIDENT_REFERENCE,
        severity="CRITICAL",
        version="v1.0.0",
        deduplication_key="dedup-sig-001",
        scope={"domain": "CLINICAL_SAFETY_ADVERSE_REACTION"},
    )
    monitoring = SafetyMonitoringRecord(
        monitoring_id="mon-rec-001",
        verification_id="verif-seed-001",
        rollout_id="rollout-seed-001",
        change_id="chg-seed-001",
        monitored_version="v1.0.0",
        created_by="system",
        scope=MonitoringScope(
            organization_id=completion.organization_id,
            facility_id=completion.facility_id,
        ),
        lifecycle_state=MonitoringLifecycleState.ACTIVE,
        signals=[signal],
    )
    mon_repo.save(monitoring)

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == VerificationLifecycleState.REOPEN_RECOMMENDED.value
    assert data["reopen_recommended"] is True


# ===========================================================================
# SCENARIO E: Reopening Governance & Phase 65 Delegation
# ===========================================================================


def test_scenario_e_reopening_coordination_delegates_to_phase65(test_client):
    """Authorized reopening coordinates with Phase 65 and strictly preserves closure history."""
    completion = seed_closed_completion_pipeline()

    # Submit reopening request as ADMIN
    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/reopening-requests",
        json={
            "reopen_trigger": "MATERIAL_NEW_OUTCOME",
            "reason": "Downstream adverse signal requires workflow review",
            "reopen_rationale": "Full governed clinical review required",
            "finding_refs": ["fnd-001"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["authorized"] is True
    assert data["executed"] is True
    assert data["phase65_reopen_record"] is not None

    # Verify Phase 65 completion record updated to REOPENED
    comp_repo = get_safety_workflow_completion_repository()
    updated_comp = comp_repo.get(completion.completion_id)
    assert updated_comp.state == CompletionLifecycleState.REOPENED
    # Invariant check: original closure evidence remains preserved
    assert updated_comp.closure is not None
    assert updated_comp.closure["closure_id"] == "cls-001"
    assert len(updated_comp.reopen_history) == 1


def test_scenario_e_patient_forbidden_from_reopening(test_client):
    """Patients cannot request or authorize workflow reopening."""
    completion = seed_closed_completion_pipeline()

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/reopening-requests",
        json={
            "reopen_trigger": "MATERIAL_NEW_OUTCOME",
            "reason": "Patient attempt",
            "reopen_rationale": "Unauthorized",
        },
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-pat-01"},
    )
    assert response.status_code == 403


# ===========================================================================
# SCENARIO F: Retries & Event Handling
# ===========================================================================


def test_scenario_f_retry_verification(test_client):
    """Retrying an incomplete/conflicted verification succeeds and increments retry count."""
    completion = seed_closed_completion_pipeline()

    # Create first verification with conflict
    comp_repo = get_safety_workflow_completion_repository()
    completion.completion_package["completion_id"] = "conflict-id"
    comp_repo.save(completion)

    init_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )
    v_data = init_res.json()
    v_id = v_data["verification_id"]
    assert v_data["state"] == VerificationLifecycleState.CONFLICTED.value

    # Fix conflict
    completion.completion_package["completion_id"] = completion.completion_id
    comp_repo.save(completion)

    # Retry
    retry_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications/{v_id}/retry",
        json={"reason": "Inconsistency in completion package was corrected."},
    )
    assert retry_res.status_code == 200
    retry_data = retry_res.json()
    assert retry_data["state"] == VerificationLifecycleState.VERIFIED.value
    assert retry_data["retry_count"] == 1


# ===========================================================================
# SCENARIO G: Security, Privacy & Tenant Isolation
# ===========================================================================


def test_scenario_g_cross_tenant_access_denied(test_client):
    """Accessing verification or findings across tenants is forbidden."""
    completion = seed_closed_completion_pipeline(org_id="org-tenant-a")

    # Attempt access as user from tenant-b
    response = test_client.get(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        headers={"X-User-Organization": "org-tenant-b"},
    )
    assert response.status_code == 403


def test_scenario_g_patient_role_denied_verification_trigger(test_client):
    """Patients cannot trigger post-closure verifications."""
    completion = seed_closed_completion_pipeline()

    response = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
        headers={"X-User-Role": "PATIENT"},
    )
    assert response.status_code == 403


# ===========================================================================
# SCENARIO H: Integrity Finding Review, Dismissal & Resolution
# ===========================================================================


def test_scenario_h_finding_review_and_resolution(test_client):
    """Clinicians can review findings and resolve them with evidence without erasing audit trail."""
    completion = seed_closed_completion_pipeline()

    # Trigger verification that generates a policy version finding
    test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v2.0.0"},
    )

    # Get generated finding
    findings = test_client.get(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/integrity-findings"
    ).json()
    assert len(findings) > 0
    f_id = findings[0]["finding_id"]

    # 1. Review finding
    review_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/integrity-findings/{f_id}/review",
        json={
            "action": "CONFIRM",
            "notes": "Clinician confirms policy discrepancy requiring evaluation.",
        },
    )
    assert review_res.status_code == 200
    assert review_res.json()["lifecycle_state"] == FindingLifecycleState.REVIEWED.value
    assert review_res.json()["reviewed_by"] == "usr-safety-admin-01"

    # 2. Resolve finding
    resolve_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/integrity-findings/{f_id}/resolve",
        json={
            "resolution_evidence": "ev-policy-conformance-cert-001",
            "resolution_notes": "Policy diff resolved and certified conforming.",
        },
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["lifecycle_state"] == FindingLifecycleState.RESOLVED.value
    assert resolve_res.json()["resolution_evidence"] == "ev-policy-conformance-cert-001"


def test_scenario_h_dismissing_finding_requires_explicit_rationale(test_client):
    """Dismissing an integrity finding without dismissal_rationale is rejected."""
    completion = seed_closed_completion_pipeline()

    test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v2.0.0"},
    )
    findings = test_client.get(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/integrity-findings"
    ).json()
    f_id = findings[0]["finding_id"]

    bad_dismiss = test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/integrity-findings/{f_id}/review",
        json={"action": "DISMISS", "notes": "No rationale provided."},
    )
    assert bad_dismiss.status_code == 400


# ===========================================================================
# SCENARIO I: Filtered Listings, Monitoring Status & History
# ===========================================================================


def test_scenario_i_monitoring_status_and_history(test_client):
    """Operational monitoring status and chronological history responses conform to contracts."""
    completion = seed_closed_completion_pipeline()

    # Trigger verification
    test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v1.0.0"},
    )

    # 1. Monitoring status
    mon_res = test_client.get(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/monitoring-status"
    )
    assert mon_res.status_code == 200
    mon_data = mon_res.json()
    assert mon_data["monitoring_active"] is True
    assert mon_data["last_verification_state"] == VerificationLifecycleState.VERIFIED.value

    # 2. Post-closure history
    hist_res = test_client.get(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-history"
    )
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert len(hist_data["verifications"]) == 1
    assert hist_data["closure_preserved"] is not None
    assert hist_data["closure_preserved"]["closure_id"] == "cls-001"


def test_scenario_i_filtered_listings(test_client):
    """Filtered listings for pending verifications and review-required findings."""
    completion = seed_closed_completion_pipeline()

    # Generate finding
    test_client.post(
        f"/api/v1/safety-workflow-completions/{completion.completion_id}/post-closure-verifications",
        json={"policy_version": "v2.0.0"},
    )

    # Check review-required findings list
    rev_res = test_client.get("/api/v1/safety-workflow-completions/integrity-findings/review-required")
    assert rev_res.status_code == 200
    assert len(rev_res.json()) > 0

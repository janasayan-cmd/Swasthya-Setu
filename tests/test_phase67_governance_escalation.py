"""Phase 67: Clinical Safety Governance Escalation & Exception Resolution Tests.

Validates:
- Scenario A: Exception ingestion, source provenance & idempotent deduplication
- Scenario B: Policy-driven priority evaluation, routing & deterministic classification
- Scenario C: Controlled aggregation & separation of cross-workflow exceptions
- Scenario D: Ownership assignment, acknowledgement tracking & queue lookups
- Scenario E: Cross-workflow decision conflicts (preserving both sources, no auto-winner)
- Scenario F: Governance reviews, decision recording & separation of duties
- Scenario G: Resolution requirements reconciliation & blocking premature resolution
- Scenario H: Controlled closure & governed reopening preserving history
- Scenario I: Deadline tracking, overdue detection & authorized extensions
- Scenario J: Tenant isolation, role-based authorization & clinical safety boundaries
- Scenario K: Queue monitoring endpoints and filtered queries
"""

from datetime import datetime, timedelta, timezone
import os

# Ensure testing environment variables
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_escalation_repository import (
    get_governance_escalation_repository,
)
from app.schemas.auth import UserRole
from app.schemas.governance_decision_coordination import (
    ConflictSeverity,
    GovernanceReviewOutcome,
)
from app.schemas.governance_escalation import (
    EscalationLifecycleState,
    RoutingDomain,
)
from app.schemas.governance_exception import (
    ExceptionCategory,
    ExceptionLifecycleState,
    ExceptionSourcePhase,
    GovernancePriority,
)
from app.schemas.governance_resolution_requirement import (
    RequirementStatus,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = UserRole.ADMIN if role_str == "ADMIN" else (
        UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-gov-admin-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and configure auth dependency override."""
    repo = get_governance_escalation_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def test_client():
    return TestClient(app)


# ===========================================================================
# Scenario A: Exception Ingestion, Provenance & Deduplication
# ===========================================================================


def test_scenario_a_exception_ingestion_and_deduplication(test_client: TestClient):
    """Test raw exception ingestion and verify duplicate event deduplication."""
    payload = {
        "category": ExceptionCategory.MATERIAL_INTEGRITY_CHANGE.value,
        "source_phase": ExceptionSourcePhase.PHASE_66_POST_CLOSURE.value,
        "source_record_id": "verif-test-001",
        "source_version": "v1.0.0",
        "source_severity": "HIGH",
        "title": "Post-closure verification detected material downstream outcome modification",
        "description": "Downstream safety action invalidated in Phase 54 after historical completion closure.",
        "is_material": True,
        "materiality_rationale": "Materially impacts completed risk mitigation assumptions.",
    }

    # 1. First ingestion
    resp1 = test_client.post(
        "/api/v1/governance-escalations/ingest-exception",
        json=payload,
        headers={"X-User-Id": "usr-admin-01", "X-User-Organization": "org-apollo-01"},
    )
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["exception_id"].startswith("gex-")
    assert data1["category"] == ExceptionCategory.MATERIAL_INTEGRITY_CHANGE.value
    assert data1["lifecycle_state"] == ExceptionLifecycleState.ACTIVE.value
    assert data1["is_material"] is True

    # 2. Duplicate ingestion (same source_phase, source_record_id, source_version)
    resp2 = test_client.post(
        "/api/v1/governance-escalations/ingest-exception",
        json=payload,
        headers={"X-User-Id": "usr-admin-01", "X-User-Organization": "org-apollo-01"},
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    # Must be deduplicated idempotently
    assert data2["exception_id"] == data1["exception_id"]


def test_scenario_a_cross_tenant_exception_ingestion_forbidden(test_client: TestClient):
    """Test that duplicate ingestion across tenant boundaries is forbidden."""
    payload = {
        "category": ExceptionCategory.UNRESOLVED_SAFETY_FINDING.value,
        "source_phase": ExceptionSourcePhase.PHASE_63_RISK_REVIEW.value,
        "source_record_id": "rev-cross-001",
        "source_version": "v1.0.0",
        "title": "Unresolved risk finding",
        "description": "Risk review requires action",
    }
    # Tenant 1
    resp1 = test_client.post(
        "/api/v1/governance-escalations/ingest-exception",
        json=payload,
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert resp1.status_code == 201

    # Tenant 2 attempting same source
    resp2 = test_client.post(
        "/api/v1/governance-escalations/ingest-exception",
        json=payload,
        headers={"X-User-Organization": "org-max-02"},
    )
    assert resp2.status_code == 403


# ===========================================================================
# Scenario B: Escalation Creation & Priority Classification
# ===========================================================================


def test_scenario_b_create_escalation_and_priority_classification(test_client: TestClient):
    """Test policy-driven priority classification upon escalation creation."""
    # 1. Critical surveillance escalation
    crit_payload = {
        "title": "Critical Surveillance Breach Escalation",
        "summary": "Repeated critical safety alerts detected post-closure",
        "primary_category": ExceptionCategory.SURVEILLANCE_THRESHOLD_ESCALATION.value,
        "routing_domain": RoutingDomain.CLINICAL_SAFETY.value,
    }
    crit_resp = test_client.post(
        "/api/v1/governance-escalations",
        json=crit_payload,
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert crit_resp.status_code == 201
    crit_data = crit_resp.json()
    assert crit_data["governance_priority"] == GovernancePriority.CRITICAL.value
    assert crit_data["lifecycle_state"] == EscalationLifecycleState.CLASSIFIED.value

    # 2. Routine manual review
    routine_payload = {
        "title": "Routine Documentation Clarification",
        "summary": "Routine policy review question",
        "primary_category": ExceptionCategory.MANUAL_GOVERNANCE_REVIEW.value,
        "routing_domain": RoutingDomain.WORKFLOW_COORDINATION.value,
    }
    routine_resp = test_client.post(
        "/api/v1/governance-escalations",
        json=routine_payload,
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert routine_resp.status_code == 201
    assert routine_resp.json()["governance_priority"] == GovernancePriority.ROUTINE.value


# ===========================================================================
# Scenario C: Exception Aggregation & Separation
# ===========================================================================


def test_scenario_c_exception_aggregation_and_separation(test_client: TestClient):
    """Test aggregating multiple related exceptions and separating incorrectly grouped ones."""
    # Create escalation
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Complex Safety Incident Coordination",
            "summary": "Multiple workflow findings",
            "primary_category": ExceptionCategory.INCIDENT_ESCALATION_REQUIRED.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Ingest 2 exceptions
    ex1 = test_client.post(
        "/api/v1/governance-escalations/ingest-exception",
        json={
            "category": ExceptionCategory.GOVERNANCE_ACTION_FAILED.value,
            "source_phase": ExceptionSourcePhase.PHASE_54_CONTROLLED_ACTION.value,
            "source_record_id": "act-001",
            "title": "Action failed",
            "description": "Action failed to execute",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()["exception_id"]

    ex2 = test_client.post(
        "/api/v1/governance-escalations/ingest-exception",
        json={
            "category": ExceptionCategory.EFFECTIVENESS_REVIEW_FAILED.value,
            "source_phase": ExceptionSourcePhase.PHASE_55_EFFECTIVENESS.value,
            "source_record_id": "eff-001",
            "title": "Effectiveness review failed",
            "description": "Validation failed",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()["exception_id"]

    # Aggregate exceptions into escalation
    agg_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/exceptions",
        json={
            "exception_ids": [ex1, ex2],
            "aggregation_reason": "Correlated safety action and effectiveness failures",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert agg_resp.status_code == 200
    agg_data = agg_resp.json()
    assert ex1 in agg_data["aggregated_exception_ids"]
    assert ex2 in agg_data["aggregated_exception_ids"]

    # Verify exception list endpoint
    list_ex_resp = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}/exceptions",
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert list_ex_resp.status_code == 200
    assert len(list_ex_resp.json()) == 2

    # Separate exception ex2
    sep_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/exceptions/separate",
        json={
            "exception_id": ex2,
            "separation_reason": "Determined to belong to unrelated facility workflow",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert sep_resp.status_code == 200
    sep_data = sep_resp.json()
    assert ex2 not in sep_data["aggregated_exception_ids"]
    assert ex1 in sep_data["aggregated_exception_ids"]


def test_scenario_c_prevent_cross_patient_aggregation(test_client: TestClient):
    """Test that exceptions belonging to distinct patients cannot be grouped together."""
    # Escalation scoped to Patient 001
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Patient 001 Escalation",
            "summary": "Escalation",
            "primary_category": ExceptionCategory.UNRESOLVED_SAFETY_FINDING.value,
            "patient_id": "pat-001",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Exception scoped to Patient 002
    ex2 = test_client.post(
        "/api/v1/governance-escalations/ingest-exception",
        json={
            "category": ExceptionCategory.UNRESOLVED_SAFETY_FINDING.value,
            "source_phase": ExceptionSourcePhase.PHASE_63_RISK_REVIEW.value,
            "source_record_id": "rev-pat-002",
            "title": "Patient 002 finding",
            "description": "Patient 002 finding",
            "patient_id": "pat-002",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()["exception_id"]

    # Attempt aggregation
    agg_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/exceptions",
        json={
            "exception_ids": [ex2],
            "aggregation_reason": "Attempting invalid patient grouping",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert agg_resp.status_code == 400


# ===========================================================================
# Scenario D: Routing, Ownership & Acknowledgement
# ===========================================================================


def test_scenario_d_routing_ownership_and_acknowledgement(test_client: TestClient):
    """Test routing, owner assignment, deadline calculation, and owner acknowledgement."""
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Medication Safety Conflict",
            "summary": "Conflicting contraindication reviews",
            "primary_category": ExceptionCategory.CONFLICTING_AUTHORITATIVE_DECISIONS.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # 1. Route escalation
    route_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/route",
        json={
            "routing_domain": RoutingDomain.MEDICATION_SAFETY.value,
            "escalation_level": 2,
            "specialist_role_required": "CLINICAL_PHARMACOLOGIST",
            "rationale": "Complex multi-drug interaction conflict",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert route_resp.status_code == 200
    assert route_resp.json()["lifecycle_state"] == EscalationLifecycleState.ROUTED.value
    assert route_resp.json()["routing_domain"] == RoutingDomain.MEDICATION_SAFETY.value

    # 2. Assign owner
    assign_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/assign",
        json={
            "assigned_owner_id": "usr-dr-priya-01",
            "assigned_owner_role": "DOCTOR",
            "secondary_reviewer_id": "usr-admin-01",
            "rationale": "Assigning lead clinical pharmacologist",
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert assign_resp.status_code == 200
    assign_data = assign_resp.json()
    assert assign_data["lifecycle_state"] == EscalationLifecycleState.ASSIGNED.value
    assert assign_data["assigned_owner_id"] == "usr-dr-priya-01"
    assert assign_data["acknowledgement_deadline"] is not None
    assert assign_data["is_acknowledged"] is False

    # 3. Check awaiting-acknowledgement queue
    ack_queue_resp = test_client.get(
        "/api/v1/governance-escalations/queues/awaiting-acknowledgement",
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert ack_queue_resp.status_code == 200
    queue_ids = [e["escalation_id"] for e in ack_queue_resp.json()]
    assert esc_id in queue_ids

    # 4. Unauthorized actor attempts acknowledgement -> forbidden
    unauth_ack = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/acknowledge",
        json={"acknowledgement_notes": "Attempting unauthorized ack"},
        headers={"X-User-Id": "usr-other-user", "X-User-Role": "DOCTOR", "X-User-Organization": "org-apollo-01"},
    )
    assert unauth_ack.status_code == 403

    # 5. Designated owner acknowledges
    auth_ack = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/acknowledge",
        json={"acknowledgement_notes": "I accept primary responsibility for investigating this conflict."},
        headers={"X-User-Id": "usr-dr-priya-01", "X-User-Role": "DOCTOR", "X-User-Organization": "org-apollo-01"},
    )
    assert auth_ack.status_code == 200
    ack_data = auth_ack.json()
    assert ack_data["is_acknowledged"] is True
    assert ack_data["acknowledged_by"] == "usr-dr-priya-01"
    assert ack_data["lifecycle_state"] == EscalationLifecycleState.ACKNOWLEDGED.value


# ===========================================================================
# Scenario E: Cross-Workflow Decision Conflicts
# ===========================================================================


def test_scenario_e_cross_workflow_decision_conflicts(test_client: TestClient):
    """Test recording and reconciling cross-workflow decision conflicts."""
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Cross-Phase Handoff Disposition Contradiction",
            "summary": "Phase 63 vs Phase 64 disagreement",
            "primary_category": ExceptionCategory.HANDOFF_OUTCOME_CONFLICT.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Record conflict directly via conflict service
    from app.services.cross_workflow_conflict_service import get_cross_workflow_conflict_service
    cs = get_cross_workflow_conflict_service()
    user_ctx = AuthenticatedUserContext(
        user_id="usr-admin-01",
        role=UserRole.ADMIN,
        organization_id="org-apollo-01",
        facility_id="fac-delhi-01",
    )
    conflict = cs.record_conflict(
        user=user_ctx,
        escalation_id=esc_id,
        conflict_type="DISPOSITION_OUTCOME_CONTRADICTION",
        severity=ConflictSeverity.HIGH,
        source_phase_a="PHASE_63_RISK_REVIEW",
        source_record_id_a="disp-001",
        source_state_a="SPECIALIST_FOLLOW_UP_REQUIRED",
        source_version_a="v1.0.0",
        source_phase_b="PHASE_64_HANDOFF",
        source_record_id_b="handoff-001",
        source_state_b="RECONCILED_WITHOUT_FOLLOW_UP",
        source_version_b="v1.1.0",
        description="Phase 64 marked handoff reconciled while Phase 63 explicitly mandates follow-up.",
    )
    assert conflict.conflict_id.startswith("gconf-")
    assert conflict.is_resolved is False

    # Escalation state must now be CONFLICTED
    esc_status = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}",
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()
    assert esc_status["lifecycle_state"] == EscalationLifecycleState.CONFLICTED.value

    # Conflicted queue must contain this escalation
    conf_queue = test_client.get(
        "/api/v1/governance-escalations/queues/conflicted",
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()
    assert esc_id in [e["escalation_id"] for e in conf_queue]

    # Resolve conflict via endpoint
    res_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/conflicts/{conflict.conflict_id}/resolve?resolution_rationale=Specialist+follow-up+formally+waived+by+Clinical+Safety+Director",
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["is_resolved"] is True


# ===========================================================================
# Scenario F: Governance Reviews & Authoritative Decisions
# ===========================================================================


def test_scenario_f_governance_review_and_decision(test_client: TestClient):
    """Test conducting a review, issuing an authoritative decision, and checking role rules."""
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Assurance Exception Coordination",
            "summary": "Phase 52 assurance review blocked",
            "primary_category": ExceptionCategory.ASSURANCE_REVIEW_BLOCKED.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Patient cannot submit governance review
    pat_rev = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/reviews",
        json={
            "outcome": GovernanceReviewOutcome.ACTION_REQUIRED.value,
            "rationale": "Patient attempting governance action",
        },
        headers={"X-User-Role": "PATIENT", "X-User-Organization": "org-apollo-01"},
    )
    assert pat_rev.status_code == 403

    # Clinician conducts formal review
    rev_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/reviews",
        json={
            "outcome": GovernanceReviewOutcome.ACTION_REQUIRED.value,
            "rationale": "Clinical assurance requires additional lab documentation and re-evaluation.",
            "required_follow_up_actions": ["Submit updated liver enzymes panel", "Phase 52 Assurance reverification"],
        },
        headers={"X-User-Role": "DOCTOR", "X-User-Id": "usr-doc-01", "X-User-Organization": "org-apollo-01"},
    )
    assert rev_resp.status_code == 201
    rev_data = rev_resp.json()
    assert rev_data["review_id"].startswith("grev-")
    assert rev_data["outcome"] == GovernanceReviewOutcome.ACTION_REQUIRED.value

    # Record authoritative governance decision
    dec_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/decisions",
        json={
            "decision_type": "MANDATORY_REASSESSMENT_ORDER",
            "decision_title": "Order Phase 52 Clinical Reassessment",
            "rationale": "Safety assurance cannot proceed without explicit enzyme baseline confirmation.",
            "approved_actions": ["Reopen Phase 52 evidence packet"],
            "required_resolution_requirements": ["Enzyme panel submission", "Director sign-off"],
        },
        headers={"X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"},
    )
    assert dec_resp.status_code == 201
    dec_data = dec_resp.json()
    assert dec_data["decision_id"].startswith("gdec-")

    # Escalation state must transition to ACTION_REQUIRED
    esc_curr = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}",
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()
    assert esc_curr["lifecycle_state"] == EscalationLifecycleState.ACTION_REQUIRED.value


# ===========================================================================
# Scenario G: Resolution Requirements Reconciliation & Resolving
# ===========================================================================


def test_scenario_g_reconcile_requirements_and_resolve(test_client: TestClient):
    """Test that an escalation cannot be resolved until all mandatory requirements are satisfied."""
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Unresolved Risk Disposition",
            "summary": "Mandatory follow-up obligation outstanding",
            "primary_category": ExceptionCategory.RISK_DISPOSITION_REVIEW_REQUIRED.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Retrieve seeded resolution requirements
    reqs_resp = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}/resolution-requirements",
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert reqs_resp.status_code == 200
    reqs = reqs_resp.json()
    assert len(reqs) >= 1
    req_id = reqs[0]["requirement_id"]
    assert reqs[0]["status"] == RequirementStatus.PENDING.value

    # 1. Attempting resolution with unsatisfied mandatory requirement -> fails
    premature_resolve = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/resolve",
        json={"resolution_rationale": "Premature attempt to resolve"},
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert premature_resolve.status_code == 400

    # 2. Reconcile requirement to SATISFIED
    rec_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/resolution-requirements/{req_id}/reconcile",
        json={
            "status": RequirementStatus.SATISFIED.value,
            "notes": "Verified downstream specialist follow-up completed in Phase 63 review record.",
            "reconciliation_evidence": ["ev-spec-001"],
        },
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert rec_resp.status_code == 200
    assert rec_resp.json()["status"] == RequirementStatus.SATISFIED.value

    # 3. Resolve escalation successfully
    resolve_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/resolve",
        json={"resolution_rationale": "All mandatory requirements verified and satisfied."},
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["lifecycle_state"] == EscalationLifecycleState.RESOLVED.value


# ===========================================================================
# Scenario H: Controlled Closure & Governed Reopening
# ===========================================================================


def test_scenario_h_controlled_closure_and_reopening(test_client: TestClient):
    """Test controlled administrative closure and governed reopening while preserving history."""
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Post-Closure Integrity Check",
            "summary": "Closure integrity monitoring",
            "primary_category": ExceptionCategory.POST_CLOSURE_REASSESSMENT_REQUIRED.value,
        },
        headers={"X-User-Organization": "org-apollo-01", "X-User-Id": "usr-admin-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Reconcile seeded requirement
    req_id = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}/resolution-requirements",
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()[0]["requirement_id"]

    test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/resolution-requirements/{req_id}/reconcile",
        json={"status": RequirementStatus.SATISFIED.value, "notes": "Satisfied"},
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )

    # Resolve escalation
    test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/resolve",
        json={"resolution_rationale": "Resolved"},
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )

    # Close escalation
    close_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/close",
        json={
            "closure_rationale": "Administrative closure confirmed by Governance Board.",
            "administrative_notes": "All actions logged and reconciled.",
        },
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert close_resp.status_code == 200
    close_data = close_resp.json()
    assert close_data["lifecycle_state"] == EscalationLifecycleState.CLOSED.value
    assert close_data["closed_at"] is not None

    # Reopen escalation upon material new finding
    reopen_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/reopen",
        json={
            "reopen_reason": "New material safety signal observed in Phase 59 surveillance invalidating closure.",
            "triggering_source_phase": "PHASE_59_SURVEILLANCE",
            "triggering_source_record_id": "sig-crit-099",
        },
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert reopen_resp.status_code == 200
    reopen_data = reopen_resp.json()
    assert reopen_data["lifecycle_state"] == EscalationLifecycleState.REOPENED.value
    assert reopen_data["is_reopened"] is True
    assert reopen_data["reopen_count"] == 1
    # Historical closure data is preserved
    assert reopen_data["closed_at"] is not None

    # Check complete transition audit history
    hist_resp = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}/history",
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert hist_resp.status_code == 200
    hist = hist_resp.json()["history"]
    actions = [h["action"] for h in hist]
    assert "CREATE_ESCALATION" in actions
    assert "RESOLVE_ESCALATION" in actions
    assert "CLOSE_ESCALATION" in actions
    assert "REOPEN_ESCALATION" in actions


# ===========================================================================
# Scenario I: Deadline Tracking & Extensions
# ===========================================================================


def test_scenario_i_deadline_tracking_and_extensions(test_client: TestClient):
    """Test policy deadline extension authorization and validation."""
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Deadline Testing Escalation",
            "summary": "Deadline tracking test",
            "primary_category": ExceptionCategory.UNRESOLVED_SAFETY_FINDING.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Assign owner to generate deadlines
    test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/assign",
        json={"assigned_owner_id": "usr-doc-01", "assigned_owner_role": "DOCTOR", "rationale": "Assign"},
        headers={"X-User-Organization": "org-apollo-01"},
    )

    # 1. Past extension rejected
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    past_resp = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/extend-deadline",
        json={
            "deadline_type": "acknowledgement",
            "extended_until": past_time,
            "extension_rationale": "Attempting past extension",
        },
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert past_resp.status_code == 400

    # 2. Patient cannot extend deadlines
    future_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    pat_ext = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/extend-deadline",
        json={
            "deadline_type": "acknowledgement",
            "extended_until": future_time,
            "extension_rationale": "Patient attempting extension",
        },
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "PATIENT"},
    )
    assert pat_ext.status_code == 403

    # 3. Authorized extension succeeds
    auth_ext = test_client.post(
        f"/api/v1/governance-escalations/{esc_id}/extend-deadline",
        json={
            "deadline_type": "acknowledgement",
            "extended_until": future_time,
            "extension_rationale": "Owner on medical leave; secondary reviewer assuming responsibility.",
        },
        headers={"X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"},
    )
    assert auth_ext.status_code == 200
    assert auth_ext.json()["extensions_count"] == 1


# ===========================================================================
# Scenario J: Multi-Tenant Isolation & Role Authorization
# ===========================================================================


def test_scenario_j_tenant_isolation_and_role_access(test_client: TestClient):
    """Test that cross-tenant access is strictly blocked and patient permissions are restricted."""
    # Create under Org Apollo
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Tenant Isolation Test",
            "summary": "Isolation test",
            "primary_category": ExceptionCategory.EVIDENCE_INTEGRITY_EXCEPTION.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Access by Org Max must return 403
    other_tenant_resp = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}",
        headers={"X-User-Organization": "org-max-02"},
    )
    assert other_tenant_resp.status_code == 403

    # Patient role forbidden from creating escalations
    patient_create = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Patient Escalation Attempt",
            "summary": "Unauthorized",
            "primary_category": ExceptionCategory.MANUAL_GOVERNANCE_REVIEW.value,
        },
        headers={"X-User-Role": "PATIENT", "X-User-Organization": "org-apollo-01"},
    )
    assert patient_create.status_code == 403


# ===========================================================================
# Scenario K: Queue Endpoints & Filtered Listings
# ===========================================================================


def test_scenario_k_queue_endpoints_and_filtering(test_client: TestClient):
    """Test unassigned, review-required, and status summary endpoints."""
    # 1. Create an escalation -> remains in unassigned queue until assigned
    esc_resp = test_client.post(
        "/api/v1/governance-escalations",
        json={
            "title": "Queue Test Escalation",
            "summary": "Unassigned testing",
            "primary_category": ExceptionCategory.REQUIRED_APPROVAL_OVERDUE.value,
        },
        headers={"X-User-Organization": "org-apollo-01"},
    )
    esc_id = esc_resp.json()["escalation_id"]

    # Unassigned queue contains esc_id
    unassigned = test_client.get(
        "/api/v1/governance-escalations/queues/unassigned",
        headers={"X-User-Organization": "org-apollo-01"},
    ).json()
    assert esc_id in [e["escalation_id"] for e in unassigned]

    # Status summary endpoint
    status_resp = test_client.get(
        f"/api/v1/governance-escalations/{esc_id}/status",
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert status_resp.status_code == 200
    stat_data = status_resp.json()
    assert stat_data["escalation_id"] == esc_id
    assert stat_data["is_acknowledged"] is False
    assert stat_data["active_conflicts_count"] == 0

    # Filtered list endpoint by category and state
    list_filtered = test_client.get(
        f"/api/v1/governance-escalations?state={EscalationLifecycleState.CLASSIFIED.value}",
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert list_filtered.status_code == 200
    assert len(list_filtered.json()) >= 1

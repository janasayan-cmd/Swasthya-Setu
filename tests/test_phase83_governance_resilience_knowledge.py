"""Phase 83: Clinical Safety Governance Resilience Knowledge Management Tests.

Comprehensive test suite verifying:
- Scenario 1: Resilience knowledge creation in DRAFT state with disclaimer and version 1
- Scenario 2: Material change updates incrementing version and resetting lifecycle state
- Scenario 3: Submission for independent review
- Scenario 4: Author/owner self-review separation of duties rejection (HTTP 400)
- Scenario 5: Review and validation by independent reviewer
- Scenario 6: Author/owner self-approval separation of duties rejection (HTTP 400)
- Scenario 7: Publication approval by independent approver
- Scenario 8: Publication of approved resilience knowledge
- Scenario 9: Distribution gate rejection for unpublished knowledge (HTTP 400)
- Scenario 10: Campaign lifecycle: create, approve, dispatch, and complete
- Scenario 11: Acknowledgement delivery, viewing, and user confirmation
- Scenario 12: Practical application evidence submission and independent verification
- Scenario 13: Organizational learning gap identification and validation
- Scenario 14: Human validation prerequisite before Phase 54 CAPA referral
- Scenario 15: Learning gap resolution with notes
- Scenario 16: Continuous capability development recommendation lifecycle
- Scenario 17: Knowledge succession transfer and strict third-party verification
- Scenario 18: Knowledge conflict detection and automatic superseding resolution
- Scenario 19: 7 Executive reports and routine preparedness maintenance scan
- Scenario 20: Patient role authorization rejection (HTTP 403 INSUFFICIENT_PERMISSIONS)
"""

import os
from datetime import datetime, timedelta

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_resilience_knowledge_repository import (
    get_governance_resilience_knowledge_repository,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    try:
        role_enum = UserRole(role_str)
    except ValueError:
        role_enum = UserRole.SUPPORT_OPERATOR if role_str != "PATIENT" else UserRole.PATIENT
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-lead-01"),
        email=request.headers.get("X-User-Email", "lead@healthsetu.org"),
        role=role_enum,
        organization_id="org-apollo-01",
    )


@pytest.fixture(autouse=True)
def setup_test_environment():
    app.dependency_overrides[get_current_user] = mock_current_user
    repo = get_governance_resilience_knowledge_repository()
    repo.clear()
    yield
    repo.clear()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Resilience Knowledge Creation
# =============================================================================

def test_scenario_01_create_resilience_knowledge(client):
    payload = {
        "title": "Hospital Emergency Oxygen Continuity Operating Guidance",
        "category": "CONTINUITY_OPERATING_GUIDANCE",
        "summary": "Procedures for maintaining clinical oxygen manifold pressure during pipeline disruptions.",
        "content": "Step 1: Activate emergency cylinder manifold switchover. Step 2: Notify ICU head.",
        "source_phase": "PHASE_80",
        "tags": ["oxygen", "icu", "continuity"],
        "confidentiality_level": "INTERNAL",
    }
    response = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json=payload,
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["category"] == "CONTINUITY_OPERATING_GUIDANCE"
    assert data["current_state"] == "DRAFT"
    assert data["version"] == 1
    assert data["owner_id"] == "usr-author-01"
    assert data["author_id"] == "usr-author-01"
    assert "administrative capability development instruments" in data["disclaimer"]


# =============================================================================
# Scenario 2: Material Updates and Versioning
# =============================================================================

def test_scenario_02_material_update_version_increment(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Power Failure Triage Operating Procedure",
            "category": "CONTINUITY_OPERATING_GUIDANCE",
            "summary": "Triage protocols during generator switch delay.",
            "content": "Deploy headlamps and battery-powered monitors.",
        },
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    kid = create_res.json()["knowledge_id"]

    # Non-material update
    update_res1 = client.put(
        f"/api/v1/governance-resilience-knowledge/{kid}",
        json={"summary": "Updated summary for triage protocols."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert update_res1.status_code == 200
    assert update_res1.json()["version"] == 1

    # Material update
    update_res2 = client.put(
        f"/api/v1/governance-resilience-knowledge/{kid}",
        json={"content": "Deploy secondary battery units.", "material_change": True},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert update_res2.status_code == 200
    assert update_res2.json()["version"] == 2


# =============================================================================
# Scenario 3: Submission for Review
# =============================================================================

def test_scenario_03_submit_for_review(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Clinical EHR Offline Charting Guidance",
            "category": "RECOVERY_COORDINATION_GUIDANCE",
            "summary": "Paper backup chart protocols.",
            "content": "Use triplicate paper forms.",
        },
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    kid = create_res.json()["knowledge_id"]

    sub_res = client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/submit",
        json={"submission_notes": "Ready for governance committee review."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["current_state"] == "SUBMITTED_FOR_REVIEW"


# =============================================================================
# Scenario 4: Author Self-Review Violation (HTTP 400)
# =============================================================================

def test_scenario_04_author_self_review_separation_of_duties_violation(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Pharmacy Dispensation Degraded Mode",
            "category": "CONTINUITY_OPERATING_GUIDANCE",
            "summary": "Manual label check guidelines.",
            "content": "Verify high alert medications with second pharmacist.",
        },
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    kid = create_res.json()["knowledge_id"]

    client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/submit",
        json={},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )

    # Author attempts to review own record
    review_res = client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/review",
        json={"outcome": "VALIDATE", "review_notes": "Looks good to me."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert review_res.status_code == 400
    assert review_res.json()["error"]["code"] == "KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 5: Independent Review and Validation
# =============================================================================

def test_scenario_05_independent_review_and_validation(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Blood Bank Temperature Excursion Guidance",
            "category": "VALIDATED_LESSONS_LEARNED",
            "summary": "Handling blood storage cold chain breach.",
            "content": "Perform immediate haemolysis inspection.",
        },
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    kid = create_res.json()["knowledge_id"]

    client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/submit",
        json={},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )

    # Independent reviewer reviews
    review_res = client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/review",
        json={"outcome": "VALIDATE", "review_notes": "Clinically sound."},
        headers={"X-User-Id": "usr-reviewer-02", "X-User-Role": "ADMIN"},
    )
    assert review_res.status_code == 200
    assert review_res.json()["current_state"] == "VALIDATED"
    assert review_res.json()["validated_by"] == "usr-reviewer-02"


# =============================================================================
# Scenario 6: Author Self-Approval Violation (HTTP 400)
# =============================================================================

def test_scenario_06_author_self_approval_separation_of_duties_violation(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Emergency Transfer Authorization Protocol",
            "category": "DELEGATED_AUTHORITY_GUIDANCE",
            "summary": "Inter-hospital transfer authority during disaster.",
            "content": "Senior Registrar authorization valid if Consultant unavailable.",
        },
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    kid = create_res.json()["knowledge_id"]

    client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/submit",
        json={},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/review",
        json={"outcome": "VALIDATE"},
        headers={"X-User-Id": "usr-reviewer-02", "X-User-Role": "ADMIN"},
    )

    # Author attempts to approve publication
    appr_res = client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/approve",
        json={"approval_notes": "Author approval attempt."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert appr_res.status_code == 400
    assert appr_res.json()["error"]["code"] == "KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 7: Independent Publication Approval
# =============================================================================

def test_scenario_07_independent_publication_approval(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Neonatal ICU Generator Handoff Protocol",
            "category": "OPERATIONAL_HANDOFF_GUIDANCE",
            "summary": "NICU power switchover coordination.",
            "content": "Prioritize incubator circuits before general lighting.",
        },
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    kid = create_res.json()["knowledge_id"]

    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/submit", json={}, headers={"X-User-Id": "usr-author-01"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/review", json={"outcome": "VALIDATE"}, headers={"X-User-Id": "usr-reviewer-02"})

    appr_res = client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/approve",
        json={"approval_notes": "Approved for dissemination by Chief Medical Officer."},
        headers={"X-User-Id": "usr-cmo-03", "X-User-Role": "ADMIN"},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["current_state"] == "APPROVED_FOR_PUBLICATION"
    assert appr_res.json()["approved_by"] == "usr-cmo-03"


# =============================================================================
# Scenario 8: Publication of Approved Knowledge
# =============================================================================

def test_scenario_08_publish_approved_knowledge(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Water Supply Interruption Infection Control",
            "category": "CONTINUITY_OPERATING_GUIDANCE",
            "summary": "Surgical scrub alternative procedures.",
            "content": "Use alcohol rub with 3-minute contact time.",
        },
        headers={"X-User-Id": "usr-author-01"},
    )
    kid = create_res.json()["knowledge_id"]

    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/submit", json={}, headers={"X-User-Id": "usr-author-01"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/review", json={"outcome": "VALIDATE"}, headers={"X-User-Id": "usr-reviewer-02"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/approve", json={}, headers={"X-User-Id": "usr-cmo-03"})

    pub_res = client.post(
        f"/api/v1/governance-resilience-knowledge/{kid}/publish",
        json={"publication_notes": "Published to all clinical wards."},
        headers={"X-User-Id": "usr-author-01"},
    )
    assert pub_res.status_code == 200
    assert pub_res.json()["current_state"] == "PUBLISHED"
    assert pub_res.json()["published_at"] is not None


# =============================================================================
# Scenario 9: Distribution Gate Violation for Unpublished Knowledge (HTTP 400)
# =============================================================================

def test_scenario_09_distribution_gate_unpublished_knowledge_denied(client):
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Draft Radiology PACS Downtime SOP",
            "category": "CONTINUITY_OPERATING_GUIDANCE",
            "summary": "PACS image caching procedures.",
            "content": "Save DICOM images locally on modality workstation.",
        },
        headers={"X-User-Id": "usr-author-01"},
    )
    kid = create_res.json()["knowledge_id"]

    # Attempt to create campaign for DRAFT knowledge
    camp_res = client.post(
        "/api/v1/governance-resilience-knowledge/campaigns",
        json={
            "knowledge_id": kid,
            "title": "Radiology Staff Broadcast",
            "target_audiences": [{"audience_type": "DEPARTMENT", "audience_identifier": "radiology"}],
        },
        headers={"X-User-Id": "usr-author-01"},
    )
    assert camp_res.status_code == 400
    assert camp_res.json()["error"]["code"] == "UNPUBLISHED_KNOWLEDGE_DISTRIBUTION_DENIED"


# =============================================================================
# Scenario 10: Campaign Lifecycle (Create, Approve, Dispatch, Complete)
# =============================================================================

def test_scenario_10_distribution_campaign_full_lifecycle(client):
    # Setup published knowledge
    create_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={
            "title": "Hospital Evacuation Routing Guidance",
            "category": "CONTINUITY_OPERATING_GUIDANCE",
            "summary": "Safe stairwell evacuation priorities.",
            "content": "Evacuate ambulatory patients first.",
        },
        headers={"X-User-Id": "usr-author-01"},
    )
    kid = create_res.json()["knowledge_id"]
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/submit", json={}, headers={"X-User-Id": "usr-author-01"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/review", json={"outcome": "VALIDATE"}, headers={"X-User-Id": "usr-reviewer-02"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/approve", json={}, headers={"X-User-Id": "usr-cmo-03"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/publish", json={}, headers={"X-User-Id": "usr-author-01"})

    # Create campaign
    create_camp = client.post(
        "/api/v1/governance-resilience-knowledge/campaigns",
        json={
            "knowledge_id": kid,
            "title": "Evacuation Broadcast Campaign",
            "target_audiences": [{"audience_type": "FACILITY", "audience_identifier": "fac-apollo-main"}],
            "acknowledgement_required": True,
        },
        headers={"X-User-Id": "usr-author-01"},
    )
    assert create_camp.status_code == 201
    cid = create_camp.json()["campaign_id"]
    assert create_camp.json()["status"] == "DRAFT"

    # Approve campaign
    appr_camp = client.post(
        f"/api/v1/governance-resilience-knowledge/campaigns/{cid}/approve",
        json={"approval_notes": "Campaign approved."},
        headers={"X-User-Id": "usr-cmo-03"},
    )
    assert appr_camp.status_code == 200
    assert appr_camp.json()["status"] == "APPROVED"

    # Dispatch campaign with recipient user IDs
    disp_camp = client.post(
        f"/api/v1/governance-resilience-knowledge/campaigns/{cid}/dispatch",
        json={"recipient_user_ids": ["usr-nurse-01", "usr-doc-02"]},
        headers={"X-User-Id": "usr-coordinator-04"},
    )
    assert disp_camp.status_code == 200
    assert disp_camp.json()["status"] == "DISPATCHED"

    # Verify acknowledgements were seeded
    acks_res = client.get(
        f"/api/v1/governance-resilience-knowledge/acknowledgements?campaign_id={cid}",
        headers={"X-User-Id": "usr-coordinator-04"},
    )
    assert acks_res.status_code == 200
    assert len(acks_res.json()) == 2

    # Complete campaign
    comp_camp = client.post(
        f"/api/v1/governance-resilience-knowledge/campaigns/{cid}/complete",
        headers={"X-User-Id": "usr-coordinator-04"},
    )
    assert comp_camp.status_code == 200
    assert comp_camp.json()["status"] == "COMPLETED"


# =============================================================================
# Scenario 11: Acknowledgement View and User Confirmation
# =============================================================================

def test_scenario_11_user_acknowledgement_tracking(client):
    # Setup published knowledge & campaign
    k_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={"title": "Cryogenic Tank Safety SOP", "category": "PREPAREDNESS_IMPROVEMENT_GUIDANCE", "summary": "Safe vent valve ops.", "content": "Check frost collars."},
        headers={"X-User-Id": "usr-author-01"},
    )
    kid = k_res.json()["knowledge_id"]
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/submit", json={}, headers={"X-User-Id": "usr-author-01"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/review", json={"outcome": "VALIDATE"}, headers={"X-User-Id": "usr-reviewer-02"})
    client.post(f"/api/v1/governance-resilience-knowledge/{kid}/approve", json={}, headers={"X-User-Id": "usr-cmo-03"})

    c_res = client.post(
        "/api/v1/governance-resilience-knowledge/campaigns",
        json={"knowledge_id": kid, "title": "Safety Briefing"},
        headers={"X-User-Id": "usr-author-01"},
    )
    cid = c_res.json()["campaign_id"]
    client.post(f"/api/v1/governance-resilience-knowledge/campaigns/{cid}/approve", json={}, headers={"X-User-Id": "usr-cmo-03"})
    client.post(
        f"/api/v1/governance-resilience-knowledge/campaigns/{cid}/dispatch",
        json={"recipient_user_ids": ["usr-tech-01"]},
        headers={"X-User-Id": "usr-cmo-03"},
    )

    acks = client.get(
        f"/api/v1/governance-resilience-knowledge/acknowledgements?campaign_id={cid}",
        headers={"X-User-Id": "usr-tech-01"},
    ).json()
    ack_id = acks[0]["acknowledgement_id"]
    assert acks[0]["status"] == "DELIVERED"

    # User views guidance
    view_res = client.post(
        f"/api/v1/governance-resilience-knowledge/acknowledgements/{ack_id}/record",
        json={"status": "VIEWED"},
        headers={"X-User-Id": "usr-tech-01"},
    )
    assert view_res.status_code == 200
    assert view_res.json()["status"] == "VIEWED"

    # User formally acknowledges guidance
    ack_res = client.post(
        f"/api/v1/governance-resilience-knowledge/acknowledgements/{ack_id}/record",
        json={"status": "ACKNOWLEDGED", "acknowledgement_notes": "Read and understood frost collar protocols."},
        headers={"X-User-Id": "usr-tech-01"},
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"
    assert ack_res.json()["acknowledged_at"] is not None


# =============================================================================
# Scenario 12: Application Evidence & Verification Separation of Duties
# =============================================================================

def test_scenario_12_application_evidence_and_verification(client):
    k_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={"title": "Emergency Backup Triage Protocol", "category": "EXERCISE_LEARNING", "summary": "Triage drill ops.", "content": "Color coded cards."},
        headers={"X-User-Id": "usr-author-01"},
    )
    kid = k_res.json()["knowledge_id"]

    # Submit practical application evidence
    evd_res = client.post(
        "/api/v1/governance-resilience-knowledge/evidence",
        json={
            "knowledge_id": kid,
            "operational_context": "CONTINUITY_EXERCISE",
            "operational_reference_id": "ex-drill-2026",
            "description": "Applied color-coded cards during simulated mass casualty exercise.",
            "observed_effectiveness_rating": 4,
            "phase55_assessment_id": "p55-eff-991",
        },
        headers={"X-User-Id": "usr-submitter-01"},
    )
    assert evd_res.status_code == 201
    eid = evd_res.json()["evidence_id"]
    assert evd_res.json()["status"] == "RECORDED"

    # Submitter self-verification attempt (should fail 400)
    self_verify = client.post(
        f"/api/v1/governance-resilience-knowledge/evidence/{eid}/verify",
        json={"verified": True, "notes": "Self verification attempt."},
        headers={"X-User-Id": "usr-submitter-01"},
    )
    assert self_verify.status_code == 400
    assert self_verify.json()["error"]["code"] == "KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent verifier verifies
    indep_verify = client.post(
        f"/api/v1/governance-resilience-knowledge/evidence/{eid}/verify",
        json={"verified": True, "notes": "Observed drill; protocols correctly adhered to."},
        headers={"X-User-Id": "usr-evaluator-05"},
    )
    assert indep_verify.status_code == 200
    assert indep_verify.json()["status"] == "VERIFIED"
    assert indep_verify.json()["verified_by"] == "usr-evaluator-05"


# =============================================================================
# Scenario 13: Organizational Learning Gap Identification & Validation
# =============================================================================

def test_scenario_13_learning_gap_identification_and_validation(client):
    gap_res = client.post(
        "/api/v1/governance-resilience-knowledge/gaps",
        json={
            "gap_type": "UNADDRESSED_EXERCISE_FINDING",
            "severity": "HIGH",
            "title": "Incomplete Backup Oxygen Switchover in Ward 4",
            "description": "Nursing staff were unable to locate secondary manual wrench during exercise.",
            "affected_capabilities": ["cap-oxygen-manifold"],
            "affected_roles": ["NURSE"],
            "affected_facilities": ["fac-apollo-main"],
        },
        headers={"X-User-Id": "usr-observer-01"},
    )
    assert gap_res.status_code == 201
    gid = gap_res.json()["gap_id"]
    assert gap_res.json()["status"] == "IDENTIFIED"

    # Identifier self-validation attempt (should fail 400)
    self_val = client.post(
        f"/api/v1/governance-resilience-knowledge/gaps/{gid}/validate",
        json={"is_valid": True},
        headers={"X-User-Id": "usr-observer-01"},
    )
    assert self_val.status_code == 400
    assert self_val.json()["error"]["code"] == "KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent validator validates
    val_res = client.post(
        f"/api/v1/governance-resilience-knowledge/gaps/{gid}/validate",
        json={"is_valid": True, "validation_notes": "Confirmed wrench missing from designated lockbox."},
        headers={"X-User-Id": "usr-auditor-02"},
    )
    assert val_res.status_code == 200
    assert val_res.json()["status"] == "VALIDATED"
    assert val_res.json()["validated_by"] == "usr-auditor-02"


# =============================================================================
# Scenario 14: Human Validation Prerequisite Before Phase 54 CAPA Referral
# =============================================================================

def test_scenario_14_capa_referral_requires_prior_validation(client):
    # Create unvalidated gap
    gap_res = client.post(
        "/api/v1/governance-resilience-knowledge/gaps",
        json={
            "gap_type": "REPEATED_DISRUPTION_FAILURE",
            "severity": "CRITICAL",
            "title": "Frequent Telemetry Server Crashes",
            "description": "Telemetry monitoring server restarted three times in one month.",
        },
        headers={"X-User-Id": "usr-nurse-01"},
    )
    gid = gap_res.json()["gap_id"]

    # Attempt referral while still in IDENTIFIED state (should fail 400)
    unval_ref = client.post(
        f"/api/v1/governance-resilience-knowledge/gaps/{gid}/refer-capa",
        json={"capa_title": "Fix Telemetry Server Crashes", "capa_description": "Root cause analysis."},
        headers={"X-User-Id": "usr-nurse-01"},
    )
    assert unval_ref.status_code == 400
    assert unval_ref.json()["error"]["code"] == "INVALID_LEARNING_GAP_STATE"

    # Validate gap
    client.post(
        f"/api/v1/governance-resilience-knowledge/gaps/{gid}/validate",
        json={"is_valid": True},
        headers={"X-User-Id": "usr-auditor-02"},
    )

    # Now refer to CAPA
    capa_res = client.post(
        f"/api/v1/governance-resilience-knowledge/gaps/{gid}/refer-capa",
        json={"capa_title": "Investigate Telemetry Memory Leak", "capa_description": "Root cause fix."},
        headers={"X-User-Id": "usr-auditor-02"},
    )
    assert capa_res.status_code == 200
    assert capa_res.json()["status"] == "CAPA_REFERRED"
    assert capa_res.json()["capa_referral_id"].startswith("capa-ref-")


# =============================================================================
# Scenario 15: Resolve Learning Gap
# =============================================================================

def test_scenario_15_resolve_learning_gap(client):
    gap_res = client.post(
        "/api/v1/governance-resilience-knowledge/gaps",
        json={"gap_type": "OUTDATED_OPERATING_GUIDANCE", "severity": "MEDIUM", "title": "Old Dialysis Water SOP", "description": "References retired filter model."},
        headers={"X-User-Id": "usr-tech-01"},
    )
    gid = gap_res.json()["gap_id"]
    client.post(f"/api/v1/governance-resilience-knowledge/gaps/{gid}/validate", json={"is_valid": True}, headers={"X-User-Id": "usr-lead-02"})

    res_out = client.post(
        f"/api/v1/governance-resilience-knowledge/gaps/{gid}/resolve",
        json={"resolution_notes": "SOP rewritten to reference current filter system."},
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert res_out.status_code == 200
    assert res_out.json()["status"] == "RESOLVED"
    assert res_out.json()["resolved_at"] is not None


# =============================================================================
# Scenario 16: Continuous Capability Development Recommendation Lifecycle
# =============================================================================

def test_scenario_16_capability_recommendation_lifecycle(client):
    prop_res = client.post(
        "/api/v1/governance-resilience-knowledge/recommendations",
        json={
            "activity_type": "SIMULATION_DRILL",
            "priority": "HIGH",
            "title": "Hospital-wide Oxygen Failure Simulation",
            "rationalization": "Recent exercise showed ward 4 struggled with switchover manual valves.",
            "target_capabilities": ["cap-oxygen-manifold"],
            "target_roles": ["NURSE", "RESPIRATORY_THERAPIST"],
        },
        headers={"X-User-Id": "usr-planner-01"},
    )
    assert prop_res.status_code == 201
    rid = prop_res.json()["recommendation_id"]
    assert prop_res.json()["status"] == "PROPOSED"

    # Accept recommendation
    acc_res = client.put(
        f"/api/v1/governance-resilience-knowledge/recommendations/{rid}/status",
        json={"status": "ACCEPTED", "notes": "Accepted by Safety Committee."},
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert acc_res.status_code == 200
    assert acc_res.json()["status"] == "ACCEPTED"
    assert acc_res.json()["approved_by"] == "usr-lead-01"

    # Complete recommendation
    comp_res = client.put(
        f"/api/v1/governance-resilience-knowledge/recommendations/{rid}/status",
        json={"status": "COMPLETED", "notes": "Drill executed on 2026-11-20."},
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"
    assert comp_res.json()["completed_at"] is not None


# =============================================================================
# Scenario 17: Knowledge Succession Transfer & Strict Verification
# =============================================================================

def test_scenario_17_knowledge_succession_transfer_governance(client):
    # Create knowledge owned by usr-departing-01
    k_res = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={"title": "Disaster Pharmacy Command SOP", "category": "GOVERNANCE_DECISION_CONTINUITY", "summary": "Emergency drugs inventory authority.", "content": "Override stock locks."},
        headers={"X-User-Id": "usr-departing-01"},
    )
    kid = k_res.json()["knowledge_id"]

    # Self-transfer attempt (should fail 400)
    self_trf = client.post(
        "/api/v1/governance-resilience-knowledge/transfers",
        json={"knowledge_ids": [kid], "successor_owner_id": "usr-departing-01", "reason": "Self transfer"},
        headers={"X-User-Id": "usr-departing-01"},
    )
    assert self_trf.status_code == 400

    # Initiate valid transfer to usr-successor-02
    init_res = client.post(
        "/api/v1/governance-resilience-knowledge/transfers",
        json={
            "knowledge_ids": [kid],
            "successor_owner_id": "usr-successor-02",
            "reason": "Departing owner retirement.",
            "handoff_checklist": {"briefing_done": True, "access_granted": True},
        },
        headers={"X-User-Id": "usr-departing-01"},
    )
    assert init_res.status_code == 201
    tid = init_res.json()["transfer_id"]
    assert init_res.json()["status"] == "INITIATED"

    # Mark transfer completed
    client.post(
        f"/api/v1/governance-resilience-knowledge/transfers/{tid}/complete",
        json={"notes": "All documents handed over."},
        headers={"X-User-Id": "usr-departing-01"},
    )

    # Verification attempt by departing owner (should fail 400)
    v_depart = client.post(
        f"/api/v1/governance-resilience-knowledge/transfers/{tid}/verify",
        json={"approved": True},
        headers={"X-User-Id": "usr-departing-01"},
    )
    assert v_depart.status_code == 400
    assert v_depart.json()["error"]["code"] == "KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION"

    # Verification attempt by successor owner (should fail 400)
    v_succ = client.post(
        f"/api/v1/governance-resilience-knowledge/transfers/{tid}/verify",
        json={"approved": True},
        headers={"X-User-Id": "usr-successor-02"},
    )
    assert v_succ.status_code == 400
    assert v_succ.json()["error"]["code"] == "KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION"

    # Verification by independent governance lead
    v_indep = client.post(
        f"/api/v1/governance-resilience-knowledge/transfers/{tid}/verify",
        json={"approved": True, "notes": "Independent verification completed."},
        headers={"X-User-Id": "usr-gov-lead-03"},
    )
    assert v_indep.status_code == 200
    assert v_indep.json()["status"] == "VERIFIED"

    # Verify that the knowledge record's owner_id was automatically transferred!
    updated_k = client.get(
        f"/api/v1/governance-resilience-knowledge/{kid}",
        headers={"X-User-Id": "usr-gov-lead-03"},
    ).json()
    assert updated_k["owner_id"] == "usr-successor-02"


# =============================================================================
# Scenario 18: Knowledge Conflict Detection & Resolution
# =============================================================================

def test_scenario_18_knowledge_conflict_detection_and_resolution(client):
    k1 = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={"title": "Primary Ventilation Failure Protocol v2", "category": "CONTINUITY_OPERATING_GUIDANCE", "summary": "Use Bag-Valve-Mask at 12 breaths/min.", "content": "Target 12 bpm."},
        headers={"X-User-Id": "usr-doc-01"},
    ).json()["knowledge_id"]

    k2 = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={"title": "Legacy Ventilation Failure Guidance v1", "category": "CONTINUITY_OPERATING_GUIDANCE", "summary": "Use Bag-Valve-Mask at 20 breaths/min.", "content": "Target 20 bpm."},
        headers={"X-User-Id": "usr-doc-02"},
    ).json()["knowledge_id"]

    # Detect conflict
    conf_res = client.post(
        "/api/v1/governance-resilience-knowledge/conflicts",
        json={
            "conflict_type": "DIRECT_CONTRADICTION",
            "description": "Contradictory respiratory rate targets for bag-valve-mask manual ventilation.",
            "primary_knowledge_id": k1,
            "conflicting_knowledge_id": k2,
        },
        headers={"X-User-Id": "usr-doc-01"},
    )
    assert conf_res.status_code == 201
    cid = conf_res.json()["conflict_id"]
    assert conf_res.json()["status"] == "DETECTED"

    # Resolve conflict with supersede_conflicting=True
    res_conf = client.post(
        f"/api/v1/governance-resilience-knowledge/conflicts/{cid}/resolve",
        json={
            "resolution_strategy": "SUPERSEDE_LEGACY",
            "resolution_rationale": "Clinical consensus aligns with 12 breaths/min.",
            "supersede_conflicting": True,
        },
        headers={"X-User-Id": "usr-chief-01"},
    )
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "RESOLVED"

    # Verify that conflicting record was superseded
    k2_record = client.get(
        f"/api/v1/governance-resilience-knowledge/{k2}",
        headers={"X-User-Id": "usr-chief-01"},
    ).json()
    assert k2_record["current_state"] == "SUPERSEDED"
    assert k2_record["superseded_by_id"] == k1


# =============================================================================
# Scenario 19: Management Reporting & Maintenance Scan
# =============================================================================

def test_scenario_19_management_reporting_and_maintenance_scan(client):
    # Seed a published knowledge asset
    k = client.post(
        "/api/v1/governance-resilience-knowledge/",
        json={"title": "Trauma Bay Disaster Protocol", "category": "ORGANIZATIONAL_RESILIENCE_PRACTICES", "summary": "General practices.", "content": "Practices."},
        headers={"X-User-Id": "usr-lead-01"},
    ).json()["knowledge_id"]
    client.post(f"/api/v1/governance-resilience-knowledge/{k}/submit", json={}, headers={"X-User-Id": "usr-lead-01"})
    client.post(f"/api/v1/governance-resilience-knowledge/{k}/review", json={"outcome": "VALIDATE"}, headers={"X-User-Id": "usr-rev-02"})
    client.post(f"/api/v1/governance-resilience-knowledge/{k}/approve", json={}, headers={"X-User-Id": "usr-app-03"})
    client.post(f"/api/v1/governance-resilience-knowledge/{k}/publish", json={}, headers={"X-User-Id": "usr-lead-01"})

    # 1. Inventory Report
    inv = client.get("/api/v1/governance-resilience-knowledge/reports/inventory").json()
    assert inv["total_knowledge_records"] >= 1
    assert "ORGANIZATIONAL_RESILIENCE_PRACTICES" in inv["by_category"]

    # 2. Distribution Compliance Report
    dist = client.get("/api/v1/governance-resilience-knowledge/reports/distribution-compliance").json()
    assert "acknowledgement_rate_percent" in dist

    # 3. Application Evidence Report
    evd = client.get("/api/v1/governance-resilience-knowledge/reports/application-evidence").json()
    assert "average_effectiveness_rating" in evd

    # 4. Learning Gaps Report
    gaps = client.get("/api/v1/governance-resilience-knowledge/reports/learning-gaps").json()
    assert "total_gaps_identified" in gaps

    # 5. Capability Development Report
    cap = client.get("/api/v1/governance-resilience-knowledge/reports/capability-development").json()
    assert "total_recommendations" in cap

    # 6. Succession Report
    succ = client.get("/api/v1/governance-resilience-knowledge/reports/succession").json()
    assert "total_transfers" in succ

    # 7. Maturity Report
    mat = client.get("/api/v1/governance-resilience-knowledge/reports/maturity").json()
    assert "overall_resilience_posture" in mat

    # Routine Maintenance Scan
    scan = client.post("/api/v1/governance-resilience-knowledge/maintenance/scan").json()
    assert "total_anomalies_detected" in scan


# =============================================================================
# Scenario 20: Patient Role Authorization Rejection (HTTP 403)
# =============================================================================

def test_scenario_20_patient_role_rejected_with_403(client):
    response = client.get(
        "/api/v1/governance-resilience-knowledge/",
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-01"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "Patients are not permitted to access" in response.json()["error"]["message"]

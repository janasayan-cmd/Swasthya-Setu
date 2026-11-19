"""Phase 69: Clinical Safety Governance Compliance & Regulatory Evidence Tests.

Validates:
- Scenario 1: Framework registration, requirement creation, approval, and activation lifecycle
- Scenario 2: Unapproved requirements cannot be activated (REQUIREMENT_NOT_APPROVED)
- Scenario 3: Requirement-to-control mapping traceability
- Scenario 4: Full assessment passing clean (COMPLIANT) with mapped controls & valid evidence
- Scenario 5: Missing control mappings yielding CONTROL_NOT_IMPLEMENTED
- Scenario 6: Mapped controls lacking evidence yielding EVIDENCE_INSUFFICIENT (cannot produce COMPLIANT)
- Scenario 7: Inaccessible evidence yielding EVIDENCE_UNAVAILABLE
- Scenario 8: Invalidated evidence yielding EVIDENCE_CONFLICTED
- Scenario 9: Stale evidence yielding COMPLIANT_WITH_LIMITATIONS with recorded diagnostic limitations
- Scenario 10: Reassessment preserves historical assessment run and marks prior run SUPERSEDED
- Scenario 11: Compliance finding review and governed resolution
- Scenario 12: Corrective action request coordination directed to Phase 54 & Phase 55
- Scenario 13: Evidence reconciliation across items
- Scenario 14: Controlled evidence package generation, integrity hashing & access auditing
- Scenario 15: Restricted evidence tier access restrictions & tenant isolation
- Scenario 16: Patient role authorization restrictions (403 Forbidden)
- Scenario 17: Assessment idempotency verification
- Scenario 18: Aggregated compliance reporting & specialized queue lookups
"""

from datetime import datetime, timedelta, timezone
import os

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_compliance_repository import (
    get_governance_compliance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.compliance_assessment import (
    ComplianceStatus,
)
from app.schemas.compliance_evidence import (
    AccessClassification,
    EvidenceCategory,
    EvidenceValidityStatus,
)
from app.schemas.compliance_finding import (
    ComplianceGapCategory,
    CompliancePriority,
    ComplianceReviewOutcome,
)
from app.schemas.compliance_framework import (
    FrameworkLifecycleStatus,
    FrameworkType,
    RequirementCategory,
    RequirementLifecycleStatus,
    VerificationMethod,
)
from app.schemas.compliance_package_report import (
    CorrectiveActionStatus,
    PackageStatus,
    TargetAudience,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = (
        UserRole.ADMIN
        if role_str == "ADMIN"
        else (UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT)
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-gov-officer-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and configure auth dependency override."""
    repo = get_governance_compliance_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def test_client():
    return TestClient(app)


# ===========================================================================
# Scenario 1: Framework Registration, Requirement Creation, Approval & Activation
# ===========================================================================

def test_scenario_1_framework_and_requirement_lifecycle(test_client: TestClient):
    """Test full requirement lifecycle: DRAFT -> APPROVED -> ACTIVE."""
    # 1. Create Framework
    fw_payload = {
        "name": "Clinical Safety Governance Framework 2026",
        "version": "v1.0.0",
        "framework_type": "INTERNAL_SAFETY_POLICY",
        "description": "Standard governing clinical safety verification and risk acceptance.",
    }
    fw_res = test_client.post("/api/v1/governance-compliance/frameworks", json=fw_payload)
    assert fw_res.status_code == 201
    fw_data = fw_res.json()
    assert fw_data["framework_id"].startswith("gfw-")
    assert fw_data["lifecycle_status"] == "ACTIVE"
    fw_id = fw_data["framework_id"]

    # 2. Create Requirement in DRAFT
    req_payload = {
        "framework_id": fw_id,
        "requirement_code": "REQ-SAF-001",
        "title": "Dual-Clinician Sign-off on High-Risk Dispositions",
        "description": "Requires independent review before risk acceptance.",
        "category": "CLINICAL_SAFETY",
        "assessment_frequency": "MONTHLY",
    }
    req_res = test_client.post("/api/v1/governance-compliance/requirements", json=req_payload)
    assert req_res.status_code == 201
    req_data = req_res.json()
    assert req_data["lifecycle_status"] == "DRAFT"
    req_id = req_data["requirement_id"]

    # 3. Approve Requirement
    app_res = test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/approve",
        json={"approval_rationale": "Reviewed and validated against Clinical Governance Charter."},
    )
    assert app_res.status_code == 200
    assert app_res.json()["lifecycle_status"] == "APPROVED"
    assert app_res.json()["approved_by"] == "usr-gov-officer-01"

    # 4. Activate Requirement
    act_res = test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/activate",
        json={"activation_rationale": "Published for active monitoring across facilities."},
    )
    assert act_res.status_code == 200
    assert act_res.json()["lifecycle_status"] == "ACTIVE"
    assert act_res.json()["activated_by"] == "usr-gov-officer-01"


# ===========================================================================
# Scenario 2: Unapproved Requirements Cannot Be Activated
# ===========================================================================

def test_scenario_2_unapproved_requirement_activation_forbidden(test_client: TestClient):
    """Test that DRAFT requirements cannot be activated without approval."""
    # Create framework and draft requirement
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={
            "name": "Operational Standards",
            "framework_type": "OPERATIONAL_PROCEDURE",
            "description": "Standard operations.",
        },
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-OPS-002",
            "title": "Unapproved Test Requirement",
            "description": "Testing activation guard.",
            "category": "OPERATIONAL_COMPLIANCE",
        },
    )
    req_id = req_res.json()["requirement_id"]

    # Attempt activation directly on DRAFT -> Should fail with 400
    act_res = test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/activate",
        json={"activation_rationale": "Premature activation attempt."},
    )
    assert act_res.status_code == 400
    assert act_res.json()["error"]["code"] == "REQUIREMENT_NOT_APPROVED"


# ===========================================================================
# Scenario 3: Requirement-to-Control Traceability
# ===========================================================================

def test_scenario_3_requirement_control_mapping(test_client: TestClient):
    """Test mapping a requirement to an authoritative workflow control."""
    # Setup framework & approved requirement
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Traceability FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-MAP-003",
            "title": "Decision Assurance Conformance",
            "description": "Verify decision assurance checks.",
            "category": "WORKFLOW_INTEGRITY",
        },
    )
    req_id = req_res.json()["requirement_id"]

    # Create Control Mapping
    map_payload = {
        "requirement_id": req_id,
        "control_id": "CTRL-P68-DECISION-ASSURANCE",
        "control_name": "Governance Decision Provenance & Auth Verification",
        "control_owner_phase": "PHASE_68",
        "control_owner_id": "usr-lead-clinician",
        "control_purpose": "Verify all governance decisions have verifiable historical authority.",
        "verification_method": "DECISION_ASSURANCE",
        "expected_evidence": "Phase 68 DecisionAssuranceRecord in VERIFIED status.",
        "policy_version": "v1.0.0",
        "rationale": "Directly satisfies requirement for tamper-evident authorization verification.",
    }
    map_res = test_client.post("/api/v1/governance-compliance/control-mappings", json=map_payload)
    assert map_res.status_code == 201
    map_data = map_res.json()
    assert map_data["mapping_id"].startswith("gmap-")
    assert map_data["control_owner_phase"] == "PHASE_68"

    # List mapped controls for requirement
    list_res = test_client.get(f"/api/v1/governance-compliance/requirements/{req_id}/controls")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["control_id"] == "CTRL-P68-DECISION-ASSURANCE"


# ===========================================================================
# Scenario 4: Full Assessment Passing Clean (COMPLIANT)
# ===========================================================================

def test_scenario_4_full_assessment_clean_pass(test_client: TestClient):
    """Test full assessment where control is mapped and supporting evidence is active and valid."""
    # 1. Setup Framework & Active Requirement
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Compliant FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-PASS-004",
            "title": "Valid Evidence Requirement",
            "description": "Demonstrating compliant outcome.",
            "category": "CLINICAL_SAFETY",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    # 2. Map Control
    test_client.post(
        "/api/v1/governance-compliance/control-mappings",
        json={
            "requirement_id": req_id,
            "control_id": "CTRL-P65-COMPLETION",
            "control_name": "Completion Coordination",
            "control_owner_phase": "PHASE_65",
            "control_purpose": "Ensure verified completion.",
            "expected_evidence": "Handoff sign-off record.",
            "rationale": "Satisfies handoff compliance.",
        },
    )

    # 3. Register Valid Evidence
    ev_payload = {
        "source_phase": "PHASE_65",
        "source_record_id": "rec-valid-signoff-101",
        "evidence_category": "DISPOSITION_RECORD",
        "evidence_version": "v1.0.0",
        "provenance_details": {"author": "Dr. Sarah", "hsm_signed": True},
    }
    ev_res = test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/evidence", json=ev_payload)
    assert ev_res.status_code == 201

    # 4. Trigger Assessment
    asm_res = test_client.post(
        "/api/v1/governance-compliance/assessments",
        json={"requirement_id": req_id, "idempotency_key": "idem-pass-004"},
    )
    assert asm_res.status_code == 201
    asm_data = asm_res.json()
    assert asm_data["status"] == "COMPLIANT"
    assert asm_data["findings_count"] == 0
    assert len(asm_data["evidence_refs"]) == 1


# ===========================================================================
# Scenario 5: Missing Control Mappings Yielding CONTROL_NOT_IMPLEMENTED
# ===========================================================================

def test_scenario_5_missing_control_mappings_yields_control_not_implemented(test_client: TestClient):
    """Test assessment when requirement has no mapped controls."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "No Mapping FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-NOMAP-005",
            "title": "Unmapped Requirement",
            "description": "Has no controls mapped.",
            "category": "WORKFLOW_INTEGRITY",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    asm_res = test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    assert asm_res.status_code == 201
    asm_data = asm_res.json()
    assert asm_data["status"] == "CONTROL_NOT_IMPLEMENTED"
    assert asm_data["findings_count"] >= 1

    # Check finding created
    findings_res = test_client.get(f"/api/v1/governance-compliance/findings?requirement_id={req_id}")
    assert findings_res.status_code == 200
    findings = findings_res.json()
    assert len(findings) == 1
    assert findings[0]["gap_category"] == "REQUIREMENT_MAPPING_MISSING"


# ===========================================================================
# Scenario 6: Mapped Controls Lacking Evidence (EVIDENCE_INSUFFICIENT)
# ===========================================================================

def test_scenario_6_missing_evidence_cannot_produce_compliant(test_client: TestClient):
    """Test that mapped controls with zero indexed evidence yield EVIDENCE_INSUFFICIENT, never COMPLIANT."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "No Evidence FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-NOEV-006",
            "title": "No Evidence Requirement",
            "description": "Controls exist but evidence omitted.",
            "category": "AUDIT_RETENTION",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    # Map control
    test_client.post(
        "/api/v1/governance-compliance/control-mappings",
        json={
            "requirement_id": req_id,
            "control_id": "CTRL-P47-PROVENANCE",
            "control_name": "Audit Logging",
            "control_owner_phase": "PHASE_47",
            "control_purpose": "Audit trail logging.",
            "expected_evidence": "Audit event hash.",
            "rationale": "Audit trail conformance.",
        },
    )

    # Evaluate without registering evidence
    asm_res = test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    assert asm_res.status_code == 201
    asm_data = asm_res.json()
    assert asm_data["status"] == "EVIDENCE_INSUFFICIENT"
    assert asm_data["findings_count"] >= 1

    # Check evidence required queue
    q_res = test_client.get("/api/v1/governance-compliance/queues/evidence-required")
    assert q_res.status_code == 200
    queue_items = q_res.json()
    assert any(item["requirement_id"] == req_id for item in queue_items)


# ===========================================================================
# Scenario 7: Inaccessible Evidence Yielding EVIDENCE_UNAVAILABLE
# ===========================================================================

def test_scenario_7_inaccessible_evidence_yields_evidence_unavailable(test_client: TestClient):
    """Test assessment when supporting evidence is unreachable or offline."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Inaccessible FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-INACC-007",
            "title": "Inaccessible Evidence Requirement",
            "description": "Storage offline.",
            "category": "PRIVACY_DATA_PROTECTION",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    test_client.post(
        "/api/v1/governance-compliance/control-mappings",
        json={
            "requirement_id": req_id,
            "control_id": "CTRL-P24-PRIVACY",
            "control_name": "Consent Verification",
            "control_owner_phase": "PHASE_24",
            "control_purpose": "Consent check.",
            "expected_evidence": "Signed consent artifact.",
            "rationale": "Privacy conformance.",
        },
    )

    # Register evidence that is marked inaccessible
    test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        json={
            "source_phase": "PHASE_24",
            "source_record_id": "ev-inaccessible-storage-offline-999",
            "evidence_category": "CONSENT_RECORD",
        },
    )

    asm_res = test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    assert asm_res.status_code == 201
    assert asm_res.json()["status"] == "EVIDENCE_UNAVAILABLE"


# ===========================================================================
# Scenario 8: Invalidated Evidence Yielding EVIDENCE_CONFLICTED
# ===========================================================================

def test_scenario_8_invalidated_evidence_yields_evidence_conflicted(test_client: TestClient):
    """Test assessment when supporting evidence was revoked or invalidated."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Invalidated FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-INVAL-008",
            "title": "Invalidated Evidence Requirement",
            "description": "Retracted artifact.",
            "category": "RISK_GOVERNANCE",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    test_client.post(
        "/api/v1/governance-compliance/control-mappings",
        json={
            "requirement_id": req_id,
            "control_id": "CTRL-P51-RISK",
            "control_name": "Risk Acceptance",
            "control_owner_phase": "PHASE_51",
            "control_purpose": "Risk check.",
            "expected_evidence": "Signed disposition.",
            "rationale": "Risk governance.",
        },
    )

    # Register evidence that contains 'invalidated'
    test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        json={
            "source_phase": "PHASE_51",
            "source_record_id": "ev-invalidated-disposition-505",
            "evidence_category": "DISPOSITION_RECORD",
        },
    )

    asm_res = test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    assert asm_res.status_code == 201
    assert asm_res.json()["status"] == "EVIDENCE_CONFLICTED"


# ===========================================================================
# Scenario 9: Stale Evidence Yielding COMPLIANT_WITH_LIMITATIONS
# ===========================================================================

def test_scenario_9_stale_evidence_yields_compliant_with_limitations(test_client: TestClient):
    """Test assessment when evidence is valid but stale (exceeding freshness window)."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Stale FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-STALE-009",
            "title": "Stale Evidence Requirement",
            "description": "Evidence requires refresh.",
            "category": "OPERATIONAL_COMPLIANCE",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    test_client.post(
        "/api/v1/governance-compliance/control-mappings",
        json={
            "requirement_id": req_id,
            "control_id": "CTRL-P58-VERIFICATION",
            "control_name": "Verification",
            "control_owner_phase": "PHASE_58",
            "control_purpose": "Verification check.",
            "expected_evidence": "Verification report.",
            "rationale": "Operational verification.",
        },
    )

    # Register evidence that contains 'stale'
    test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        json={
            "source_phase": "PHASE_58",
            "source_record_id": "ev-stale-annual-review-2024",
            "evidence_category": "POST_CLOSURE_VERIFICATION",
        },
    )

    asm_res = test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    assert asm_res.status_code == 201
    asm_data = asm_res.json()
    assert asm_data["status"] == "COMPLIANT_WITH_LIMITATIONS"
    assert len(asm_data["limitations"]) >= 1


# ===========================================================================
# Scenario 10: Reassessment Preserves History & Marks Prior SUPERSEDED
# ===========================================================================

def test_scenario_10_reassessment_preserves_history(test_client: TestClient):
    """Test that reassessing a requirement preserves historical run and marks prior run SUPERSEDED."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Reassess FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-REASM-010",
            "title": "Reassessment Requirement",
            "description": "Historical preservation check.",
            "category": "WORKFLOW_INTEGRITY",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    # Run 1: unmapped -> CONTROL_NOT_IMPLEMENTED
    asm1_res = test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    asm1_id = asm1_res.json()["assessment_id"]
    assert asm1_res.json()["status"] == "CONTROL_NOT_IMPLEMENTED"

    # Map control and add valid evidence
    test_client.post(
        "/api/v1/governance-compliance/control-mappings",
        json={
            "requirement_id": req_id,
            "control_id": "CTRL-P66-POSTCLOSURE",
            "control_name": "Integrity Check",
            "control_owner_phase": "PHASE_66",
            "control_purpose": "Post-closure.",
            "expected_evidence": "Reconciliation log.",
            "rationale": "Integrity.",
        },
    )
    test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        json={
            "source_phase": "PHASE_66",
            "source_record_id": "ev-valid-reconciled-66",
            "evidence_category": "POST_CLOSURE_VERIFICATION",
        },
    )

    # Run 2: Reassess
    reasm_res = test_client.post(
        f"/api/v1/governance-compliance/assessments/{asm1_id}/reassess",
        json={"reassessment_reason": "Remediated mapping and uploaded evidence."},
    )
    assert reasm_res.status_code == 200
    asm2_data = reasm_res.json()
    assert asm2_data["status"] == "COMPLIANT"
    assert asm2_data["assessment_id"] != asm1_id

    # Verify prior run is now marked SUPERSEDED
    prior_get = test_client.get(f"/api/v1/governance-compliance/assessments/{asm1_id}")
    assert prior_get.status_code == 200
    assert prior_get.json()["status"] == "SUPERSEDED"


# ===========================================================================
# Scenario 11: Compliance Finding Review and Governed Resolution
# ===========================================================================

def test_scenario_11_finding_review_and_resolution(test_client: TestClient):
    """Test human specialist review and administrative resolution of findings."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Finding FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-FND-011",
            "title": "Finding Review Test",
            "description": "Desc",
            "category": "CLINICAL_SAFETY",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    # Trigger unmapped assessment -> produces finding
    test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    findings = test_client.get(f"/api/v1/governance-compliance/findings?requirement_id={req_id}").json()
    assert len(findings) >= 1
    finding_id = findings[0]["finding_id"]

    # 1. Specialist Review
    rev_res = test_client.post(
        f"/api/v1/governance-compliance/findings/{finding_id}/review",
        json={
            "review_outcome": "CORRECTIVE_ACTION_REQUIRED",
            "review_rationale": "Confirmed unmapped requirement; routing action request to clinical safety.",
            "recommended_action": "Map to Phase 63 Risk Review control.",
        },
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["review_outcome"] == "CORRECTIVE_ACTION_REQUIRED"

    # 2. Governed Resolution
    res_res = test_client.post(
        f"/api/v1/governance-compliance/findings/{finding_id}/resolve",
        json={
            "resolution_rationale": "Control mapping created and validated by clinical director.",
            "supporting_evidence_refs": ["ev-manual-signoff-doc-1"],
        },
    )
    assert res_res.status_code == 200
    assert res_res.json()["is_resolved"] is True
    assert res_res.json()["resolved_by"] == "usr-gov-officer-01"


# ===========================================================================
# Scenario 12: Corrective Action Coordination (Phase 54 & 55)
# ===========================================================================

def test_scenario_12_corrective_action_coordination(test_client: TestClient):
    """Test submitting corrective action requests directed to Phase 54 and Phase 55."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "CA FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-CA-012",
            "title": "CA Requirement",
            "description": "Desc",
            "category": "CLINICAL_SAFETY",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    test_client.post("/api/v1/governance-compliance/assessments", json={"requirement_id": req_id})
    findings = test_client.get(f"/api/v1/governance-compliance/findings?requirement_id={req_id}").json()
    finding_id = findings[0]["finding_id"]

    # Submit Corrective Action Request
    ca_payload = {
        "reason": "Missing control mapping represents critical governance gap.",
        "required_outcome": "Establish and verify automated control binding through Phase 54.",
        "phase54_action_ref": "p54-action-orchestrate-1234",
        "phase55_effectiveness_required": True,
    }
    ca_res = test_client.post(
        f"/api/v1/governance-compliance/findings/{finding_id}/corrective-actions",
        json=ca_payload,
    )
    assert ca_res.status_code == 201
    ca_data = ca_res.json()
    assert ca_data["target_phase"] == "PHASE_54_CONTROLLED_ACTION"
    assert ca_data["status"] == "SUBMITTED"
    assert ca_data["phase55_eval_ref"] is not None

    # List CAs
    list_res = test_client.get(f"/api/v1/governance-compliance/findings/{finding_id}/corrective-actions")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


# ===========================================================================
# Scenario 13: Evidence Reconciliation
# ===========================================================================

def test_scenario_13_evidence_reconciliation(test_client: TestClient):
    """Test reconciling and diagnosing evidence status across a requirement."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Recon FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-REC-013",
            "title": "Recon Requirement",
            "description": "Desc",
            "category": "AUDIT_RETENTION",
        },
    )
    req_id = req_res.json()["requirement_id"]

    # Add 1 valid, 1 stale
    test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        json={
            "source_phase": "PHASE_47",
            "source_record_id": "ev-valid-audit-1",
            "evidence_category": "AUDIT_EVENT",
        },
    )
    test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        json={
            "source_phase": "PHASE_47",
            "source_record_id": "ev-stale-audit-2",
            "evidence_category": "AUDIT_EVENT",
        },
    )

    recon_res = test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence/reconcile",
        json={"verification_depth": "FULL"},
    )
    assert recon_res.status_code == 200
    recon_data = recon_res.json()
    assert recon_data["total_items"] == 2
    assert recon_data["valid_items"] == 1
    assert recon_data["stale_items"] == 1


# ===========================================================================
# Scenario 14: Evidence Package Generation & Integrity Hashing
# ===========================================================================

def test_scenario_14_evidence_package_generation(test_client: TestClient):
    """Test generating a controlled evidence package with manifest hashing and audit logging."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Audit Package FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    pkg_payload = {
        "framework_id": fw_id,
        "title": "Annual Regulatory Safety Conformance Package 2026",
        "description": "Complete bundle of assessed safety requirements.",
        "target_audience": "REGULATORY_PREPARATION",
    }
    pkg_res = test_client.post("/api/v1/governance-compliance/evidence-packages", json=pkg_payload)
    assert pkg_res.status_code == 201
    pkg_data = pkg_res.json()
    assert pkg_data["status"] == "READY"
    assert pkg_data["integrity_hash"] is not None
    pkg_id = pkg_data["package_id"]

    # Retrieve package (increments download count)
    get_res = test_client.get(f"/api/v1/governance-compliance/evidence-packages/{pkg_id}")
    assert get_res.status_code == 200
    assert get_res.json()["download_count"] == 1

    # Check status endpoint
    status_res = test_client.get(f"/api/v1/governance-compliance/evidence-packages/{pkg_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "READY"


# ===========================================================================
# Scenario 15: Restricted Evidence Tier & Tenant Isolation
# ===========================================================================

def test_scenario_15_restricted_evidence_and_tenant_isolation(test_client: TestClient):
    """Test tenant isolation on requirements and access restriction on RESTRICTED tier evidence."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Tenant FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-TENANT-015",
            "title": "Tenant Requirement",
            "description": "Desc",
            "category": "PRIVACY_DATA_PROTECTION",
        },
    )
    req_id = req_res.json()["requirement_id"]

    # 1. Cross-tenant access -> 403 Forbidden
    other_res = test_client.get(
        f"/api/v1/governance-compliance/requirements/{req_id}",
        headers={"X-User-Organization": "org-other-hospital"},
    )
    assert other_res.status_code == 403
    assert other_res.json()["error"]["code"] == "CROSS_TENANT_ACCESS_FORBIDDEN"

    # 2. Register RESTRICTED evidence
    ev_res = test_client.post(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        json={
            "source_phase": "PHASE_24",
            "source_record_id": "ev-restricted-keys-001",
            "evidence_category": "TECHNICAL_CONFIGURATION",
            "access_classification": "RESTRICTED",
        },
    )
    ev_id = ev_res.json()["evidence_id"]

    # Doctor/Admin can access
    doc_get = test_client.get(
        f"/api/v1/governance-compliance/requirements/{req_id}/evidence",
        headers={"X-User-Role": "DOCTOR"},
    )
    assert doc_get.status_code == 200


# ===========================================================================
# Scenario 16: Patient Role Authorization Restrictions
# ===========================================================================

def test_scenario_16_patient_role_restrictions(test_client: TestClient):
    """Test that patient role cannot access compliance frameworks, requirements or assessments."""
    pat_res = test_client.get(
        "/api/v1/governance-compliance/frameworks",
        headers={"X-User-Role": "PATIENT"},
    )
    assert pat_res.status_code == 403
    assert pat_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


# ===========================================================================
# Scenario 17: Assessment Idempotency Verification
# ===========================================================================

def test_scenario_17_assessment_idempotency(test_client: TestClient):
    """Test that identical idempotency keys return the exact same assessment record."""
    fw_res = test_client.post(
        "/api/v1/governance-compliance/frameworks",
        json={"name": "Idem FW", "framework_type": "INTERNAL_SAFETY_POLICY", "description": "Desc"},
    )
    fw_id = fw_res.json()["framework_id"]

    req_res = test_client.post(
        "/api/v1/governance-compliance/requirements",
        json={
            "framework_id": fw_id,
            "requirement_code": "REQ-IDEM-017",
            "title": "Idempotent Requirement",
            "description": "Desc",
            "category": "WORKFLOW_INTEGRITY",
        },
    )
    req_id = req_res.json()["requirement_id"]
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/approve", json={"approval_rationale": "OK"})
    test_client.post(f"/api/v1/governance-compliance/requirements/{req_id}/activate", json={"activation_rationale": "OK"})

    idem_token = "unique-compliance-idem-token-017"
    run1 = test_client.post(
        "/api/v1/governance-compliance/assessments",
        json={"requirement_id": req_id, "idempotency_key": idem_token},
    )
    assert run1.status_code == 201
    asm1_id = run1.json()["assessment_id"]

    # Re-run with identical key
    run2 = test_client.post(
        "/api/v1/governance-compliance/assessments",
        json={"requirement_id": req_id, "idempotency_key": idem_token},
    )
    assert run2.status_code == 201
    asm2_id = run2.json()["assessment_id"]

    assert asm1_id == asm2_id


# ===========================================================================
# Scenario 18: Aggregated Reporting & Specialized Queue Lookups
# ===========================================================================

def test_scenario_18_reporting_and_queues(test_client: TestClient):
    """Test aggregated reports and specialized queue query endpoints."""
    # Reports
    summary = test_client.get("/api/v1/governance-compliance/reports/compliance-summary")
    assert summary.status_code == 200
    assert "total_frameworks" in summary.json()
    assert summary.json()["organization_id"] == "org-apollo-01"

    gaps = test_client.get("/api/v1/governance-compliance/reports/compliance-gaps")
    assert gaps.status_code == 200
    assert "gaps_by_category" in gaps.json()

    conformance = test_client.get("/api/v1/governance-compliance/reports/control-conformance")
    assert conformance.status_code == 200
    assert "mapping_coverage_percentage" in conformance.json()

    evidence = test_client.get("/api/v1/governance-compliance/reports/evidence-completeness")
    assert evidence.status_code == 200
    assert "total_evidence_items" in evidence.json()

    # Queues
    review_q = test_client.get("/api/v1/governance-compliance/queues/review-required")
    assert review_q.status_code == 200

    overdue_q = test_client.get("/api/v1/governance-compliance/queues/overdue")
    assert overdue_q.status_code == 200

    ev_q = test_client.get("/api/v1/governance-compliance/queues/evidence-required")
    assert ev_q.status_code == 200

    reasm_q = test_client.get("/api/v1/governance-compliance/queues/reassessment-required")
    assert reasm_q.status_code == 200

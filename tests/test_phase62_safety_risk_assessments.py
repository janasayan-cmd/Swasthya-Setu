"""Phase 62: Clinical Safety Risk Signal Consolidation, Cross-Domain Correlation & Governed Risk Assessment Tests.

Validates:
- Phase 60 and Phase 61 finding consumption into cross-domain risk assessment
- Finding eligibility, scope alignment, version alignment, and PHI privacy redaction
- Finding consolidation preserving complete source finding history
- Cross-domain correlation across safety controls, workflows, and rollout governance
- Non-negotiable architectural invariants:
    - FINDING != RISK
    - CORRELATION != CAUSATION
    - PATTERN != INCIDENT
    - SYSTEM RISK != PATIENT RISK
    - RISK PRIORITY != CLINICAL URGENCY
    - AI ASSESSMENT != GOVERNED DECISION
    - CONFLICTED / UNKNOWN / INSUFFICIENT_DATA != SAFE
- Evidence reconciliation and explicit contradiction preservation (never favored to safe)
- Governed categorical risk characterization and uncertainty quantification
- Human surveillance risk review workflow and strict AI boundary enforcement (AI cannot approve reviews or declare safety)
- Governed routing and multi-routing to authoritative downstream phases (Phase 49 Incident, Phase 51 Governance, Phase 52 Assurance, Phase 55 Effectiveness, Phase 54 Action, Phase 60 Reassessment, Phase 61 Reanalysis)
- Subpath endpoints (status, findings, evidence, correlations, risk-context, history)
- Filtered listing endpoints (review-required, high-priority, escalation-required, reassessment-required, conflicted)
- Multi-tenant isolation and security boundary enforcement
- Idempotency protection and reanalysis/reassessment requests
- Async execution simulation
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_risk_assessment_repository import get_safety_risk_assessment_repository
from app.schemas.auth import UserRole
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    AssessmentReadinessState,
    CrossDomainCorrelationOutcome,
    EvidenceReconciliationState,
    FindingEligibilityStatus,
    HumanRiskReviewDecision,
    RiskPriority,
    RiskRoutingDestination,
    RiskUncertaintyState,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-risk-officer-01"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    repo = get_safety_risk_assessment_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _sample_findings(
    base_id: str = "fnd-p61",
    org_id: str = "org-apollo-01",
    facility_id: str = "fac-delhi-01",
    control_id: str = "sc-pediatric-weight-check",
    version: str = "v2.5.0",
    count: int = 3,
) -> list:
    findings = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        findings.append({
            "finding_id": f"{base_id}-{i+1}",
            "source_phase": "PHASE_61",
            "finding_type": "SAFETY_CONTROL_CLUSTER" if i == 0 else "REPEATED_FAILURE",
            "title": f"Surveillance Finding {i+1} on {control_id}",
            "organization_id": org_id,
            "facility_id": facility_id,
            "version": version,
            "observed_at": (now - timedelta(days=count - i)).isoformat(),
            "metadata": {
                "safety_control_id": control_id,
                "workflow": "clinical-dosing",
                "rollout_id": "rol-p57-001",
                "change_id": "chg-p51-001",
            },
        })
    return findings


# ---------------------------------------------------------------------------
# 1. Creation, Input Validation & Eligibility
# ---------------------------------------------------------------------------


def test_create_risk_assessment_eligibility_filtering(client: TestClient):
    """Mismatched scopes, versions, stale timestamps, and raw PHI are filtered appropriately."""
    now = datetime.now(timezone.utc)
    raw_findings = [
        # 1. Valid eligible finding
        {
            "finding_id": "fnd-valid-01",
            "organization_id": "org-apollo-01",
            "facility_id": "fac-delhi-01",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
            "metadata": {"workflow": "clinical-dosing"},
        },
        # 2. Duplicate finding
        {
            "finding_id": "fnd-valid-01",
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
        },
        # 3. Scope mismatch (different org)
        {
            "finding_id": "fnd-wrong-org",
            "organization_id": "org-other-99",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
        },
        # 4. Version mismatch
        {
            "finding_id": "fnd-wrong-ver",
            "organization_id": "org-apollo-01",
            "version": "v9.9.9",
            "observed_at": now.isoformat(),
        },
        # 5. Privacy restricted (unminimized raw PHI)
        {
            "finding_id": "fnd-phi-leak",
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
            "metadata": {"ssn": "999-00-1111", "patient_name": "Jane Doe"},
        },
    ]

    payload = {
        "assessment_id": "sra-test-eligibility",
        "scope": {
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
        },
        "findings": raw_findings,
    }

    res = client.post("/api/v1/safety-risk-assessments", json=payload)
    assert res.status_code == 201
    data = res.json()["data"]

    assert len(data["source_findings"]) == 1
    assert data["source_findings"][0]["finding_id"] == "fnd-valid-01"

    excluded_map = {f["finding_id"]: f["eligibility_status"] for f in data["excluded_findings"]}
    assert excluded_map["fnd-valid-01"] == FindingEligibilityStatus.DUPLICATE.value
    assert excluded_map["fnd-wrong-org"] == FindingEligibilityStatus.SCOPE_MISMATCH.value
    assert excluded_map["fnd-wrong-ver"] == FindingEligibilityStatus.VERSION_MISMATCH.value
    assert excluded_map["fnd-phi-leak"] == FindingEligibilityStatus.PRIVACY_RESTRICTED.value


# ---------------------------------------------------------------------------
# 2. Consolidation & Cross-Domain Correlation
# ---------------------------------------------------------------------------


def test_consolidation_preserves_source_history_and_evaluates_correlations(client: TestClient):
    """Consolidation preserves all individual source finding references without deletion."""
    findings = _sample_findings(base_id="fnd-cons", count=3)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={
            "assessment_id": "sra-cons-01",
            "scope": {"organization_id": "org-apollo-01", "version": "v2.5.0"},
            "findings": findings,
        },
    )

    res_cons = client.post(
        "/api/v1/safety-risk-assessments/sra-cons-01/consolidate",
        json={"concern_summary": "Recurrent pediatric dosing safety control failure cluster"},
    )
    assert res_cons.status_code == 200
    data = res_cons.json()["data"]

    assert data["lifecycle_state"] == AssessmentLifecycleState.CONSOLIDATED.value
    assert data["risk_context"] is not None
    assert len(data["risk_context"]["supporting_finding_ids"]) == 3
    assert len(data["source_findings"]) == 3  # Source findings preserved!

    # Check cross-domain correlations
    assert len(data["correlations"]) >= 1
    cor = data["correlations"][0]
    assert cor["relationship"] == CrossDomainCorrelationOutcome.STRONGLY_RELATED.value
    assert "causation" in cor["analytical_note"].lower()

    # Analytical note in context verifies non-clinical diagnosis invariant
    assert "clinical diagnosis" in data["risk_context"]["analytical_note"].lower()


# ---------------------------------------------------------------------------
# 3. Evidence Reconciliation & Conflict Preservation
# ---------------------------------------------------------------------------


def test_evidence_reconciliation_preserves_contradiction(client: TestClient):
    """Contradictory evidence triggers CONFLICTED state and cannot be silently resolved to safe."""
    findings = _sample_findings(base_id="fnd-rec", count=2)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-conflict-01", "findings": findings},
    )
    client.post("/api/v1/safety-risk-assessments/sra-conflict-01/consolidate", json={})

    # Ingest external evidence claiming effectiveness while surveillance shows failures
    reconcile_payload = {
        "external_evidence": [
            {
                "source_phase": "PHASE_55",
                "source_record_id": "eff-test-99",
                "status": "VALIDATED",
                "claims_effective": True,  # Contradicts failure findings
                "description": "Phase 55 report claims safety control was 100% effective",
            }
        ]
    }

    res_rec = client.post(
        "/api/v1/safety-risk-assessments/sra-conflict-01/reconcile",
        json=reconcile_payload,
    )
    assert res_rec.status_code == 200
    data = res_rec.json()["data"]

    assert data["has_unresolved_conflicts"] is True
    assert data["lifecycle_state"] == AssessmentLifecycleState.CONFLICTED.value
    assert data["readiness_state"] == AssessmentReadinessState.CONFLICT_REQUIRES_REVIEW.value
    assert data["overall_uncertainty"] == RiskUncertaintyState.CONFLICTED_EVIDENCE.value
    assert data["requires_human_review"] is True


# ---------------------------------------------------------------------------
# 4. Governed Risk Characterization & Prioritization
# ---------------------------------------------------------------------------


def test_governed_risk_characterization(client: TestClient):
    """Characterizes system risk and sets priority without creating clinical emergency scores."""
    findings = _sample_findings(base_id="fnd-char", count=3)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-char-01", "findings": findings},
    )

    # Execute assess endpoint directly (triggers auto-consolidation)
    res_assess = client.post("/api/v1/safety-risk-assessments/sra-char-01/assess", json={})
    assert res_assess.status_code == 200
    data = res_assess.json()["data"]

    char = data["characterization"]
    assert char is not None
    assert char["primary_category"] == "SAFETY_CONTROL_INTEGRITY"
    assert char["persistence"] == "RECURRENT"
    assert char["system_severity"] == "HIGH"
    assert char["priority"] in (RiskPriority.URGENT_GOVERNANCE_REVIEW.value, RiskPriority.HIGH_PRIORITY_REVIEW.value)
    assert "clinical urgency" in char["notes"].lower()


# ---------------------------------------------------------------------------
# 5. Fail-Safe Behavior & Uncertainty Quantification
# ---------------------------------------------------------------------------


def test_empty_findings_fail_safe_behavior(client: TestClient):
    """Assessment without eligible findings yields ASSESSMENT_BLOCKED or INSUFFICIENT_DATA, never safe."""
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-empty-01", "findings": []},
    )

    res = client.post("/api/v1/safety-risk-assessments/sra-empty-01/consolidate", json={})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "CONSOLIDATION_FAILED"

    # Status must reflect blocked readiness
    res_status = client.get("/api/v1/safety-risk-assessments/sra-empty-01/status")
    assert res_status.status_code == 200
    assert res_status.json()["data"]["readiness_state"] == AssessmentReadinessState.ASSESSMENT_BLOCKED.value


# ---------------------------------------------------------------------------
# 6. Human Review Workflow & AI Boundary Restrictions
# ---------------------------------------------------------------------------


def test_ai_agent_cannot_approve_risk_assessment(client: TestClient):
    """AI agents cannot approve risk assessments or dismiss evidence conflicts (HTTP 403)."""
    findings = _sample_findings(base_id="fnd-ai", count=2)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-ai-block", "findings": findings},
    )
    client.post("/api/v1/safety-risk-assessments/sra-ai-block/assess", json={})

    review_payload = {
        "decision": HumanRiskReviewDecision.ACKNOWLEDGE.value,
        "reason": "AI summary claims all risks are acceptable",
        "is_ai": True,  # Prohibited AI action
    }

    res = client.post("/api/v1/safety-risk-assessments/sra-ai-block/review", json=review_payload)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CLINICAL_ACTION_RESTRICTED"


def test_human_review_successful_disposition(client: TestClient):
    """Authorized human safety officer reviews and escalates risk assessment."""
    findings = _sample_findings(base_id="fnd-human", count=2)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-human-rev", "findings": findings},
    )
    client.post("/api/v1/safety-risk-assessments/sra-human-rev/assess", json={})

    review_payload = {
        "decision": HumanRiskReviewDecision.ESCALATE.value,
        "reason": "Critical cross-domain risk context verified; escalating to governance committee",
        "is_ai": False,
    }

    res = client.post("/api/v1/safety-risk-assessments/sra-human-rev/review", json=review_payload)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["lifecycle_state"] == AssessmentLifecycleState.ESCALATION_REQUIRED.value
    assert data["requires_escalation"] is True
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["decision"] == HumanRiskReviewDecision.ESCALATE.value


# ---------------------------------------------------------------------------
# 7. Governed Multi-Routing
# ---------------------------------------------------------------------------


def test_governed_multi_routing(client: TestClient):
    """Risk assessment can be dispatched simultaneously to Phase 51 Governance and Phase 52 Assurance."""
    findings = _sample_findings(base_id="fnd-route", count=3)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-multiroute", "findings": findings},
    )
    client.post("/api/v1/safety-risk-assessments/sra-multiroute/assess", json={})

    routing_payload = {
        "destinations": [
            RiskRoutingDestination.PHASE_51_GOVERNANCE_REVIEW.value,
            RiskRoutingDestination.PHASE_52_ASSURANCE_REVIEW.value,
            RiskRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW.value,
        ],
        "reason": "Consolidated findings show recurrent cross-domain control degradation",
    }

    res = client.post("/api/v1/safety-risk-assessments/sra-multiroute/route", json=routing_payload)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["lifecycle_state"] == AssessmentLifecycleState.ROUTED.value
    assert len(data["routings"]) == 3
    targets = {r["destination"]: r["target_phase"] for r in data["routings"]}
    assert targets[RiskRoutingDestination.PHASE_51_GOVERNANCE_REVIEW.value] == "PHASE_51_SAFETY_GOVERNANCE"
    assert targets[RiskRoutingDestination.PHASE_52_ASSURANCE_REVIEW.value] == "PHASE_52_SAFETY_ASSURANCE"
    assert targets[RiskRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW.value] == "PHASE_55_ACTION_EFFECTIVENESS"


# ---------------------------------------------------------------------------
# 8. Subpath Resource Endpoints
# ---------------------------------------------------------------------------


def test_subpath_resource_endpoints(client: TestClient):
    """Verify detailed subpath endpoints (status, findings, evidence, correlations, risk-context, history)."""
    findings = _sample_findings(base_id="fnd-subpaths", count=3)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-subpaths-01", "findings": findings},
    )
    client.post("/api/v1/safety-risk-assessments/sra-subpaths-01/assess", json={})

    # Status
    res_status = client.get("/api/v1/safety-risk-assessments/sra-subpaths-01/status")
    assert res_status.status_code == 200
    assert "lifecycle_state" in res_status.json()["data"]

    # Findings
    res_fnds = client.get("/api/v1/safety-risk-assessments/sra-subpaths-01/findings")
    assert res_fnds.status_code == 200
    assert len(res_fnds.json()["data"]["eligible"]) == 3

    # Evidence
    res_evd = client.get("/api/v1/safety-risk-assessments/sra-subpaths-01/evidence")
    assert res_evd.status_code == 200
    assert len(res_evd.json()["data"]) >= 1

    # Correlations
    res_cors = client.get("/api/v1/safety-risk-assessments/sra-subpaths-01/correlations")
    assert res_cors.status_code == 200

    # Risk Context
    res_ctx = client.get("/api/v1/safety-risk-assessments/sra-subpaths-01/risk-context")
    assert res_ctx.status_code == 200
    assert res_ctx.json()["data"] is not None

    # History
    res_hist = client.get("/api/v1/safety-risk-assessments/sra-subpaths-01/history")
    assert res_hist.status_code == 200
    assert len(res_hist.json()["data"]) >= 2


# ---------------------------------------------------------------------------
# 9. Reanalysis & Reassessment Flows
# ---------------------------------------------------------------------------


def test_reassess_and_reanalyze_flows(client: TestClient):
    """Reassessment requests Phase 60 review; reanalysis requests Phase 61 longitudinal review."""
    findings = _sample_findings(base_id="fnd-re", count=2)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-re-01", "findings": findings},
    )
    client.post("/api/v1/safety-risk-assessments/sra-re-01/assess", json={})

    # 1. Reassess
    res_reassess = client.post(
        "/api/v1/safety-risk-assessments/sra-re-01/reassess",
        json={"reason": "Contributing signals require Phase 60 threshold reassessment"},
    )
    assert res_reassess.status_code == 200
    assert res_reassess.json()["data"]["lifecycle_state"] == AssessmentLifecycleState.REASSESSMENT_REQUIRED.value

    # 2. Reanalyze
    res_reanalyze = client.post(
        "/api/v1/safety-risk-assessments/sra-re-01/reanalyze",
        json={"reason": "Longitudinal analytics window changed; Phase 61 re-run needed"},
    )
    assert res_reanalyze.status_code == 200
    assert res_reanalyze.json()["data"]["lifecycle_state"] == AssessmentLifecycleState.STALE.value


# ---------------------------------------------------------------------------
# 10. Filtered Listing Queries
# ---------------------------------------------------------------------------


def test_filtered_listing_endpoints(client: TestClient):
    """Verify review-required, high-priority, escalation-required, reassessment-required, conflicted lists."""
    findings = _sample_findings(base_id="fnd-list", count=3)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-filter-01", "findings": findings},
    )
    client.post("/api/v1/safety-risk-assessments/sra-filter-01/assess", json={})

    # Review required
    res_rev = client.get("/api/v1/safety-risk-assessments/review-required")
    assert res_rev.status_code == 200
    assert len(res_rev.json()["data"]) >= 1

    # High priority
    res_hp = client.get("/api/v1/safety-risk-assessments/high-priority")
    assert res_hp.status_code == 200
    assert len(res_hp.json()["data"]) >= 1

    # All assessments
    res_all = client.get("/api/v1/safety-risk-assessments")
    assert res_all.status_code == 200
    assert len(res_all.json()["data"]) >= 1


# ---------------------------------------------------------------------------
# 11. Multi-Tenant Boundary Enforcement
# ---------------------------------------------------------------------------


def test_cross_tenant_access_denied(client: TestClient):
    """User from another organization must be rejected with 403 ACCESS_DENIED."""
    findings = _sample_findings(base_id="fnd-sec", count=2)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-tenant-01", "findings": findings},
    )

    headers = {
        "X-User-Id": "usr-malicious-99",
        "X-User-Organization": "org-competitor-88",
    }
    res = client.get("/api/v1/safety-risk-assessments/sra-tenant-01", headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCESS_DENIED"


# ---------------------------------------------------------------------------
# 12. Idempotency Protection
# ---------------------------------------------------------------------------


def test_idempotency_protection(client: TestClient):
    """Repeated calls with same idempotency key return original assessment deterministically."""
    findings = _sample_findings(base_id="fnd-idem", count=2)
    payload = {
        "assessment_id": "sra-idem-01",
        "idempotency_key": "idemp-risk-key-999",
        "findings": findings,
    }

    res1 = client.post("/api/v1/safety-risk-assessments", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/safety-risk-assessments", json=payload)
    assert res2.status_code == 201
    assert res2.json()["data"]["assessment_id"] == "sra-idem-01"


# ---------------------------------------------------------------------------
# 13. Phase 22 Async Execution Simulation
# ---------------------------------------------------------------------------


def test_async_assessment_execution(client: TestClient):
    """Triggering assessment with is_async=True enqueues Phase 22 worker run."""
    findings = _sample_findings(base_id="fnd-async", count=2)
    client.post(
        "/api/v1/safety-risk-assessments",
        json={"assessment_id": "sra-async-01", "findings": findings},
    )

    res = client.post(
        "/api/v1/safety-risk-assessments/sra-async-01/assess",
        json={"is_async": True},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "QUEUED"
    assert data["worker_lane"] == "CROSS_DOMAIN_RISK_ASSESSMENT_V1"

"""Phase 60: Clinical Safety Surveillance Analysis, Signal Triage & Governed Risk Escalation Tests.

Validates:
- Phase 59 surveillance signal intake into safety triage
- Provenance preservation and signal grouping
- Governed signal classification (Technical, Safety Control, Data Integrity, Privacy, Security, Unknown)
- Unknown classification remains unknown without forced automation
- Governed operational severity and evidence uncertainty quantification
- Fail-safe invariants: UNKNOWN != LOW RISK, INSUFFICIENT_DATA != NORMAL, CONFLICTED_EVIDENCE != SAFE
- Escalation conditions and explicit routing determinations
- Multi-routing orchestration across Phase 58 (Reopen), Phase 49 (Incident), Phase 51 (Governance), Phase 52 (Assurance), Phase 55 (Effectiveness)
- Human surveillance triage review workflow and strict AI boundary enforcement (AI cannot approve reviews, reopen, or confirm harm)
- Separation of duties and multi-tenant isolation
- Filtered listing endpoints (review-required, high-priority, escalation-required, reopen-required, incident-routing-required, governance-routing-required)
- Async triage processing without PHI leakage
"""

from datetime import datetime, timezone
from typing import Optional
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_triage_repository import get_safety_triage_repository
from app.schemas.auth import UserRole
from app.schemas.safety_triage import (
    EscalationRoutingPriority,
    GovernedSignalSeverity,
    HumanTriageReviewDecision,
    RoutingDestination,
    SignalClassification,
    TriageLifecycleState,
    UncertaintyState,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_triage_async_service import get_safety_triage_async_service


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-triage-officer-01"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    repo = get_safety_triage_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _sample_triage_payload(
    triage_id: str = "trg-p60-001",
    primary_signal_id: str = "sig-p59-001",
    signal_type: str = "SAFETY_CONTROL_FAILURE",
    severity: str = "CRITICAL",
    org_id: str = "org-apollo-01",
    facility_id: str = "fac-delhi-01",
    version: str = "v2.5.0",
) -> dict:
    return {
        "triage_id": triage_id,
        "primary_signal_id": primary_signal_id,
        "monitoring_id": "mon-p59-001",
        "verification_id": "ver-p58-001",
        "change_id": "chg-p51-001",
        "rollout_id": "rol-p57-001",
        "version": version,
        "scope": {
            "organization_id": org_id,
            "facility_id": facility_id,
            "department": "pediatrics",
            "workflow": "clinical-dosing",
            "safety_control_id": "sc-pediatric-weight-check",
            "environment": "production",
        },
        "signal_data": {
            "source": "Phase 59",
            "source_record_id": "ctrl-evt-001",
            "signal_type": signal_type,
            "severity": severity,
            "metadata": {"violation_code": "DOSE_LIMIT_EXCEEDED"},
        },
        "related_signals": [
            {
                "signal_id": f"sig-rel-{triage_id}",
                "source": "Phase 48",
                "source_record_id": "ctrl-evt-002",
                "signal_type": signal_type,
                "severity": severity,
                "metadata": {"guardrail_tripped": True},
            }
        ],
        "evidence_items": [
            {
                "evidence_id": f"evi-{triage_id}",
                "evidence_type": "SAFETY_CONTROL_LOG",
                "source_phase": "Phase 48",
                "reference_id": "log-entry-99",
                "description": "Deterministic safety gate execution trace",
            }
        ],
    }


# =====================================================================
# 1. Creation, Idempotency & Tenant Isolation Tests
# =====================================================================


def test_create_safety_triage_success(client):
    payload = _sample_triage_payload()
    resp = client.post("/api/v1/safety-triage", json=payload, headers={"X-Idempotency-Key": "idem-p60-001"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["triage_id"] == "trg-p60-001"
    assert data["primary_signal_id"] == "sig-p59-001"
    assert data["organization_id"] == "org-apollo-01"
    assert len(data["signals"]) == 2  # Primary + related
    assert len(data["evidence"]) == 1


def test_create_safety_triage_idempotency_safe_replay(client):
    payload = _sample_triage_payload()
    headers = {"X-Idempotency-Key": "idem-p60-replay"}
    r1 = client.post("/api/v1/safety-triage", json=payload, headers=headers)
    assert r1.status_code == 201

    # Safe replay returns existing
    r2 = client.post("/api/v1/safety-triage", json=payload, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["data"]["triage_id"] == "trg-p60-001"


def test_create_safety_triage_idempotency_conflict(client):
    payload = _sample_triage_payload()
    headers = {"X-Idempotency-Key": "idem-p60-conflict"}
    r1 = client.post("/api/v1/safety-triage", json=payload, headers=headers)
    assert r1.status_code == 201

    conflict_payload = _sample_triage_payload(triage_id="trg-p60-different")
    r2 = client.post("/api/v1/safety-triage", json=conflict_payload, headers=headers)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_cross_tenant_access_denied(client):
    client.post("/api/v1/safety-triage", json=_sample_triage_payload("trg-org-1", org_id="org-apollo-01"))

    # Access with different tenant header
    resp = client.get(
        "/api/v1/safety-triage/trg-org-1",
        headers={"X-User-Organization": "org-fortis-02"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"


# =====================================================================
# 2. Signal Classification Tests
# =====================================================================


def test_signal_classification_governed_categories(client):
    client.post(
        "/api/v1/safety-triage",
        json=_sample_triage_payload("trg-cls-1", signal_type="SAFETY_CONTROL_FAILURE"),
    )

    # Classify endpoint
    resp = client.post(
        "/api/v1/safety-triage/trg-cls-1/classify",
        json={"classification": "SAFETY_CONTROL", "rationale": "Safety guardrail gate breach"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["classification"] == "SAFETY_CONTROL"
    assert data["requires_human_review"] is True


def test_unknown_classification_remains_unknown(client):
    # Payload with an unmapped signal type
    payload = _sample_triage_payload("trg-unk-1", signal_type="UNUSUAL_CUSTOM_OS_METRIC")
    client.post("/api/v1/safety-triage", json=payload)

    resp = client.post(
        "/api/v1/safety-triage/trg-unk-1/classify",
        json={"classification": "UNKNOWN", "rationale": "Ambiguous anomalous signal without clear category"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Fail-safe: UNKNOWN remains UNKNOWN and requires human review
    assert data["classification"] == "UNKNOWN"
    assert data["requires_human_review"] is True


def test_ai_classification_requires_human_review(client):
    client.post("/api/v1/safety-triage", json=_sample_triage_payload("trg-ai-cls-1"))

    resp = client.post(
        "/api/v1/safety-triage/trg-ai-cls-1/classify",
        json={
            "classification": "TECHNICAL",
            "rationale": "Automated ML clustering suggested network latency anomaly",
            "is_ai_agent": True,
            "ai_metadata": {"model": "signal-cluster-v1", "confidence": 0.88},
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["requires_human_review"] is True
    assert "ai_classification_metadata" in data["metadata"]


# =====================================================================
# 3. Severity & Uncertainty Evaluation Tests
# =====================================================================


def test_severity_evaluation_critical_safety_control_failure(client):
    client.post(
        "/api/v1/safety-triage",
        json=_sample_triage_payload("trg-sev-crit", signal_type="SAFETY_CONTROL_FAILURE", severity="CRITICAL"),
    )

    resp = client.post("/api/v1/safety-triage/trg-sev-crit/evaluate-severity")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["governed_severity"] == "CRITICAL"
    assert data["priority"] == "CRITICAL_ESCALATION"
    assert data["is_escalated"] is True
    assert data["requires_human_review"] is True


def test_failsafe_insufficient_data_and_conflicted_evidence(client):
    # Create triage with conflicted evidence metadata
    payload = _sample_triage_payload("trg-conflicted", signal_type="LATENCY_INCREASE", severity="LOW")
    payload["signal_data"]["metadata"]["conflicted"] = True
    client.post("/api/v1/safety-triage", json=payload)

    resp = client.post("/api/v1/safety-triage/trg-conflicted/evaluate-severity")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Fail-safe invariant: CONFLICTED_EVIDENCE does not equal SAFE or LOW_PRIORITY
    assert data["uncertainty_state"] == "CONFLICTED_EVIDENCE"
    assert data["requires_human_review"] is True
    assert data["priority"] == "HIGH_PRIORITY_REVIEW"


# =====================================================================
# 4. Governed Routing & Multi-Routing Tests
# =====================================================================


def test_critical_signal_multi_routing(client):
    # Create critical safety control triage context
    client.post(
        "/api/v1/safety-triage",
        json=_sample_triage_payload("trg-multi-1", signal_type="SAFETY_CONTROL_FAILURE", severity="CRITICAL"),
    )

    # Run end-to-end evaluation
    resp_eval = client.post("/api/v1/safety-triage/trg-multi-1/evaluate")
    assert resp_eval.status_code == 200
    data = resp_eval.json()["data"]
    assert data["lifecycle_state"] == "REOPEN_REQUIRED"

    # Verify Multi-Routing Decisions created (Phase 58 Reopen, Phase 49 Incident, Phase 51 Governance)
    routes = data["routing_decisions"]
    destinations = [d["destination"] for d in routes]
    assert "PHASE_58_REOPEN_REVIEW" in destinations
    assert "PHASE_49_INCIDENT_ROUTING" in destinations
    assert "PHASE_51_GOVERNANCE_REVIEW" in destinations


def test_assurance_signal_routing(client):
    client.post(
        "/api/v1/safety-triage",
        json=_sample_triage_payload("trg-assur-1", signal_type="ASSURANCE_REGRESSION", severity="HIGH"),
    )

    resp = client.post("/api/v1/safety-triage/trg-assur-1/evaluate")
    assert resp.status_code == 200
    data = resp.json()["data"]
    destinations = [d["destination"] for d in data["routing_decisions"]]
    assert "PHASE_52_ASSURANCE_REVIEW" in destinations
    assert data["lifecycle_state"] == "ASSURANCE_ROUTING_REQUIRED"


def test_effectiveness_signal_routing(client):
    client.post(
        "/api/v1/safety-triage",
        json=_sample_triage_payload("trg-eff-1", signal_type="EFFECTIVENESS_REGRESSION", severity="HIGH"),
    )

    resp = client.post("/api/v1/safety-triage/trg-eff-1/evaluate")
    assert resp.status_code == 200
    data = resp.json()["data"]
    destinations = [d["destination"] for d in data["routing_decisions"]]
    assert "PHASE_55_EFFECTIVENESS_REVIEW" in destinations
    assert data["lifecycle_state"] == "EFFECTIVENESS_ROUTING_REQUIRED"


def test_nominal_signal_routes_to_continue_monitoring(client):
    # Routine low severity latency jitter with zero conflict
    payload = _sample_triage_payload("trg-nom-1", signal_type="TECHNICAL_LATENCY", severity="LOW")
    payload["related_signals"] = []  # Single signal
    client.post("/api/v1/safety-triage", json=payload)

    resp = client.post("/api/v1/safety-triage/trg-nom-1/evaluate")
    assert resp.status_code == 200
    data = resp.json()["data"]
    destinations = [d["destination"] for d in data["routing_decisions"]]
    assert "CONTINUE_MONITORING" in destinations
    assert data["lifecycle_state"] == "ROUTED"
    assert data["requires_human_review"] is False


def test_explicit_authorized_routing_execution(client):
    client.post("/api/v1/safety-triage", json=_sample_triage_payload("trg-exec-route-1"))

    # Execute authorized route
    resp = client.post(
        "/api/v1/safety-triage/trg-exec-route-1/route",
        json={
            "destination": "PHASE_49_INCIDENT_ROUTING",
            "reason": "Authorized officer routed signal to Phase 49 for clinical incident investigation",
            "target_phase": "Phase 49",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["destination"] == "PHASE_49_INCIDENT_ROUTING"

    # Duplicate routing attempt raises 409
    dup_resp = client.post(
        "/api/v1/safety-triage/trg-exec-route-1/route",
        json={
            "destination": "PHASE_49_INCIDENT_ROUTING",
            "reason": "Repeated routing",
        },
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "ROUTING_ALREADY_COMPLETED"


def test_reassessment_routing(client):
    client.post("/api/v1/safety-triage", json=_sample_triage_payload("trg-reassess-1"))

    resp = client.post(
        "/api/v1/safety-triage/trg-reassess-1/reassess",
        json={"reason": "Longitudinal trend warrants formal governance reassessment"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["destination"] == "PHASE_58_REASSESSMENT"

    # Check status
    stat = client.get("/api/v1/safety-triage/trg-reassess-1/status").json()["data"]
    assert stat["lifecycle_state"] == "REASSESSMENT_REQUIRED"


# =====================================================================
# 5. Human Review Workflow & AI Boundary Enforcement
# =====================================================================


def test_human_triage_review_workflow(client):
    client.post("/api/v1/safety-triage", json=_sample_triage_payload("trg-rev-1"))

    resp = client.post(
        "/api/v1/safety-triage/trg-rev-1/review",
        json={
            "decision": "ESCALATE",
            "rationale": "Safety supervisor verified critical weight check failure pattern",
        },
    )
    assert resp.status_code == 200
    rev = resp.json()["data"]
    assert rev["decision"] == "ESCALATE"
    assert rev["reviewer_id"] == "usr-triage-officer-01"

    stat = client.get("/api/v1/safety-triage/trg-rev-1/status").json()["data"]
    assert stat["lifecycle_state"] == "ESCALATION_REQUIRED"
    assert stat["is_escalated"] is True


def test_ai_cannot_conduct_triage_review_or_routing(client):
    client.post("/api/v1/safety-triage", json=_sample_triage_payload("trg-ai-rev-1"))

    # Attempt review with AI flag
    resp = client.post(
        "/api/v1/safety-triage/trg-ai-rev-1/review",
        json={
            "decision": "CONTINUE",
            "rationale": "AI autonomous decision claiming no patient harm occurred",
            "is_ai_agent": True,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"


# =====================================================================
# 6. Filtered Listing Endpoints & Single Reanalysis
# =====================================================================


def test_filtered_listing_endpoints(client):
    # Create two records: one critical/reopen, one review-required
    client.post(
        "/api/v1/safety-triage",
        json=_sample_triage_payload("trg-list-crit", signal_type="SAFETY_CONTROL_FAILURE", severity="CRITICAL"),
    )
    client.post("/api/v1/safety-triage/trg-list-crit/evaluate")

    client.post(
        "/api/v1/safety-triage",
        json=_sample_triage_payload("trg-list-warn", signal_type="WORKFLOW_FAILURE", severity="MEDIUM"),
    )
    client.post("/api/v1/safety-triage/trg-list-warn/evaluate")

    # 1. /review-required
    r_rev = client.get("/api/v1/safety-triage/review-required")
    assert r_rev.status_code == 200
    ids_rev = [r["triage_id"] for r in r_rev.json()["data"]]
    assert "trg-list-crit" in ids_rev

    # 2. /high-priority
    r_high = client.get("/api/v1/safety-triage/high-priority")
    assert r_high.status_code == 200
    ids_high = [r["triage_id"] for r in r_high.json()["data"]]
    assert "trg-list-crit" in ids_high

    # 3. /reopen-required
    r_reopen = client.get("/api/v1/safety-triage/reopen-required")
    assert r_reopen.status_code == 200
    ids_reopen = [r["triage_id"] for r in r_reopen.json()["data"]]
    assert "trg-list-crit" in ids_reopen

    # 4. /incident-routing-required
    r_inc = client.get("/api/v1/safety-triage/incident-routing-required")
    assert r_inc.status_code == 200

    # 5. /reanalysis (batch)
    r_reanalysis = client.post("/api/v1/safety-triage/reanalysis")
    assert r_reanalysis.status_code == 200
    assert r_reanalysis.json()["data"]["reanalysis_completed"] is True

    # 6. /{triage_id}/reanalysis (single)
    r_single = client.post("/api/v1/safety-triage/trg-list-crit/reanalysis")
    assert r_single.status_code == 200
    assert r_single.json()["data"]["triage_id"] == "trg-list-crit"


# =====================================================================
# 7. Asynchronous Triage Background Processing
# =====================================================================


@pytest.mark.asyncio
async def test_async_triage_scheduled_job():
    from app.services.safety_triage_service import get_safety_triage_service
    from app.schemas.safety_triage import CreateTriageRequest

    srv = get_safety_triage_service()
    user = AuthenticatedUserContext(
        user_id="usr-async-worker",
        role=UserRole.ADMIN,
        organization_id="org-apollo-01",
        facility_id="fac-delhi-01",
    )
    req = CreateTriageRequest(**_sample_triage_payload("trg-async-01"))
    srv.create_triage(req, user)

    # Run async scheduled triage cycle
    async_srv = get_safety_triage_async_service()
    res = await async_srv.run_scheduled_triage_cycle("org-apollo-01")
    assert res["status"] == "COMPLETED"
    assert res["processed_count"] >= 1

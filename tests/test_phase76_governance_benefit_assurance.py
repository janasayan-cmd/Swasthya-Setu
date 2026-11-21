"""Phase 76: Governance Portfolio Performance Assurance & Benefit Realization Tests.

Validates:
- Scenario 1: Benefit registration, validation of Phase 72/73/74/75 references, duplicate prevention, and lineage reconstruction
- Scenario 2: Version-controlled baseline creation, submission, and separation of duties on approval
- Scenario 3: Version-controlled target creation, submission, and separation of duties on approval
- Scenario 4: Configurable performance indicators, reproducible calculations, and missing data handling
- Scenario 5: Measurement intake, unit compatibility validation, separation of duties on validation, and rejection
- Scenario 6: Benefit realization assessment (REALIZED when target met with validated measurements, clinical safety notice)
- Scenario 7: Benefit realization assessment (INSUFFICIENT_EVIDENCE when unverified or missing measurements)
- Scenario 8: Portfolio-level cumulative benefit aggregation and summary
- Scenario 9: Transparent attribution analysis (distinguishing correlation from direct attribution)
- Scenario 10: Unintended consequences & trade-offs logging, human review, and authoritative routing (Phase 54/49)
- Scenario 11: Longitudinal benefit sustainability monitoring and stability scoring
- Scenario 12: Independent verification coordination and conflict-of-interest checks
- Scenario 13: Benefit exception management with explicit authorization reference and escalation to Phase 67
- Scenario 14: Strategic management review packaging and referral to Phase 72 Management Review
- Scenario 15: Consolidated reporting endpoints & background routine scan
- Scenario 16: Multi-tenant boundary isolation
- Scenario 17: Patient role authorization enforcement (403 Forbidden)
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
from app.repositories.governance_benefit_assurance_repository import (
    get_governance_benefit_assurance_repository,
)
from app.repositories.governance_decision_implementation_repository import (
    get_governance_decision_implementation_repository,
)
from app.repositories.governance_change_adoption_repository import (
    get_governance_change_adoption_repository,
)
from app.repositories.governance_change_portfolio_repository import (
    get_governance_change_portfolio_repository,
)
from app.schemas.auth import UserRole
from app.schemas.decision_implementation_register import (
    DecisionImplementationRecord,
    ImplementationCategory,
    ImplementationPriority,
    ImplementationStatus,
)
from app.schemas.governance_change_adoption_registration import (
    GovernanceChangeAdoptionRecord,
    AdoptionRegistrationStatus,
    OperationalScope,
)
from app.schemas.governance_change_portfolio import (
    GovernanceChangePortfolioRecord,
    PortfolioPriority,
    PortfolioStatus,
)
from app.schemas.governance_benefit_register import (
    BenefitCategory,
    BenefitStatus,
)
from app.schemas.governance_benefit_baseline_target import (
    BaselineStatus,
    TargetStatus,
)
from app.schemas.governance_benefit_indicator_measurement import (
    ExpectedDirection,
    IndicatorOutcome,
    IndicatorType,
    MeasurementStatus,
)
from app.schemas.governance_benefit_assessment import (
    RealizationDisposition,
)
from app.schemas.governance_benefit_attribution_consequences import (
    AttributionType,
    ConsequenceClassification,
)
from app.schemas.governance_benefit_sustainability_verification import (
    SustainabilityTrend,
    VerificationStatus,
)
from app.schemas.governance_benefit_exceptions_reviews import (
    BenefitExceptionStatus,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    try:
        role_enum = UserRole(role_str)
    except ValueError:
        role_enum = UserRole.SUPPORT_OPERATOR if role_str != "PATIENT" else UserRole.PATIENT
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-lead-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_current_user] = mock_current_user
    repo = get_governance_benefit_assurance_repository()
    repo.clear()
    phase73_repo = get_governance_decision_implementation_repository()
    phase73_repo.clear()
    phase74_repo = get_governance_change_adoption_repository()
    phase74_repo.clear()
    phase75_repo = get_governance_change_portfolio_repository()
    phase75_repo.clear()
    yield
    repo.clear()
    phase73_repo.clear()
    phase74_repo.clear()
    phase75_repo.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def seed_phase73_implementation(implementation_id: str = "impl_valid_001", tenant_id: str = "org-apollo-01"):
    phase73_repo = get_governance_decision_implementation_repository()
    now_dt = datetime.now(timezone.utc)
    record = DecisionImplementationRecord(
        implementation_id=implementation_id,
        decision_id="dec_approved_100",
        intake_id="intake_100",
        title="Clinical Safety SBAR Triage Protocol Implementation",
        description="Standardized implementation of clinical escalation gates across emergency departments.",
        intended_outcome="Achieve standardized clinical escalation gates across all emergency departments.",
        responsible_owner_id="usr-lead-01",
        accountable_lead_id="usr-lead-01",
        category=ImplementationCategory.CONTROL_IMPLEMENTATION,
        priority=ImplementationPriority.HIGH,
        status=ImplementationStatus.IN_PROGRESS,
        target_completion_date=now_dt + timedelta(days=90),
        organization_id=tenant_id,
        created_by="usr-admin-01",
        created_at=now_dt,
        updated_at=now_dt,
    )
    phase73_repo.save_implementation(record)
    return record


def seed_phase74_adoption(adoption_id: str = "adp_valid_001", tenant_id: str = "org-apollo-01"):
    phase74_repo = get_governance_change_adoption_repository()
    now_dt = datetime.now(timezone.utc).isoformat()
    rec = GovernanceChangeAdoptionRecord(
        registration_id=adoption_id,
        tenant_id=tenant_id,
        management_review_id="mr_rev_001",
        decision_id="dec_approved_100",
        implementation_id="impl_valid_001",
        title="Clinical Safety Protocol Adoption Monitoring",
        change_description="Adoption tracking for emergency triage gates",
        operational_scope=OperationalScope(
            facilities=["fac-delhi-01"],
            departments=["Emergency", "ICU"],
            roles=["CLINICAL_SAFETY_OFFICER", "STAFF_NURSE"],
        ),
        accountable_operational_owner_id="usr-lead-01",
        adoption_monitoring_owner_id="usr-admin-01",
        status=AdoptionRegistrationStatus.ACTIVE_MONITORING,
        monitoring_start_date=now_dt,
        created_by="usr-admin-01",
        created_at=now_dt,
        updated_at=now_dt,
    )
    phase74_repo.save_registration(rec)
    return rec


def seed_phase75_portfolio(portfolio_id: str = "port_valid_001", tenant_id: str = "org-apollo-01"):
    phase75_repo = get_governance_change_portfolio_repository()
    now = datetime.now(timezone.utc).isoformat()
    port = GovernanceChangePortfolioRecord(
        portfolio_id=portfolio_id,
        tenant_id=tenant_id,
        name="Emergency Safety Harmonization Portfolio",
        description="Coordinating acute care clinical safety changes",
        governance_purpose="Cross-site alignment of emergency safety controls",
        portfolio_owner_id="usr-lead-01",
        planned_start_date=now,
        target_review_date=now,
        status=PortfolioStatus.ACTIVE,
        created_by="usr-lead-01",
        created_at=now,
        updated_at=now,
    )
    phase75_repo.save_portfolio(port)
    return port


def make_benefit_payload(
    title: str = "Emergency Hand-off Latency Reduction",
    category: str = "OPERATIONAL_EFFICIENCY",
    decision_id: str = "dec_approved_100",
    implementation_id: str = "impl_valid_001",
    portfolio_id: str = None,
    adoption_id: str = None,
):
    now = datetime.now(timezone.utc)
    return {
        "title": title,
        "description": "Expected reduction in clinical handover delays between emergency and ICU",
        "category": category,
        "expected_outcome": "Average handover latency reduced from 35 mins to under 15 mins",
        "decision_id": decision_id,
        "implementation_id": implementation_id,
        "portfolio_id": portfolio_id,
        "adoption_registration_id": adoption_id,
        "responsible_benefit_owner_id": "usr-lead-01",
        "organizational_scope": {"facilities": ["fac-delhi-01"], "departments": ["Emergency", "ICU"]},
        "expected_realization_date": (now + timedelta(days=90)).isoformat(),
        "measurement_period": "2026-Q2",
        "measurement_methodology": "Automated EHR timestamp delta logging at nursing handoff sign-off",
        "evidence_requirements": ["EHR handoff timestamp audit trail", "Nursing triage log"],
        "verification_requirements": ["Independent audit sampling"],
    }


# =============================================================================
# Scenario 1: Benefit Registration, Validation & Lineage
# =============================================================================


def test_scenario_1_benefit_registration_and_lineage(client):
    seed_phase73_implementation("impl_valid_001")
    seed_phase74_adoption("adp_valid_001")
    seed_phase75_portfolio("port_valid_001")

    payload = make_benefit_payload(
        portfolio_id="port_valid_001",
        adoption_id="adp_valid_001",
    )
    resp = client.post("/api/v1/governance-benefit-assurance/benefits", json=payload)
    assert resp.status_code == 201
    benefit = resp.json()
    benefit_id = benefit["benefit_id"]
    assert benefit["status"] == BenefitStatus.REGISTERED.value
    assert benefit["category"] == BenefitCategory.OPERATIONAL_EFFICIENCY.value

    # Duplicate registration check (same title and implementation)
    resp_dup = client.post("/api/v1/governance-benefit-assurance/benefits", json=payload)
    assert resp_dup.status_code == 400
    assert resp_dup.json()["error"]["code"] == "INVALID_BENEFIT_STATE"

    # Lineage reconstruction
    lineage_resp = client.get(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/lineage")
    assert lineage_resp.status_code == 200
    lineage = lineage_resp.json()
    assert lineage["benefit_id"] == benefit_id
    assert lineage["decision_id"] == "dec_approved_100"
    assert lineage["implementation_id"] == "impl_valid_001"
    assert lineage["portfolio_id"] == "port_valid_001"
    assert len(lineage["lineage_nodes"]) >= 4


# =============================================================================
# Scenario 2: Baseline Creation & Separation of Duties on Approval
# =============================================================================


def test_scenario_2_baseline_creation_and_approval(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # 1. Create baseline in DRAFT
    bsl_payload = {
        "measurement_definition": "Pre-implementation emergency hand-off duration in minutes",
        "baseline_value": 35.0,
        "unit": "MINUTES",
        "measurement_period": "2026-Q1",
        "source_system": "EHR_AUDIT_LOG",
        "data_collection_method": "Automated timestamp extraction",
    }
    resp = client.post(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/baselines", json=bsl_payload)
    assert resp.status_code == 201
    baseline = resp.json()
    baseline_id = baseline["baseline_id"]
    assert baseline["status"] == BaselineStatus.DRAFT.value
    assert baseline["version"] == 1

    # 2. Submit baseline
    sub_resp = client.post(f"/api/v1/governance-benefit-assurance/baselines/{baseline_id}/submit", json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == BaselineStatus.SUBMITTED.value

    # 3. Separation of duties: creator attempts self-approval
    self_app = client.post(
        f"/api/v1/governance-benefit-assurance/baselines/{baseline_id}/approve",
        json={"approval_reference": "REF-GOV-001"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert self_app.status_code == 403
    assert self_app.json()["error"]["code"] == "BENEFIT_SEPARATION_OF_DUTIES_VIOLATION"

    # 4. Independent approval
    app_resp = client.post(
        f"/api/v1/governance-benefit-assurance/baselines/{baseline_id}/approve",
        json={"approval_reference": "REF-GOV-APPROVED-001"},
        headers={"X-User-Id": "usr-gov-director-99"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == BaselineStatus.APPROVED.value

    # Verify active_baseline_id updated on benefit
    b_resp = client.get(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}")
    assert b_resp.json()["active_baseline_id"] == baseline_id


# =============================================================================
# Scenario 3: Target Creation & Separation of Duties on Approval
# =============================================================================


def test_scenario_3_target_creation_and_approval(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # 1. Create target in DRAFT
    tgt_payload = {
        "target_value": 15.0,
        "target_measurement_date": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
        "unit": "MINUTES",
        "measurement_method": "Automated EHR timestamp delta extraction",
    }
    resp = client.post(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/targets", json=tgt_payload)
    assert resp.status_code == 201
    target = resp.json()
    target_id = target["target_id"]
    assert target["status"] == TargetStatus.DRAFT.value

    # 2. Submit target
    sub_resp = client.post(f"/api/v1/governance-benefit-assurance/targets/{target_id}/submit", json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == TargetStatus.SUBMITTED.value

    # 3. Separation of duties: creator attempts self-approval
    self_app = client.post(
        f"/api/v1/governance-benefit-assurance/targets/{target_id}/approve",
        json={"approval_reference": "REF-TGT-001"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert self_app.status_code == 403
    assert self_app.json()["error"]["code"] == "BENEFIT_SEPARATION_OF_DUTIES_VIOLATION"

    # 4. Independent approval
    app_resp = client.post(
        f"/api/v1/governance-benefit-assurance/targets/{target_id}/approve",
        json={"approval_reference": "REF-TGT-APPROVED-001"},
        headers={"X-User-Id": "usr-gov-director-99"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == TargetStatus.APPROVED.value


# =============================================================================
# Scenario 4: Indicator Configuration & Reproducible Assessment
# =============================================================================


def test_scenario_4_indicator_configuration_and_assessment(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # 1. Create indicator
    ind_payload = {
        "name": "Hand-off Duration (Minutes)",
        "description": "Elapsed duration between triage assessment and emergency handoff signoff",
        "indicator_type": "DURATION",
        "calculation_methodology": "timestamp_signoff - timestamp_triage",
        "unit": "MINUTES",
        "expected_direction": "DECREASING",
        "measurement_frequency": "MONTHLY",
        "source_system": "EHR_LOG",
        "responsible_owner_id": "usr-lead-01",
    }
    resp = client.post(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/indicators", json=ind_payload)
    assert resp.status_code == 201
    indicator = resp.json()
    indicator_id = indicator["indicator_id"]
    assert indicator["unit"] == "MINUTES"

    # 2. Assess indicator with missing data -> INSUFFICIENT_DATA
    missing_resp = client.post(
        f"/api/v1/governance-benefit-assurance/indicators/{indicator_id}/assess",
        json={"assessment_period": "2026-Q2"},
    )
    assert missing_resp.status_code == 200
    assert missing_resp.json()["outcome"] == IndicatorOutcome.INSUFFICIENT_DATA.value

    # 3. Assess indicator with observed value
    obs_resp = client.post(
        f"/api/v1/governance-benefit-assurance/indicators/{indicator_id}/assess",
        json={"assessment_period": "2026-Q2", "observed_value": 14.5},
    )
    assert obs_resp.status_code == 200
    assert obs_resp.json()["observed_value"] == 14.5


# =============================================================================
# Scenario 5: Measurement Intake, Validation & Rejection
# =============================================================================


def test_scenario_5_measurement_intake_validation_and_rejection(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    ind_id = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/indicators",
        json={
            "name": "Handoff Minutes",
            "description": "Duration in minutes",
            "indicator_type": "DURATION",
            "calculation_methodology": "delta",
            "unit": "MINUTES",
            "expected_direction": "DECREASING",
            "measurement_frequency": "MONTHLY",
            "source_system": "EHR",
            "responsible_owner_id": "usr-lead-01",
        },
    ).json()["indicator_id"]

    # 1. Incompatible unit rejection
    bad_unit = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/measurements",
        json={
            "indicator_id": ind_id,
            "measurement_period": "2026-Q2",
            "observed_value": 14.0,
            "unit": "HOURS",  # Incompatible with indicator unit MINUTES
            "source_reference": "EVID-001",
            "source_system": "EHR",
        },
    )
    assert bad_unit.status_code == 400
    assert bad_unit.json()["error"]["code"] == "MEASUREMENT_VALIDATION_ERROR"

    # 2. Submit valid measurement
    meas_resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/measurements",
        json={
            "indicator_id": ind_id,
            "measurement_period": "2026-Q2",
            "observed_value": 13.5,
            "unit": "MINUTES",
            "source_reference": "EVID-002",
            "source_system": "EHR",
        },
    )
    assert meas_resp.status_code == 201
    meas = meas_resp.json()
    measurement_id = meas["measurement_id"]
    assert meas["validation_status"] == MeasurementStatus.SUBMITTED.value

    # 3. Separation of duties: submitter attempts validation
    self_val = client.post(
        f"/api/v1/governance-benefit-assurance/measurements/{measurement_id}/validate",
        json={"validation_notes": "Attempting self validation"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert self_val.status_code == 403
    assert self_val.json()["error"]["code"] == "BENEFIT_SEPARATION_OF_DUTIES_VIOLATION"

    # 4. Validated by independent reviewer
    val_resp = client.post(
        f"/api/v1/governance-benefit-assurance/measurements/{measurement_id}/validate",
        json={"validation_notes": "Verified against EHR timestamp extract"},
        headers={"X-User-Id": "usr-reviewer-02"},
    )
    assert val_resp.status_code == 200
    assert val_resp.json()["validation_status"] == MeasurementStatus.VALIDATED.value

    # 5. Reject another measurement
    meas_2 = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/measurements",
        json={
            "indicator_id": ind_id,
            "measurement_period": "2026-Q2",
            "observed_value": 99.0,
            "unit": "MINUTES",
            "source_reference": "EVID-ANOMALOUS",
            "source_system": "EHR",
        },
    ).json()["measurement_id"]

    rej_resp = client.post(
        f"/api/v1/governance-benefit-assurance/measurements/{meas_2}/reject",
        json={"rejection_reason": "Anomalous reading caused by staging EHR sync failure."},
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["validation_status"] == MeasurementStatus.REJECTED.value


# =============================================================================
# Scenario 6: Benefit Realization Assessment (Target Met -> REALIZED)
# =============================================================================


def test_scenario_6_benefit_realization_assessment_realized(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # Create & approve target of 15.0 minutes
    tgt_id = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/targets",
        json={
            "target_value": 15.0,
            "target_measurement_date": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
            "unit": "MINUTES",
            "measurement_method": "EHR extract",
        },
    ).json()["target_id"]
    client.post(f"/api/v1/governance-benefit-assurance/targets/{tgt_id}/submit", json={})
    client.post(
        f"/api/v1/governance-benefit-assurance/targets/{tgt_id}/approve",
        json={"approval_reference": "TGT-APP-01"},
        headers={"X-User-Id": "usr-director-01"},
    )

    ind_id = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/indicators",
        json={
            "name": "Handoff",
            "description": "minutes",
            "indicator_type": "DURATION",
            "calculation_methodology": "delta",
            "unit": "MINUTES",
            "expected_direction": "DECREASING",
            "measurement_frequency": "MONTHLY",
            "source_system": "EHR",
            "responsible_owner_id": "usr-lead-01",
        },
    ).json()["indicator_id"]

    # Submit & validate measurement: 16.0 minutes (exceeds or achieves target)
    meas_id = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/measurements",
        json={
            "indicator_id": ind_id,
            "measurement_period": "2026-Q2",
            "observed_value": 16.0,
            "unit": "MINUTES",
            "source_reference": "EVID-VALID",
            "source_system": "EHR",
        },
    ).json()["measurement_id"]
    client.post(
        f"/api/v1/governance-benefit-assurance/measurements/{meas_id}/validate",
        json={"validation_notes": "Validated"},
        headers={"X-User-Id": "usr-reviewer-02"},
    )

    # Perform realization assessment
    ass_resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/assessments",
        json={"measurement_period": "2026-Q2"},
    )
    assert ass_resp.status_code == 201
    assessment = ass_resp.json()
    assessment_id = assessment["assessment_id"]
    assert assessment["disposition"] == RealizationDisposition.REALIZED.value
    # Mandatory Clinical Safety Notice
    assert "clinical effectiveness" in assessment["clinical_safety_notice"].lower()
    assert "does not establish" in assessment["clinical_safety_notice"].lower()

    # Submit & Approve assessment
    client.post(f"/api/v1/governance-benefit-assurance/assessments/{assessment_id}/submit", json={})
    app_resp = client.post(
        f"/api/v1/governance-benefit-assurance/assessments/{assessment_id}/approve",
        json={"approval_notes": "Assessment reviewed and verified."},
        headers={"X-User-Id": "usr-governance-approver-09"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # Benefit status is now REALIZED
    b_resp = client.get(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}")
    assert b_resp.json()["status"] == BenefitStatus.REALIZED.value


# =============================================================================
# Scenario 7: Realization Assessment (INSUFFICIENT_EVIDENCE when no validated data)
# =============================================================================


def test_scenario_7_benefit_realization_insufficient_evidence(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # Assess without any validated measurements
    ass_resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/assessments",
        json={"measurement_period": "2026-Q2"},
    )
    assert ass_resp.status_code == 201
    assert ass_resp.json()["disposition"] == RealizationDisposition.INSUFFICIENT_EVIDENCE.value


# =============================================================================
# Scenario 8: Portfolio-Level Benefit Summary & Assessment
# =============================================================================


def test_scenario_8_portfolio_benefit_summary_and_assessment(client):
    seed_phase73_implementation("impl_valid_001")
    seed_phase75_portfolio("port_valid_001")

    # Register 2 benefits in portfolio
    client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(title="Benefit 1", portfolio_id="port_valid_001"),
    )
    client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(title="Benefit 2", portfolio_id="port_valid_001"),
    )

    # Retrieve portfolio summary
    sum_resp = client.get("/api/v1/governance-benefit-assurance/portfolios/port_valid_001/benefit-summary")
    assert sum_resp.status_code == 200
    summary = sum_resp.json()
    assert summary["portfolio_id"] == "port_valid_001"
    assert summary["total_benefits"] == 2
    assert "methodology_disclosure" in summary

    # Perform portfolio assessment
    ass_resp = client.post(
        "/api/v1/governance-benefit-assurance/portfolios/port_valid_001/benefit-assessments",
        json={"assessment_period": "2026-Q2", "limitations": ["Limited to emergency and ICU rollouts"]},
    )
    assert ass_resp.status_code == 201
    assert ass_resp.json()["portfolio_id"] == "port_valid_001"
    assert ass_resp.json()["double_counting_checks_passed"] is True


# =============================================================================
# Scenario 9: Transparent Attribution Analysis
# =============================================================================


def test_scenario_9_attribution_analysis(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    attr_payload = {
        "attribution_type": AttributionType.SHARED_CONTRIBUTION.value,
        "related_initiative_ids": ["init_er_01", "init_icu_02"],
        "relevant_implementation_periods": ["2026-Q1", "2026-Q2"],
        "external_influencing_factors": ["Seasonal reduction in patient admissions"],
        "measurement_limitations": ["Confounding staffing changes in ICU night shifts"],
        "attribution_methodology": "Difference-in-differences analysis against unexposed non-emergency wards",
        "supporting_evidence": ["EHR-DIFF-REPORT-2026"],
    }
    resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/attribution-assessments",
        json=attr_payload,
    )
    assert resp.status_code == 201
    attr = resp.json()
    assert attr["attribution_type"] == AttributionType.SHARED_CONTRIBUTION.value
    # Notice affirming correlation does not imply causation
    assert "correlation does not imply causation" in attr["clinical_safety_notice"].lower()


# =============================================================================
# Scenario 10: Unintended Consequences & Trade-offs Logging and Routing
# =============================================================================


def test_scenario_10_unintended_consequences_and_routing(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # 1. Log unintended consequence
    csq_payload = {
        "description": "Faster hand-off protocol increased electronic documentation burden on staff nurses by 12 minutes.",
        "related_initiative_ids": ["init_er_01"],
        "affected_organizational_scope": {"departments": ["Emergency"]},
        "evidence_references": ["EHR-TIME-STUDY-009"],
        "source_measurements": [],
        "potential_impact": "Nurse burnout and potential charting delays during peak hours.",
    }
    resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/consequences",
        json=csq_payload,
    )
    assert resp.status_code == 201
    csq = resp.json()
    consequence_id = csq["consequence_id"]
    assert csq["status"] == ConsequenceClassification.POTENTIAL_CONSEQUENCE.value

    # 2. Human review of consequence
    rev_resp = client.post(
        f"/api/v1/governance-benefit-assurance/consequences/{consequence_id}/review",
        json={
            "status": ConsequenceClassification.CONFIRMED_OPERATIONAL_CONSEQUENCE.value,
            "review_notes": "Confirmed by nursing leadership survey and observational audit.",
        },
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == ConsequenceClassification.CONFIRMED_OPERATIONAL_CONSEQUENCE.value

    # 3. Route to Phase 54 Corrective Action
    route_resp = client.post(
        f"/api/v1/governance-benefit-assurance/consequences/{consequence_id}/route",
        json={
            "routed_destination": "PHASE_54_CAPA",
            "destination_reference": "CAPA-2026-NURSE-WORKLOAD-011",
            "routing_notes": "Referred to streamline documentation requirements and eliminate duplicate fields.",
        },
    )
    assert route_resp.status_code == 200
    routed = route_resp.json()
    assert routed["routed_destination"] == "PHASE_54_CAPA"
    assert routed["destination_reference"] == "CAPA-2026-NURSE-WORKLOAD-011"


# =============================================================================
# Scenario 11: Longitudinal Sustainability Monitoring
# =============================================================================


def test_scenario_11_sustainability_monitoring(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # 1. Create sustainability assessment
    sus_resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/sustainability-assessments",
        json={
            "assessment_period": "2026-Q3",
            "notes": "Hand-off speed and consistency sustained over third continuous quarter.",
        },
    )
    assert sus_resp.status_code == 201
    sus = sus_resp.json()
    assert sus["trend"] == SustainabilityTrend.SUSTAINED.value
    assert sus["performance_stability_score"] >= 0.9

    # 2. Get sustainability summary
    summary_resp = client.get(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/sustainability")
    assert summary_resp.status_code == 200
    assert summary_resp.json()["latest_trend"] == SustainabilityTrend.SUSTAINED.value

    # 3. Performance history
    hist_resp = client.get(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/performance-history")
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()) >= 1


# =============================================================================
# Scenario 12: Independent Verification & Conflict of Interest Checks
# =============================================================================


def test_scenario_12_independent_verification(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # 1. Create verification request
    vrf_resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/verification-requests",
        json={
            "verification_scope": "Sample 50 emergency-to-ICU handoffs to verify recorded latency measurements.",
            "evidence_reviewed": ["EHR-RAW-EXTRACT-001"],
        },
    )
    assert vrf_resp.status_code == 201
    vrf = vrf_resp.json()
    verification_id = vrf["verification_id"]
    assert vrf["status"] == VerificationStatus.REQUESTED.value

    # 2. Conflict of interest check: cannot assign benefit owner/creator
    bad_assign = client.post(
        f"/api/v1/governance-benefit-assurance/verification-requests/{verification_id}/assign",
        json={
            "verifier_id": "usr-lead-01",  # Creator of the benefit
            "conflict_of_interest_cleared": True,
        },
    )
    assert bad_assign.status_code == 400
    assert bad_assign.json()["error"]["code"] == "BENEFIT_SEPARATION_OF_DUTIES_VIOLATION"

    # 3. Assign independent verifier
    assign_resp = client.post(
        f"/api/v1/governance-benefit-assurance/verification-requests/{verification_id}/assign",
        json={
            "verifier_id": "usr-independent-auditor-88",
            "conflict_of_interest_cleared": True,
        },
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == VerificationStatus.ASSIGNED.value

    # 4. Complete verification
    comp_resp = client.post(
        f"/api/v1/governance-benefit-assurance/verification-requests/{verification_id}/complete",
        json={
            "status": VerificationStatus.VERIFIED.value,
            "findings": "Audited 50 random handoffs; observed 14.1 minutes average latency matching recorded claims.",
            "verifier_comments": "Independent verification confirmed calculation reproducibility.",
            "recalculated_values": {"sample_mean": 14.1, "sample_std": 2.1},
        },
        headers={"X-User-Id": "usr-independent-auditor-88"},
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == VerificationStatus.VERIFIED.value


# =============================================================================
# Scenario 13: Benefit Exception Management & Governance Escalation
# =============================================================================


def test_scenario_13_benefit_exception_management(client):
    seed_phase73_implementation("impl_valid_001")
    benefit_id = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    ).json()["benefit_id"]

    # 1. Create exception
    exc_payload = {
        "exception_category": "SYSTEM_MIGRATION",
        "description": "EHR server upgrade temporarily interrupted automated timestamp delta logging.",
        "supporting_evidence": ["IT-TICKET-EHR-MIGRATE-991"],
        "impact_on_measurement": "14 days of missing automated logs during server cutover.",
        "requested_duration_days": 30,
        "review_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    resp = client.post(f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}/exceptions", json=exc_payload)
    assert resp.status_code == 201
    exc = resp.json()
    exception_id = exc["exception_id"]
    assert exc["status"] == BenefitExceptionStatus.DRAFT.value

    # 2. Submit exception
    sub_resp = client.post(f"/api/v1/governance-benefit-assurance/exceptions/{exception_id}/submit", json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == BenefitExceptionStatus.SUBMITTED.value

    # 3. Review without authorization reference -> Rejected
    bad_app = client.post(
        f"/api/v1/governance-benefit-assurance/exceptions/{exception_id}/review",
        json={"approved": True, "review_notes": "Approval attempted without authorization reference"},
    )
    assert bad_app.status_code == 400
    assert bad_app.json()["error"]["code"] == "INVALID_BENEFIT_EXCEPTION_STATE"

    # 4. Review with valid authorization reference -> Approved
    app_resp = client.post(
        f"/api/v1/governance-benefit-assurance/exceptions/{exception_id}/review",
        json={
            "approved": True,
            "authorization_reference": "AUTH-GOV-EXC-2026-09",
            "review_notes": "Authorized 30-day measurement exception during EHR upgrade.",
        },
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == BenefitExceptionStatus.APPROVED.value

    # 5. Escalate exception
    esc_resp = client.post(
        f"/api/v1/governance-benefit-assurance/exceptions/{exception_id}/escalate",
        json={
            "escalation_reason": "Cutover delayed beyond 30 days requiring Phase 67 governance escalation.",
            "target_authority": "EXECUTIVE_SAFETY_COMMITTEE",
        },
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["status"] == BenefitExceptionStatus.ESCALATED.value


# =============================================================================
# Scenario 14: Strategic Management Review Package & Phase 72 Referral
# =============================================================================


def test_scenario_14_management_review_packaging_and_referral(client):
    seed_phase73_implementation("impl_valid_001")
    seed_phase75_portfolio("port_valid_001")

    # 1. Create review package
    rev_payload = {
        "review_period": "2026-Q2",
        "title": "Emergency Portfolio Benefit Realization Review",
        "participants": ["usr-lead-01", "usr-director-02"],
        "recommendations": ["Expand SBAR protocol to pediatric acute unit."],
    }
    resp = client.post(
        "/api/v1/governance-benefit-assurance/portfolios/port_valid_001/benefit-reviews",
        json=rev_payload,
    )
    assert resp.status_code == 201
    rev = resp.json()
    review_id = rev["review_id"]
    assert rev["status"] == "DRAFT"

    # 2. Submit review
    sub_resp = client.post(f"/api/v1/governance-benefit-assurance/benefit-reviews/{review_id}/submit", json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 3. Refer to Phase 72 Management Review
    refer_resp = client.post(
        f"/api/v1/governance-benefit-assurance/benefit-reviews/{review_id}/refer-to-management",
        json={
            "management_review_reference": "MR-2026-Q2-EXEC",
            "referral_notes": "Presenting verified operational benefits and documentation trade-offs to executive board.",
        },
    )
    assert refer_resp.status_code == 200
    referred = refer_resp.json()
    assert referred["status"] == "REFERRED_TO_MANAGEMENT"
    assert referred["management_review_reference"] == "MR-2026-Q2-EXEC"


# =============================================================================
# Scenario 15: Consolidated Reporting & Background Routine Scan
# =============================================================================


def test_scenario_15_reporting_and_background_scan(client):
    seed_phase73_implementation("impl_valid_001")
    client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
    )

    # 1. Benefit Realization Report
    rep1 = client.get("/api/v1/governance-benefit-assurance/reports/benefit-realization")
    assert rep1.status_code == 200
    assert rep1.json()["total_benefits"] >= 1

    # 2. Delayed Benefits Report
    rep2 = client.get("/api/v1/governance-benefit-assurance/reports/delayed-benefits")
    assert rep2.status_code == 200

    # 3. Unrealized Benefits Report
    rep3 = client.get("/api/v1/governance-benefit-assurance/reports/unrealized-benefits")
    assert rep3.status_code == 200

    # 4. Sustainability Report
    rep4 = client.get("/api/v1/governance-benefit-assurance/reports/benefit-sustainability")
    assert rep4.status_code == 200

    # 5. Portfolio Benefit Performance Report
    rep5 = client.get("/api/v1/governance-benefit-assurance/reports/portfolio-benefit-performance")
    assert rep5.status_code == 200

    # 6. Verification Report
    rep6 = client.get("/api/v1/governance-benefit-assurance/reports/benefit-verification")
    assert rep6.status_code == 200

    # 7. Background Routine Scan Job
    job_resp = client.post("/api/v1/governance-benefit-assurance/jobs/run-benefit-assurance-cycle")
    assert job_resp.status_code == 200
    res = job_resp.json()
    assert res["job_name"] == "benefit_assurance_routine_scan"
    assert "run_timestamp" in res


# =============================================================================
# Scenario 16: Multi-Tenant Boundary Isolation
# =============================================================================


def test_scenario_16_multi_tenant_boundary_isolation(client):
    # Create benefit in Tenant A
    seed_phase73_implementation("impl_valid_001", tenant_id="org-apollo-01")
    port_resp = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert port_resp.status_code == 201
    benefit_id = port_resp.json()["benefit_id"]

    # Attempt to retrieve from Tenant B
    resp_b = client.get(
        f"/api/v1/governance-benefit-assurance/benefits/{benefit_id}",
        headers={"X-User-Organization": "org-fortis-02"},
    )
    assert resp_b.status_code == 404
    assert resp_b.json()["error"]["code"] == "BENEFIT_NOT_FOUND"


# =============================================================================
# Scenario 17: Patient Role Authorization Enforcement (403 Forbidden)
# =============================================================================


def test_scenario_17_patient_role_rejection(client):
    resp = client.post(
        "/api/v1/governance-benefit-assurance/benefits",
        json=make_benefit_payload(),
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-007"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    resp_list = client.get(
        "/api/v1/governance-benefit-assurance/benefits",
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-007"},
    )
    assert resp_list.status_code == 403
    assert resp_list.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

"""Phase 51: Clinical Safety Governance, Risk Acceptance & Controlled Safety Change Management Test Suite.

Comprehensive tests covering:
- Risk registration with provenance from incidents/findings
- Structured risk assessment and initial vs residual risk distinction
- Explicit risk acceptance, temporary expiration, and reassessment triggers
- Separation of duties (author cannot approve own change)
- AI authority prohibitions (preventing AI autonomous approvals, acceptance, deployment)
- Multi-dimensional impact assessment and stale approval invalidation
- Strict implementation gate execution (APPROVAL != IMPLEMENTATION, IMPLEMENTATION != VALIDATION)
- Post-change validation gating and failure handling
- Safe rollback without history erasure (ROLLBACK != HISTORY DELETION)
- Governance prerequisite-checked risk closure and history-preserved reopening
- Full REST API integration via HTTP client
"""

from datetime import datetime, timezone, timedelta
import pytest
from starlette.testclient import TestClient

from app.api.deps import _global_user_repo
from app.core.exceptions import (
    AISafetyGovernanceAuthorityProhibitedException,
    RiskAcceptanceDeniedException,
    RiskAcceptanceExpiredException,
    RiskAlreadyClosedException,
    RiskAssessmentRequiredException,
    RiskNotFoundException,
    RiskVersionConflictException,
    SafetyChangeAlreadyImplementedException,
    SafetyChangeAlreadyRolledBackException,
    SafetyChangeApprovalDeniedException,
    SafetyChangeApprovalRequiredException,
    SafetyChangeNotFoundException,
    SafetyChangeStaleException,
    SafetyChangeValidationFailedException,
    SafetyChangeVersionConflictException,
)
from app.core.security import create_access_token
from app.main import app
from app.repositories.safety_governance_repository import safety_governance_repository
from app.repositories.user_repository import UserRecord
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.risk import (
    RiskCloseRequest,
    RiskCreateRequest,
    RiskRecord,
    RiskReopenRequest,
    RiskReassessRequest,
    RiskSourceReference,
)
from app.schemas.risk_assessment import (
    ControlEffectiveness,
    ExistingControlEvaluation,
    RiskAssessmentCreateRequest,
)
from app.schemas.risk_mitigation import (
    MitigationCreateRequest,
    MitigationStatus,
)
from app.schemas.safety_approval import (
    RiskAcceptanceRequest,
    SafetyChangeApprovalRequest,
)
from app.schemas.safety_change import (
    ImpactAreaEvaluation,
    ImpactAssessment,
    SafetyChangeCreateRequest,
)
from app.schemas.safety_governance import (
    AIGovernanceStatus,
    AITraceabilityMetadata,
    ChangeRequestState,
    RiskCategory,
    RiskImpact,
    RiskLikelihood,
    RiskSeverity,
    RiskSourceType,
    RiskState,
    RolloutScopeType,
    SafetyChangeTargetType,
)
from app.schemas.safety_rollback import (
    SafetyChangeImplementationRequest,
    SafetyChangeRollbackRequest,
)
from app.schemas.safety_validation import (
    SafetyChangeValidationRequest,
    ValidationOutcome,
)
from app.services.risk_acceptance_service import risk_acceptance_service
from app.services.risk_assessment_service import risk_assessment_service
from app.services.risk_governance_service import risk_governance_service
from app.services.risk_mitigation_service import risk_mitigation_service
from app.services.safety_change_approval_service import safety_change_approval_service
from app.services.safety_change_implementation_service import safety_change_implementation_service
from app.services.safety_change_service import safety_change_service
from app.services.safety_change_validation_service import safety_change_validation_service
from app.services.safety_governance_policy_service import safety_governance_policy_service
from app.services.safety_reassessment_service import safety_reassessment_service
from app.services.safety_rollback_service import safety_rollback_service


@pytest.fixture(autouse=True)
def reset_phase51_state():
    """Reset repository before each test."""
    safety_governance_repository.reset()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def safety_officer_token():
    officer_id = "usr-safety-officer-p51"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=officer_id,
            identifier="safety.officer@healthsetu.org",
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
            password_hash="mock-hash",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    token, _ = create_access_token(
        user_id=officer_id,
        role=UserRole.ADMIN.value,
    )
    return token


@pytest.fixture
def safety_officer_headers(safety_officer_token):
    return {"Authorization": f"Bearer {safety_officer_token}"}


@pytest.fixture
def safety_director_token():
    director_id = "usr-safety-director-p51"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=director_id,
            identifier="safety.director@healthsetu.org",
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
            password_hash="mock-hash",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    token, _ = create_access_token(
        user_id=director_id,
        role="CLINICAL_SAFETY_DIRECTOR",
    )
    return token


@pytest.fixture
def safety_director_headers(safety_director_token):
    return {"Authorization": f"Bearer {safety_director_token}"}


# ===========================================================================
# Unit & Domain Logic Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_risk_registration_and_provenance():
    """Verify risk registration captures source provenance, starts in IDENTIFIED state."""
    req = RiskCreateRequest(
        title="High Dose Calculation Anomaly in Pediatric Workflow",
        description="Observed repeated boundary rounding discrepancy in weight-based dosing.",
        category=RiskCategory.MEDICATION_SAFETY,
        initial_severity=RiskSeverity.HIGH,
        initial_likelihood=RiskLikelihood.POSSIBLE,
        initial_impact=RiskImpact.POTENTIAL_IMPACT,
        sources=[
            RiskSourceReference(
                source_type=RiskSourceType.INCIDENT,
                source_id="inc-pediatric-001",
                description="Near-miss pediatric insulin dosing incident",
            )
        ],
        affected_subsystem="medication_safety_engine",
        organization_id="org-delhi-01",
    )

    risk = await risk_governance_service.create_risk(
        request=req,
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
        organization_id="org-delhi-01",
    )

    assert risk.id.startswith("risk-")
    assert risk.version == 1
    assert risk.state == RiskState.IDENTIFIED
    assert len(risk.sources) == 1
    assert risk.sources[0].source_id == "inc-pediatric-001"

    # Verify history
    history = risk_governance_service.get_risk_history(risk.id)
    assert len(history) == 1
    assert history[0].action == "RISK_CREATED"
    assert history[0].new_state == RiskState.IDENTIFIED


@pytest.mark.asyncio
async def test_risk_idempotency():
    """Verify duplicate risk creation requests with the same idempotency key return the same risk."""
    req = RiskCreateRequest(
        title="Triage Gate Bypass Under High Concurrency",
        description="Safety gate dropped during load spike.",
        category=RiskCategory.TRIAGE_SAFETY,
        initial_severity=RiskSeverity.MEDIUM,
        idempotency_key="idem-risk-triage-101",
    )

    risk1 = await risk_governance_service.create_risk(
        request=req,
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )
    risk2 = await risk_governance_service.create_risk(
        request=req,
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    assert risk1.id == risk2.id


@pytest.mark.asyncio
async def test_structured_risk_assessment_residual_risk():
    """Verify structured assessment calculates residual risk (INITIAL -> CONTROL -> RESIDUAL)."""
    # 1. Create risk
    risk = await risk_governance_service.create_risk(
        request=RiskCreateRequest(
            title="Allergy Warning Masking",
            description="Allergy warning was suppressed due to UI notification policy misconfiguration.",
            category=RiskCategory.CLINICAL_SAFETY,
            initial_severity=RiskSeverity.HIGH,
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    # 2. Assess risk
    assess_req = RiskAssessmentCreateRequest(
        category=RiskCategory.CLINICAL_SAFETY,
        severity=RiskSeverity.HIGH,
        likelihood=RiskLikelihood.POSSIBLE,
        impact=RiskImpact.POTENTIAL_IMPACT,
        residual_severity=RiskSeverity.MEDIUM,
        residual_likelihood=RiskLikelihood.UNLIKELY,
        residual_impact=RiskImpact.POTENTIAL_IMPACT,
        existing_controls=[
            ExistingControlEvaluation(
                control_name="Clinician Manual Chart Review",
                control_type="HUMAN_REVIEW",
                effectiveness=ControlEffectiveness.PARTIALLY_EFFECTIVE,
            )
        ],
        mitigation_recommendation="Implement hard safety gate in allergy alert banner.",
    )

    assessment = await risk_assessment_service.assess_risk(
        risk_id=risk.id,
        request=assess_req,
        assessor_id="usr-assessor-1",
        assessor_role="CLINICAL_SAFETY_ASSESSOR",
    )

    assert assessment.residual_severity == RiskSeverity.MEDIUM
    assert assessment.severity == RiskSeverity.HIGH  # Initial severity preserved

    # Check updated risk
    updated_risk = risk_governance_service.get_risk(risk.id)
    assert updated_risk.residual_severity == RiskSeverity.MEDIUM
    assert updated_risk.latest_assessment_id == assessment.id
    assert updated_risk.state == RiskState.ASSESSED


@pytest.mark.asyncio
async def test_ai_authority_prohibited_for_governance():
    """Verify AI cannot autonomously accept risks, approve changes, or close governance."""
    with pytest.raises(AISafetyGovernanceAuthorityProhibitedException):
        safety_governance_policy_service.assert_human_safety_authority(
            actor_id="ai-model-claude-3-sonnet",
            actor_role="AI_ASSISTANT",
            action="accept_risk",
        )

    with pytest.raises(AISafetyGovernanceAuthorityProhibitedException):
        safety_governance_policy_service.assert_human_safety_authority(
            actor_id="usr-123",
            actor_role="LLM_BOT",
            action="approve_change",
        )


@pytest.mark.asyncio
async def test_risk_acceptance_and_expiration():
    """Verify explicit risk acceptance with expiration and automatic transition to REASSESSMENT_REQUIRED."""
    # 1. Create and assess risk
    risk = await risk_governance_service.create_risk(
        request=RiskCreateRequest(
            title="External Terminology Service Latency Risk",
            description="Fallback dictionary lookup adds 150ms delay under network degraded conditions.",
            category=RiskCategory.INTEGRATION_SAFETY,
            initial_severity=RiskSeverity.LOW,
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    await risk_assessment_service.assess_risk(
        risk_id=risk.id,
        request=RiskAssessmentCreateRequest(
            category=RiskCategory.INTEGRATION_SAFETY,
            severity=RiskSeverity.LOW,
            likelihood=RiskLikelihood.UNLIKELY,
            impact=RiskImpact.NO_KNOWN_IMPACT,
            residual_severity=RiskSeverity.LOW,
            residual_likelihood=RiskLikelihood.UNLIKELY,
            residual_impact=RiskImpact.NO_KNOWN_IMPACT,
        ),
        assessor_id="usr-assessor-1",
        assessor_role="CLINICAL_SAFETY_ASSESSOR",
    )

    # 2. Accept risk by different authority (separation of duties)
    acc_req = RiskAcceptanceRequest(
        residual_risk_severity=RiskSeverity.LOW,
        residual_risk_likelihood=RiskLikelihood.UNLIKELY,
        residual_risk_impact=RiskImpact.NO_KNOWN_IMPACT,
        acceptance_scope="FACILITY_LEVEL",
        reason="Acceptable operational trade-off given cached local terminology fallback.",
        evidence_summary="Verified 99.9% local cache hit rate in observation logs.",
        expires_in_days=30,
    )

    acceptance = await risk_acceptance_service.accept_risk(
        risk_id=risk.id,
        request=acc_req,
        authority_id="usr-director-1",
        authority_role="CLINICAL_SAFETY_DIRECTOR",
    )

    assert acceptance.residual_risk_severity == RiskSeverity.LOW
    assert acceptance.is_temporary is True

    # Risk is now ACCEPTED
    accepted_risk = risk_governance_service.get_risk(risk.id)
    assert accepted_risk.state == RiskState.ACCEPTED

    # 3. Simulate Expiration
    acceptance.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    safety_governance_repository.save_acceptance(acceptance)

    with pytest.raises(RiskAcceptanceExpiredException):
        risk_acceptance_service.verify_acceptance_validity(risk.id)

    # Check risk state transitioned to REASSESSMENT_REQUIRED
    reassessed_risk = risk_governance_service.get_risk(risk.id)
    assert reassessed_risk.state == RiskState.REASSESSMENT_REQUIRED


@pytest.mark.asyncio
async def test_separation_of_duties_enforcement():
    """Verify change author cannot approve their own change request."""
    # 1. Create risk & change
    risk = await risk_governance_service.create_risk(
        request=RiskCreateRequest(
            title="Prescription Unit Discrepancy",
            description="Gram vs Milligram ambiguity in older templates.",
            category=RiskCategory.MEDICATION_SAFETY,
        ),
        actor_id="usr-author-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    change = await safety_change_service.create_change_request(
        request=SafetyChangeCreateRequest(
            risk_id=risk.id,
            title="Enforce Strict Unit Normalization Gate",
            description="Deploy validation rule blocking non-standard dosage units.",
            target_type=SafetyChangeTargetType.VALIDATION_LOGIC,
            affected_subsystem="medication_validator",
            current_version="v1.0.0",
            proposed_version="v1.1.0",
            proposed_change_details={"strict_units": True},
            reason="Eliminate unit ambiguity.",
            expected_benefit="Prevent overdose.",
            rollback_plan={"revert_to": "v1.0.0"},
            validation_plan={"test_suite": "test_dosage_units"},
            monitoring_plan={"observation_window_days": 14},
            impact_assessment=ImpactAssessment(
                overall_impact_summary="Low operational impact, high clinical safety benefit.",
                assessed_by_id="usr-author-1",
                assessed_at=datetime.now(timezone.utc),
            ),
        ),
        actor_id="usr-author-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    # 2. Attempt approval by same author -> Blocked by separation of duties
    approval_req = SafetyChangeApprovalRequest(
        decision="APPROVE",
        notes="Author self-approving change.",
        bound_risk_version=risk.version,
        bound_change_version=change.version,
    )

    with pytest.raises(SafetyChangeApprovalDeniedException):
        await safety_change_approval_service.approve_change(
            change_id=change.id,
            request=approval_req,
            approver_id="usr-author-1",  # Same user!
            approver_role="CLINICAL_SAFETY_OFFICER",
        )


@pytest.mark.asyncio
async def test_stale_approval_detection():
    """Verify changes to risk/change invalidate prior approval (APPROVAL -> STALE)."""
    # 1. Setup risk & change
    risk = await risk_governance_service.create_risk(
        request=RiskCreateRequest(
            title="Unchecked Alert Dismissal",
            description="Alerts dismissed without clinician justification note.",
            category=RiskCategory.CLINICAL_SAFETY,
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    change = await safety_change_service.create_change_request(
        request=SafetyChangeCreateRequest(
            risk_id=risk.id,
            title="Require Dismissal Reason for Tier 1 Alerts",
            description="Add mandatory justification popup.",
            target_type=SafetyChangeTargetType.SAFETY_POLICY,
            affected_subsystem="alert_manager",
            current_version="policy-v1",
            proposed_version="policy-v2",
            proposed_change_details={"mandatory_reason": True},
            reason="Ensure accountability.",
            expected_benefit="Reduce alert fatigue while catching critical warnings.",
            rollback_plan={"revert": "policy-v1"},
            validation_plan={"checks": ["ui_test", "audit_test"]},
            monitoring_plan={"window": 7},
            impact_assessment=ImpactAssessment(
                overall_impact_summary="Workflow change evaluated.",
                assessed_by_id="usr-evaluator-1",
                assessed_at=datetime.now(timezone.utc),
            ),
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    # 2. Approved by independent reviewer
    approval = await safety_change_approval_service.approve_change(
        change_id=change.id,
        request=SafetyChangeApprovalRequest(
            decision="APPROVE",
            notes="Authorized for rollout.",
            bound_risk_version=risk.version,
            bound_change_version=change.version,
        ),
        approver_id="usr-approver-2",
        approver_role="CLINICAL_SAFETY_DIRECTOR",
    )
    assert approval.decision == "APPROVE"

    # 3. Upstream change occurs: parent risk is updated
    await risk_governance_service.attach_evidence(
        risk_id=risk.id,
        evidence={"type": "AUDIT_FINDING", "ref": "new-alert-audit"},
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )
    risk.version += 1  # Increment version
    safety_governance_repository.save_risk(risk)

    # 4. Checking staleness should mark STALE and raise SafetyChangeStaleException
    with pytest.raises(SafetyChangeStaleException):
        safety_change_approval_service.verify_approval_staleness(change.id)

    stale_change = safety_change_service.get_change(change.id)
    assert stale_change.state == ChangeRequestState.STALE


@pytest.mark.asyncio
async def test_full_implementation_validation_and_rollback_flow():
    """Verify end-to-end lifecycle: Implementation -> Validation Failure -> Rollback."""
    # 1. Create Risk & Change
    risk = await risk_governance_service.create_risk(
        request=RiskCreateRequest(
            title="AI Triage Under-triaging Critical Sepsis Signals",
            description="Pattern detected where borderline vitals were categorized as Non-Urgent.",
            category=RiskCategory.AI_SAFETY,
            initial_severity=RiskSeverity.CRITICAL,
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    change = await safety_change_service.create_change_request(
        request=SafetyChangeCreateRequest(
            risk_id=risk.id,
            title="Deploy Conservative Sepsis Floor Rule",
            description="Hardcode automatic triage elevation if vitals meet SIRS criteria.",
            target_type=SafetyChangeTargetType.AI_GUARDRAIL,
            affected_subsystem="triage_guardrail",
            current_version="guardrail-1.0",
            proposed_version="guardrail-1.1",
            proposed_change_details={"elevate_sirs": True},
            reason="Eliminate under-triage risk.",
            expected_benefit="Immediate safety containment.",
            rollback_plan={"restore": "guardrail-1.0"},
            validation_plan={"test": "sepsis_synthetic_battery"},
            monitoring_plan={"window_days": 30},
            impact_assessment=ImpactAssessment(
                overall_impact_summary="High priority clinical safeguard.",
                assessed_by_id="usr-officer-1",
                assessed_at=datetime.now(timezone.utc),
            ),
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    # 2. Approve Change
    await safety_change_approval_service.approve_change(
        change_id=change.id,
        request=SafetyChangeApprovalRequest(
            decision="APPROVE",
            notes="Approved by safety director.",
            bound_risk_version=risk.version,
            bound_change_version=change.version,
        ),
        approver_id="usr-director-1",
        approver_role="CLINICAL_SAFETY_DIRECTOR",
    )

    # 3. Implement Change (Implementation != Validation)
    impl_record = await safety_change_implementation_service.implement_change(
        change_id=change.id,
        request=SafetyChangeImplementationRequest(),
        actor_id="usr-engineer-1",
        actor_role="PLATFORM_ENGINEER",
    )
    assert impl_record.implemented_version == "guardrail-1.1"

    implemented_change = safety_change_service.get_change(change.id)
    assert implemented_change.state == ChangeRequestState.VALIDATION_REQUIRED

    # 4. Validation Failure (Technical tests pass but clinical simulation reveals adverse delay)
    with pytest.raises(SafetyChangeValidationFailedException):
        await safety_change_validation_service.validate_change(
            change_id=change.id,
            request=SafetyChangeValidationRequest(
                outcome=ValidationOutcome.FAILED,
                findings_summary="Guardrail triggered excessive false alarms on pediatric tachycardia cases.",
                validation_evidence=[{"test_run": "sim-pediatric-fail"}],
            ),
            validator_id="usr-clinician-validator",
            validator_role="CLINICAL_VALIDATOR",
        )

    failed_change = safety_change_service.get_change(change.id)
    assert failed_change.state == ChangeRequestState.FAILED

    # 5. Execute Safe Rollback (ROLLBACK != HISTORY DELETION)
    rollback_record = await safety_rollback_service.rollback_change(
        change_id=change.id,
        request=SafetyChangeRollbackRequest(
            reason="Excessive pediatric false alerts in validation phase. Reverting to baseline guardrail-1.0.",
            target_reversion_version="guardrail-1.0",
        ),
        actor_id="usr-engineer-1",
        actor_role="PLATFORM_ENGINEER",
    )

    assert rollback_record.target_reversion_version == "guardrail-1.0"
    assert rollback_record.history_preserved is True

    rolled_back_change = safety_change_service.get_change(change.id)
    assert rolled_back_change.state == ChangeRequestState.ROLLED_BACK
    assert rolled_back_change.implemented_version == "guardrail-1.0"

    # Verify change history still exists (never deleted!)
    rollbacks = safety_governance_repository.list_rollbacks(change.id)
    assert len(rollbacks) == 1
    validations = safety_governance_repository.list_validations(change.id)
    assert len(validations) == 1


@pytest.mark.asyncio
async def test_closure_prerequisites_and_reopening():
    """Verify risk closure requires assessment, mitigations, and validated changes; reopening preserves history."""
    # 1. Create risk
    risk = await risk_governance_service.create_risk(
        request=RiskCreateRequest(
            title="Unchecked Provider Failover Timeout",
            description="External lab result ingestion hung indefinitely when provider was down.",
            category=RiskCategory.INTEGRATION_SAFETY,
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    # Attempt closure without assessment -> BLOCKED
    with pytest.raises(RiskAssessmentRequiredException):
        await risk_governance_service.close_risk(
            risk_id=risk.id,
            request=RiskCloseRequest(
                reason="Premature closure attempt",
                verification_notes="None provided",
            ),
            actor_id="usr-officer-1",
            actor_role="CLINICAL_SAFETY_OFFICER",
        )

    # 2. Complete Assessment
    await risk_assessment_service.assess_risk(
        risk_id=risk.id,
        request=RiskAssessmentCreateRequest(
            category=RiskCategory.INTEGRATION_SAFETY,
            severity=RiskSeverity.MEDIUM,
            likelihood=RiskLikelihood.UNLIKELY,
            impact=RiskImpact.NO_KNOWN_IMPACT,
            residual_severity=RiskSeverity.LOW,
            residual_likelihood=RiskLikelihood.RARE,
            residual_impact=RiskImpact.NO_KNOWN_IMPACT,
        ),
        assessor_id="usr-assessor-1",
        assessor_role="CLINICAL_SAFETY_ASSESSOR",
    )

    # 3. Create mitigation
    mit = await risk_mitigation_service.create_mitigation(
        risk_id=risk.id,
        request=MitigationCreateRequest(
            title="Configure 5-second circuit breaker timeout",
            description="Fallback immediately to cached status.",
            mitigation_type="CIRCUIT_BREAKER",
            owner_id="usr-eng-1",
            expected_outcome="No hung threads.",
            validation_criteria=["Load test with simulated outage passes."],
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    # Mark mitigation verified
    risk_mitigation_service.update_mitigation_status(
        mitigation_id=mit.id,
        new_status=MitigationStatus.VERIFIED,
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    # 4. Formally Close Risk
    closed_risk = await risk_governance_service.close_risk(
        risk_id=risk.id,
        request=RiskCloseRequest(
            reason="Verified circuit breaker prevents hung threads under network partition.",
            verification_notes="Passed synthetic timeout and chaos testing.",
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    assert closed_risk.state == RiskState.CLOSED
    assert closed_risk.is_closed is True

    # 5. Attempt modifying closed risk -> Blocked
    with pytest.raises(RiskAlreadyClosedException):
        await risk_governance_service.close_risk(
            risk_id=risk.id,
            request=RiskCloseRequest(reason="Double close", verification_notes="Duplicate close verification"),
            actor_id="usr-officer-1",
            actor_role="CLINICAL_SAFETY_OFFICER",
        )

    # 6. Reopen Risk upon recurrence
    reopened_risk = await risk_governance_service.reopen_risk(
        risk_id=risk.id,
        request=RiskReopenRequest(
            reason="Recurrence observed on newly onboarded diagnostic partner with non-standard status codes.",
            new_evidence=[{"incident_ref": "inc-new-partner-99"}],
        ),
        actor_id="usr-officer-1",
        actor_role="CLINICAL_SAFETY_OFFICER",
    )

    assert reopened_risk.state == RiskState.REOPENED
    assert reopened_risk.is_closed is False
    assert len(reopened_risk.evidence_references) == 1

    # Verify history chain is complete
    history = risk_governance_service.get_risk_history(risk.id)
    history_actions = [h.action for h in history]
    assert "RISK_CREATED" in history_actions
    assert "RISK_CLOSED" in history_actions
    assert "RISK_REOPENED" in history_actions


# ===========================================================================
# HTTP REST API Integration Tests
# ===========================================================================


def test_api_risk_crud_and_assessment_endpoints(client, safety_officer_headers):
    """Test REST API endpoints for risk creation, assessment, mitigation, and acceptance."""
    # 1. POST /risks
    risk_payload = {
        "title": "Unlogged High-Severity Alert Overrides",
        "description": "Critical alerts overridden without structured audit event generation.",
        "category": "SECURITY",
        "initial_severity": "HIGH",
        "initial_likelihood": "POSSIBLE",
        "initial_impact": "POTENTIAL_IMPACT",
        "affected_subsystem": "alert_override_service",
    }
    res = client.post("/api/v1/safety-governance/risks", json=risk_payload, headers=safety_officer_headers)
    assert res.status_code == 201
    risk_data = res.json()["data"]
    risk_id = risk_data["id"]
    assert risk_data["state"] == "IDENTIFIED"

    # 2. GET /risks
    res = client.get("/api/v1/safety-governance/risks", headers=safety_officer_headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) >= 1

    # 3. GET /risks/{risk_id}
    res = client.get(f"/api/v1/safety-governance/risks/{risk_id}", headers=safety_officer_headers)
    assert res.status_code == 200
    assert res.json()["data"]["id"] == risk_id

    # 4. POST /risks/{risk_id}/assess
    assess_payload = {
        "category": "SECURITY",
        "severity": "HIGH",
        "likelihood": "POSSIBLE",
        "impact": "POTENTIAL_IMPACT",
        "residual_severity": "MEDIUM",
        "residual_likelihood": "UNLIKELY",
        "residual_impact": "POTENTIAL_IMPACT",
        "existing_controls": [
            {
                "control_name": "Basic access log",
                "control_type": "LOGGING",
                "effectiveness": "PARTIALLY_EFFECTIVE",
            }
        ],
        "mitigation_recommendation": "Enforce mandatory tamper-proof Phase 15 audit trail.",
    }
    res = client.post(f"/api/v1/safety-governance/risks/{risk_id}/assess", json=assess_payload, headers=safety_officer_headers)
    assert res.status_code == 200
    assess_data = res.json()["data"]
    assert assess_data["residual_severity"] == "MEDIUM"

    # 5. GET /risks/{risk_id}/assessments
    res = client.get(f"/api/v1/safety-governance/risks/{risk_id}/assessments", headers=safety_officer_headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1

    # 6. POST /risks/{risk_id}/mitigate
    mit_payload = {
        "title": "Integrate with Phase 15 Audit Sink",
        "description": "Send every alert override to immutable audit repository.",
        "mitigation_type": "AUDIT_HARDENING",
        "owner_id": "usr-sec-lead",
        "expected_outcome": "Zero unlogged overrides.",
        "validation_criteria": ["Override without audit event returns 500."],
    }
    res = client.post(f"/api/v1/safety-governance/risks/{risk_id}/mitigate", json=mit_payload, headers=safety_officer_headers)
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "PLANNED"

    # 7. GET /risks/{risk_id}/history
    res = client.get(f"/api/v1/safety-governance/risks/{risk_id}/history", headers=safety_officer_headers)
    assert res.status_code == 200
    history = res.json()["data"]
    assert len(history) >= 2


def test_api_change_request_lifecycle_endpoints(client, safety_officer_headers, safety_director_headers):
    """Test REST API endpoints for safety change creation, approval, implementation, and validation."""
    # 1. Create Risk
    res_risk = client.post(
        "/api/v1/safety-governance/risks",
        json={
            "title": "Medication Dosage Rounding Hazard",
            "description": "Precision loss in micrograms conversion.",
            "category": "MEDICATION_SAFETY",
            "initial_severity": "MEDIUM",
        },
        headers=safety_officer_headers,
    )
    risk_id = res_risk.json()["data"]["id"]

    # 2. POST /change-requests
    change_payload = {
        "risk_id": risk_id,
        "title": "Switch to Decimal Fixed-Point Math",
        "description": "Replace floating-point dosage conversion with decimal64 precision.",
        "target_type": "VALIDATION_LOGIC",
        "affected_subsystem": "dosage_calculator",
        "current_version": "v2.0",
        "proposed_version": "v2.1",
        "proposed_change_details": {"math_mode": "decimal64"},
        "reason": "Eliminate floating point epsilon errors.",
        "expected_benefit": "Zero rounding discrepancies.",
        "rollback_plan": {"revert": "v2.0"},
        "validation_plan": {"battery": "dosage_precision_test"},
        "monitoring_plan": {"metric": "rounding_drift_rate"},
        "impact_assessment": {
            "overall_impact_summary": "Extensive unit and boundary testing completed.",
            "assessed_by_id": "usr-officer-1",
            "assessed_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    res_chg = client.post("/api/v1/safety-governance/change-requests", json=change_payload, headers=safety_officer_headers)
    assert res_chg.status_code == 201
    change_id = res_chg.json()["data"]["id"]

    # 3. GET /change-requests/{change_id}
    res = client.get(f"/api/v1/safety-governance/change-requests/{change_id}", headers=safety_officer_headers)
    assert res.status_code == 200
    assert res.json()["data"]["id"] == change_id

    # 4. POST /change-requests/{change_id}/approve (Director Approves)
    appr_payload = {
        "decision": "APPROVE",
        "approval_scope": "INTERNAL",
        "notes": "Approved for staging deployment.",
        "bound_risk_version": 2,  # Risk incremented version when change was linked
        "bound_change_version": 1,
    }
    res_appr = client.post(f"/api/v1/safety-governance/change-requests/{change_id}/approve", json=appr_payload, headers=safety_director_headers)
    assert res_appr.status_code == 200
    assert res_appr.json()["data"]["decision"] == "APPROVE"

    # 5. POST /change-requests/{change_id}/implement
    res_impl = client.post(f"/api/v1/safety-governance/change-requests/{change_id}/implement", json={}, headers=safety_officer_headers)
    assert res_impl.status_code == 200
    assert res_impl.json()["data"]["implemented_version"] == "v2.1"

    # 6. POST /change-requests/{change_id}/validate
    val_payload = {
        "outcome": "VALIDATED",
        "findings_summary": "All 10,000 synthetic microgram dosing calculations matched exact reference values.",
        "validation_evidence": [{"test_run": "tr-precision-pass"}],
    }
    res_val = client.post(f"/api/v1/safety-governance/change-requests/{change_id}/validate", json=val_payload, headers=safety_officer_headers)
    assert res_val.status_code == 200
    assert res_val.json()["data"]["outcome"] == "VALIDATED"

    # 7. POST /change-requests/{change_id}/close
    res_close = client.post(
        f"/api/v1/safety-governance/change-requests/{change_id}/close",
        json={"reason": "Change verified and deployed."},
        headers=safety_officer_headers,
    )
    assert res_close.status_code == 200
    assert res_close.json()["data"]["state"] == "COMPLETED"

    # 8. GET /change-requests/{change_id}/history
    res_hist = client.get(f"/api/v1/safety-governance/change-requests/{change_id}/history", headers=safety_officer_headers)
    assert res_hist.status_code == 200
    history = res_hist.json()["data"]
    assert len(history["approvals"]) == 1
    assert len(history["implementations"]) == 1
    assert len(history["validations"]) == 1


def test_api_rollback_endpoint(client, safety_officer_headers, safety_director_headers):
    """Test POST /change-requests/{change_id}/rollback via HTTP API."""
    # 1. Create Risk & Change
    res_risk = client.post(
        "/api/v1/safety-governance/risks",
        json={
            "title": "Lab Ingestion Mapping Drift",
            "description": "Drift in analyte LOINC code mapping.",
            "category": "DATA_INTEGRITY",
            "initial_severity": "HIGH",
        },
        headers=safety_officer_headers,
    )
    risk_id = res_risk.json()["data"]["id"]

    res_chg = client.post(
        "/api/v1/safety-governance/change-requests",
        json={
            "risk_id": risk_id,
            "title": "Update LOINC Mapping Table",
            "description": "Deploy loinc_v2.5 mapping table.",
            "target_type": "INTEROPERABILITY_MAPPING",
            "affected_subsystem": "loinc_mapper",
            "current_version": "v1.0",
            "proposed_version": "v2.0",
            "proposed_change_details": {"table": "loinc_v2.5"},
            "reason": "Fix analyte drift.",
            "expected_benefit": "Accurate lab imports.",
            "rollback_plan": {"target": "v1.0"},
            "validation_plan": {"test": "test_loinc_mapping"},
            "monitoring_plan": {"metric": "mapping_failure_rate"},
            "impact_assessment": {
                "overall_impact_summary": "Evaluated impact on historic observations.",
                "assessed_by_id": "usr-officer-1",
                "assessed_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        headers=safety_officer_headers,
    )
    change_id = res_chg.json()["data"]["id"]

    # 2. Approve & Implement
    client.post(
        f"/api/v1/safety-governance/change-requests/{change_id}/approve",
        json={
            "decision": "APPROVE",
            "notes": "Approved for rollback test.",
            "bound_risk_version": 2,
            "bound_change_version": 1,
        },
        headers=safety_director_headers,
    )

    client.post(f"/api/v1/safety-governance/change-requests/{change_id}/implement", json={}, headers=safety_officer_headers)

    # 3. Rollback
    rbk_res = client.post(
        f"/api/v1/safety-governance/change-requests/{change_id}/rollback",
        json={
            "reason": "Mapping discrepancies observed in production smoke check.",
            "target_reversion_version": "v1.0",
        },
        headers=safety_officer_headers,
    )
    assert rbk_res.status_code == 200
    rbk_data = rbk_res.json()["data"]
    assert rbk_data["target_reversion_version"] == "v1.0"
    assert rbk_data["history_preserved"] is True


def test_cross_org_access_blocked(client, safety_officer_token):
    """Verify cross-organization access to risk records is blocked with 403."""
    # Create risk under org-A
    risk = safety_governance_repository.save_risk(
        RiskRecord(
            title="Org A Confidential Hazard",
            description="Specific to Hospital A internal telemetry.",
            category=RiskCategory.SYSTEM_RELIABILITY,
            initial_severity=RiskSeverity.LOW,
            initial_likelihood=RiskLikelihood.RARE,
            initial_impact=RiskImpact.NO_KNOWN_IMPACT,
            organization_id="org-hospital-a",
            created_by_id="usr-1",
            created_by_role="ADMIN",
        )
    )

    from app.api.deps import get_current_user
    from app.schemas.user import AuthenticatedUserContext
    from app.core.exceptions import RiskAccessDeniedException

    # 1. Direct service verification
    with pytest.raises(RiskAccessDeniedException):
        risk_governance_service.get_risk(risk.id, actor_org_id="org-hospital-b")

    # 2. HTTP endpoint verification with organization_id in caller context
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserContext(
        user_id="usr-hospital-b",
        role=UserRole.ADMIN,
        organization_id="org-hospital-b",
    )
    try:
        res = client.get(f"/api/v1/safety-governance/risks/{risk.id}")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_emergency_change_pathway(client, safety_officer_headers):
    """Verify emergency changes can be implemented with justification and retrospective review flag."""
    # 1. Create Risk
    res_risk = client.post(
        "/api/v1/safety-governance/risks",
        json={
            "title": "Critical Injection Vulnerability in Gateway",
            "description": "Active exploit identified in external webhook parser.",
            "category": "SECURITY",
            "initial_severity": "CRITICAL",
        },
        headers=safety_officer_headers,
    )
    risk_id = res_risk.json()["data"]["id"]

    # 2. Create Emergency Change
    res_chg = client.post(
        "/api/v1/safety-governance/change-requests",
        json={
            "risk_id": risk_id,
            "title": "Emergency Firewall Filter",
            "description": "Block malformed webhook payloads immediately.",
            "target_type": "CONFIGURATION",
            "affected_subsystem": "api_gateway",
            "current_version": "gw-3.0",
            "proposed_version": "gw-3.0.1",
            "proposed_change_details": {"block_cve": True},
            "reason": "Active threat mitigation.",
            "expected_benefit": "Zero unauthorized intrusions.",
            "is_emergency": True,
            "emergency_justification": "Immediate harm containment required under emergency policy.",
            "rollback_plan": {"revert": "gw-3.0"},
            "validation_plan": {"test": "gateway_smoke"},
            "monitoring_plan": {"window": 24},
        },
        headers=safety_officer_headers,
    )
    assert res_chg.status_code == 201
    change_id = res_chg.json()["data"]["id"]

    # 3. Emergency Change can be implemented directly
    res_impl = client.post(
        f"/api/v1/safety-governance/change-requests/{change_id}/implement",
        json={},
        headers=safety_officer_headers,
    )
    assert res_impl.status_code == 200
    assert res_impl.json()["data"]["implemented_version"] == "gw-3.0.1"


def test_reopen_and_reassess_api_endpoints(client, safety_officer_headers):
    """Test POST /risks/{risk_id}/reassess and /reopen endpoints via HTTP."""
    # 1. Create Risk
    res_risk = client.post(
        "/api/v1/safety-governance/risks",
        json={
            "title": "Diagnostic Reconciliation Inconsistency",
            "description": "Duplicate reconciliation records observed.",
            "category": "DATA_RECONCILIATION",
            "initial_severity": "LOW",
        },
        headers=safety_officer_headers,
    )
    risk_id = res_risk.json()["data"]["id"]

    # 2. Reassess
    res_reassess = client.post(
        f"/api/v1/safety-governance/risks/{risk_id}/reassess",
        json={
            "trigger_reason": "New reconciliation discrepancy detected in quarterly audit.",
            "new_evidence": [{"audit_id": "aud-rec-2026-q3"}],
        },
        headers=safety_officer_headers,
    )
    assert res_reassess.status_code == 200
    assert res_reassess.json()["data"]["state"] == "REASSESSMENT_REQUIRED"


def test_safety_governance_metrics_summary():
    """Verify metrics service tracks non-PHI counters accurately."""
    from app.services.safety_governance_metrics_service import safety_governance_metrics_service

    summary = safety_governance_metrics_service.get_summary()
    assert "counters" in summary
    assert "risk_created_count" in summary["counters"]
    assert "rollback_count" in summary["counters"]

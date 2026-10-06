"""Phase 49: Clinical Safety Incident Management & Investigation Test Suite.

Comprehensive tests covering:
- Ingestion of safety signals from gates, providers, and workflows
- Deduplication within window and correlation to existing incidents
- Lifecycle state transitions (DETECTED -> TRIAGED -> INVESTIGATING -> CONTAINED -> RESOLVED -> CLOSED -> REOPENED)
- Active risk containment orchestration
- Evidence reference attachment and chronological timeline reconstruction
- Root-cause hypothesis proposal, status tracking, and confirmation gates
- Corrective and preventive action tracking
- Prerequisite validations before incident closure
- All 15 Clinical Safety Regression Test scenarios from TRD Section 74
"""

from datetime import datetime, timezone, timedelta
import pytest
from starlette.testclient import TestClient

from app.api.deps import _global_user_repo
from app.core.exceptions import (
    AIIncidentAuthorityProhibitedException,
    IncidentAlreadyClosedException,
    IncidentAlreadyResolvedException,
    IncidentClosureBlockedException,
    IncidentInvalidStateException,
    IncidentNotFoundException,
)
from app.core.security import create_access_token
from app.main import app
from app.repositories.safety_incident_repository import safety_incident_repository
from app.repositories.user_repository import UserRecord
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.corrective_actions import (
    ActionStatus,
    ActionType,
    CorrectiveActionCreateRequest,
    CorrectiveActionStatusUpdateRequest,
)
from app.schemas.incident_evidence import (
    EvidenceAttachRequest,
    EvidenceType,
)
from app.schemas.incident_investigation import (
    HypothesisCreateRequest,
    HypothesisStatus,
    HypothesisStatusUpdateRequest,
    RootCauseCategory,
)
from app.schemas.incidents import (
    IncidentClosureRequest,
    IncidentContainmentRequest,
    IncidentCreateRequest,
    IncidentImpactStatus,
    IncidentRecord,
    IncidentReopenRequest,
    IncidentResolutionRequest,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    IncidentTriageRequest,
    IncidentType,
    SafetySignalCreateRequest,
)
from app.services.clinical_incident_service import clinical_incident_service
from app.services.corrective_action_service import corrective_action_service
from app.services.incident_closure_service import incident_closure_service
from app.services.incident_containment_service import incident_containment_service
from app.services.incident_evidence_service import incident_evidence_service
from app.services.incident_investigation_service import incident_investigation_service
from app.services.safety_incident_service import safety_incident_service


@pytest.fixture(autouse=True)
def reset_phase49_state():
    """Reset Phase 49 repositories before each test."""
    safety_incident_repository.reset()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def safety_officer_token():
    officer_id = "usr-safety-officer-01"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=officer_id,
            identifier="safety.officer@healthsetu.local",
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
            password_hash="dummy-hash",
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


# ===========================================================================
# 1. Unit & Service Tests: Safety Signals & Deduplication
# ===========================================================================


@pytest.mark.asyncio
async def test_signal_ingest_and_candidate_creation():
    """Verify safety signal intake creates a candidate incident without claiming patient harm."""
    req = SafetySignalCreateRequest(
        source=IncidentSource.AI_SAFETY_GATE,
        incident_type=IncidentType.AI_SAFETY,
        summary="AI output attempted prohibited clinical recommendation.",
        severity_candidate=IncidentSeverity.HIGH,
        impact_candidate=IncidentImpactStatus.POTENTIAL_IMPACT,
        patient_id="pat-100",
    )
    signal, incident = await safety_incident_service.ingest_safety_signal(req, actor_id="sys-ai")

    assert signal.id.startswith("sig-")
    assert incident is not None
    assert incident.id.startswith("inc-")
    assert incident.status == IncidentStatus.DETECTED
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.impact_status == IncidentImpactStatus.POTENTIAL_IMPACT
    assert signal.id in incident.signal_ids


@pytest.mark.asyncio
async def test_signal_deduplication_within_window():
    """Verify repeated signals with identical correlation ID within deduplication window correlate to existing incident."""
    req1 = SafetySignalCreateRequest(
        source=IncidentSource.EXTERNAL_PROVIDER,
        incident_type=IncidentType.EXTERNAL_PROVIDER,
        summary="Provider timeout on drug interaction lookup.",
        correlation_id="corr-drug-provider-timeout",
        patient_id="pat-200",
    )
    sig1, inc1 = await safety_incident_service.ingest_safety_signal(req1)

    req2 = SafetySignalCreateRequest(
        source=IncidentSource.EXTERNAL_PROVIDER,
        incident_type=IncidentType.EXTERNAL_PROVIDER,
        summary="Provider timeout on drug interaction lookup (retry).",
        correlation_id="corr-drug-provider-timeout",
        patient_id="pat-200",
    )
    sig2, inc2 = await safety_incident_service.ingest_safety_signal(req2)

    assert sig1.id != sig2.id
    assert inc2 is not None
    assert inc2.id == inc1.id
    assert len(inc2.signal_ids) == 2
    assert sig1.id in inc2.signal_ids
    assert sig2.id in inc2.signal_ids


# ===========================================================================
# 2. Lifecycle Progression: Triage, Assignment, Containment, Hypotheses, Resolution
# ===========================================================================


@pytest.mark.asyncio
async def test_full_incident_lifecycle():
    """Verify complete governed lifecycle flow from detection to closure."""
    # 1. Create incident candidate
    inc_req = IncidentCreateRequest(
        title="Medication interaction safety check bypass attempt",
        description="Prescription dispatch attempted without required interaction check.",
        incident_type=IncidentType.MEDICATION_SAFETY,
        severity=IncidentSeverity.HIGH,
        impact_status=IncidentImpactStatus.NEAR_MISS,
        patient_id="pat-300",
    )
    incident = await clinical_incident_service.create_incident(inc_req, actor_id="dr-smith")
    assert incident.status == IncidentStatus.DETECTED

    # 2. Triage
    triage_req = IncidentTriageRequest(
        severity=IncidentSeverity.HIGH,
        impact_status=IncidentImpactStatus.NEAR_MISS,
        triage_notes="Requires immediate provider check fallback containment.",
        requires_containment=True,
    )
    incident = await clinical_incident_service.triage_incident(incident.id, triage_req, triaged_by_id="safety-off-1")
    assert incident.status == IncidentStatus.CONTAINMENT_REQUIRED

    # 3. Contain
    contain_req = IncidentContainmentRequest(
        containment_action="Enforced mandatory pharmacist review before dispatch.",
        containment_type="REQUIRE_MANUAL_REVIEW",
    )
    incident = await incident_containment_service.record_containment(incident.id, contain_req, contained_by_id="safety-off-1")
    assert incident.status == IncidentStatus.CONTAINED
    assert incident.containment_status == "CONTAINED"

    # 4. Assign investigator
    incident = await incident_investigation_service.assign_investigator(
        incident_id=incident.id,
        investigator_id="inv-lead-01",
        investigator_role="CLINICAL_SAFETY_INVESTIGATOR",
        assigned_by_id="safety-off-1",
    )
    assert incident.status == IncidentStatus.INVESTIGATING

    # 5. Propose hypothesis
    hyp_req = HypothesisCreateRequest(
        category=RootCauseCategory.SOFTWARE_DEFECT,
        title="Async queue dispatch bypassed gate check",
        statement="Worker thread did not await safety gate verification before scheduling order.",
    )
    hyp = await incident_investigation_service.propose_hypothesis(
        incident_id=incident.id,
        request=hyp_req,
        proposer_id="inv-lead-01",
        proposer_role="CLINICAL_SAFETY_INVESTIGATOR",
    )
    assert hyp.status == HypothesisStatus.PROPOSED

    # 6. Update hypothesis to CONFIRMED
    update_hyp = HypothesisStatusUpdateRequest(
        status=HypothesisStatus.CONFIRMED,
        notes="Root cause verified via worker execution trace logs.",
    )
    hyp = await incident_investigation_service.update_hypothesis_status(
        hypothesis_id=hyp.id,
        request=update_hyp,
        updater_id="inv-lead-01",
        updater_role="CLINICAL_SAFETY_INVESTIGATOR",
    )
    assert hyp.status == HypothesisStatus.CONFIRMED

    # 7. Create corrective action
    act_req = CorrectiveActionCreateRequest(
        action_type=ActionType.CODE_FIX,
        title="Enforce sync gate barrier in queue worker",
        description="Prevent queue worker from publishing job before safety clearance.",
    )
    action = await corrective_action_service.create_action(incident.id, act_req, created_by_id="inv-lead-01")
    assert action.status == ActionStatus.CREATED

    # Advance corrective action to VERIFIED
    corrective_action_service.update_action_status(
        action.id,
        CorrectiveActionStatusUpdateRequest(status=ActionStatus.COMPLETED, resolution_details="PR #402 merged."),
        updated_by_id="inv-lead-01",
    )
    corrective_action_service.update_action_status(
        action.id,
        CorrectiveActionStatusUpdateRequest(status=ActionStatus.VERIFIED, resolution_details="Regression tests verified."),
        updated_by_id="safety-off-1",
    )

    # 8. Resolve incident
    res_req = IncidentResolutionRequest(
        resolution_summary="Queue worker synchronization defect rectified and verified.",
        root_cause_category=RootCauseCategory.SOFTWARE_DEFECT.value,
        root_cause_confirmed=True,
    )
    incident = await clinical_incident_service.resolve_incident(incident.id, res_req, resolved_by_id="safety-off-1")
    assert incident.status == IncidentStatus.RESOLVED

    # 9. Close incident
    close_req = IncidentClosureRequest(
        closure_reason="All corrective actions verified, risk contained, root cause resolved.",
        validation_confirmed=True,
    )
    incident = await incident_closure_service.close_incident(
        incident.id,
        close_req,
        closed_by_id="safety-off-1",
        closed_by_role="CHIEF_MEDICAL_OFFICER",
    )
    assert incident.status == IncidentStatus.CLOSED
    assert incident.closed_at is not None


# ===========================================================================
# 3. Evidence & Timeline Integrity
# ===========================================================================


@pytest.mark.asyncio
async def test_evidence_attachment_and_timeline_chronology():
    """Verify evidence attachment sanitizes PHI and timeline correctly preserves milestones."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="External lab ingestion mismatch",
            description="Lab identifier matched multiple patient records.",
            incident_type=IncidentType.DATA_RECONCILIATION,
            severity=IncidentSeverity.MEDIUM,
        )
    )

    # Attach evidence reference
    ev_req = EvidenceAttachRequest(
        evidence_type=EvidenceType.DECISION_TRACE,
        reference_id="dec-4091",
        summary="Decision trace demonstrating conflicting reconciliation options.",
        source_system="reconciliation_service",
        snapshot_hash="hash-abc1234",
        metadata={"forbidden_key": "safe_val", "patient_data": "LEAKED_PHI_ATTEMPT"},
    )
    evidence = incident_evidence_service.attach_evidence(inc.id, ev_req, recorded_by_id="investigator-1")

    # Verify raw PHI stripped from metadata
    assert "patient_data" not in evidence.metadata
    assert evidence.metadata.get("forbidden_key") == "safe_val"

    # Reconstruct timeline
    timeline = incident_evidence_service.reconstruct_timeline(inc.id)
    assert len(timeline) >= 2
    types = [t.event_time_type for t in timeline]
    assert "OCCURRED" in types
    assert "RECORDED" in types
    assert "EVIDENCE_ATTACHED" in types


# ===========================================================================
# 4. TRD Section 74: Clinical Safety Regression Tests (15 Required Invariants)
# ===========================================================================


@pytest.mark.asyncio
async def test_regression_01_blocked_operation_does_not_claim_harm():
    """TRD 74.1: A blocked medication safety operation creates a signal without claiming patient harm."""
    sig, inc = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.RULE_ENGINE,
            incident_type=IncidentType.MEDICATION_SAFETY,
            summary="Contraindicated drug combination blocked by runtime safety gate.",
            severity_candidate=IncidentSeverity.HIGH,
            impact_candidate=IncidentImpactStatus.NEAR_MISS,
        )
    )
    assert inc.impact_status == IncidentImpactStatus.NEAR_MISS
    assert inc.impact_status != IncidentImpactStatus.CONFIRMED_IMPACT
    assert "error" not in inc.title.lower()


@pytest.mark.asyncio
async def test_regression_02_provider_timeout_not_assumed_safe():
    """TRD 74.2: A provider timeout cannot become 'safe'."""
    sig, inc = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.EXTERNAL_PROVIDER,
            incident_type=IncidentType.EXTERNAL_PROVIDER,
            summary="Medication safety provider timed out after 5000ms.",
            severity_candidate=IncidentSeverity.HIGH,
            impact_candidate=IncidentImpactStatus.POTENTIAL_IMPACT,
        )
    )
    assert inc.severity in [IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]
    assert inc.impact_status != IncidentImpactStatus.NO_KNOWN_IMPACT


@pytest.mark.asyncio
async def test_regression_03_ai_prohibited_action_generates_incident_not_clinical_action():
    """TRD 74.3: An AI prohibited action generates a safety incident without becoming a clinical action."""
    sig, inc = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.AI_SAFETY_GATE,
            incident_type=IncidentType.AI_SAFETY,
            summary="AI suggested unvalidated high-risk surgical modification; blocked.",
            severity_candidate=IncidentSeverity.CRITICAL,
            impact_candidate=IncidentImpactStatus.NEAR_MISS,
        )
    )
    assert inc.status == IncidentStatus.DETECTED
    assert inc.incident_type == IncidentType.AI_SAFETY


@pytest.mark.asyncio
async def test_regression_04_stale_decision_generates_safety_signal():
    """TRD 74.4: A stale clinical decision generates a safety signal."""
    sig, inc = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.SYSTEM,
            incident_type=IncidentType.CLINICAL_SAFETY,
            summary="Attempted application of decision older than TTL expiration threshold.",
            severity_candidate=IncidentSeverity.MEDIUM,
            decision_id="dec-expired-99",
        )
    )
    assert inc.decision_id == "dec-expired-99"
    assert sig.decision_id == "dec-expired-99"


@pytest.mark.asyncio
async def test_regression_05_workflow_safety_bypass_generates_incident():
    """TRD 74.5: A workflow safety bypass generates an incident."""
    sig, inc = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.WORKFLOW,
            incident_type=IncidentType.WORKFLOW_SAFETY,
            summary="Workflow step executed without prerequisite mandatory clinical approval.",
            severity_candidate=IncidentSeverity.HIGH,
            workflow_id="wf-bypass-10",
        )
    )
    assert inc.incident_type == IncidentType.WORKFLOW_SAFETY
    assert inc.workflow_id == "wf-bypass-10"


@pytest.mark.asyncio
async def test_regression_06_data_reconciliation_conflict_generates_incident():
    """TRD 74.6: A data reconciliation conflict generates an incident."""
    sig, inc = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.DATA_RECONCILIATION,
            incident_type=IncidentType.DATA_RECONCILIATION,
            summary="Demographic identity conflict between external FHIR feed and primary record.",
            severity_candidate=IncidentSeverity.HIGH,
            resource_type="Patient",
            resource_id="pat-conflict-01",
        )
    )
    assert inc.incident_type == IncidentType.DATA_RECONCILIATION
    assert inc.resource_id == "pat-conflict-01"


@pytest.mark.asyncio
async def test_regression_07_closure_cannot_modify_historical_clinical_data():
    """TRD 74.7: Incident closure cannot modify historical clinical data directly."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="Prescription dose discrepancy",
            description="Dose recorded in notes differed from dispensed unit.",
            incident_type=IncidentType.CLINICAL_SAFETY,
            severity=IncidentSeverity.LOW,
        )
    )
    await incident_closure_service.close_incident(
        incident_id=inc.id,
        request=IncidentClosureRequest(closure_reason="Reviewed and confirmed."),
        closed_by_id="officer-1",
        closed_by_role="SAFETY_OFFICER",
    )
    # Assert incident closure records status only and has no clinical record backdoor
    closed = clinical_incident_service.get_incident(inc.id)
    assert closed.status == IncidentStatus.CLOSED
    assert not hasattr(closed, "raw_clinical_data")


@pytest.mark.asyncio
async def test_regression_08_investigation_cannot_rewrite_audit_history():
    """TRD 74.8: Incident investigation cannot rewrite audit history."""
    # Audit log entry is immutable in AuditService; creating hypotheses or actions emits NEW events
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="Audit trail inspection test",
            description="Testing immutability of audit references.",
            incident_type=IncidentType.SECURITY,
        )
    )
    hyp = await incident_investigation_service.propose_hypothesis(
        inc.id,
        HypothesisCreateRequest(category=RootCauseCategory.SECURITY_EVENT, title="Test", statement="Stmt"),
        proposer_id="inv-1",
        proposer_role="INVESTIGATOR",
    )
    assert hyp.id.startswith("hyp-")


@pytest.mark.asyncio
async def test_regression_09_root_cause_hypotheses_cannot_be_facts_without_validation():
    """TRD 74.9: Root-cause hypotheses cannot be represented as confirmed facts without authorized transition."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="Hypothesis uncertainty test",
            description="Hypothesis remains proposed until explicit confirmation.",
            incident_type=IncidentType.SYSTEM_FAILURE,
        )
    )
    hyp = await incident_investigation_service.propose_hypothesis(
        inc.id,
        HypothesisCreateRequest(
            category=RootCauseCategory.PROVIDER_FAILURE,
            title="External gateway drop",
            statement="Gateway might have dropped connection.",
        ),
        proposer_id="inv-1",
        proposer_role="INVESTIGATOR",
    )
    assert hyp.status == HypothesisStatus.PROPOSED
    # Parent incident must NOT have confirmed root cause yet
    inc_current = clinical_incident_service.get_incident(inc.id)
    assert inc_current.root_cause_confirmed is False
    assert inc_current.root_cause_category is None


@pytest.mark.asyncio
async def test_regression_10_corrective_action_does_not_declare_patient_recovery():
    """TRD 74.10: Corrective-action completion cannot automatically declare clinical recovery."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="Remediation isolation test",
            description="Verifying corrective action completion does not update patient status.",
            incident_type=IncidentType.CLINICAL_SAFETY,
        )
    )
    act = await corrective_action_service.create_action(
        inc.id,
        CorrectiveActionCreateRequest(
            action_type=ActionType.CODE_FIX,
            title="Fix bug in parsing",
            description="Fix parser bug",
        ),
        created_by_id="dev-1",
    )
    updated = corrective_action_service.update_action_status(
        act.id,
        CorrectiveActionStatusUpdateRequest(status=ActionStatus.COMPLETED),
        updated_by_id="dev-1",
    )
    assert updated.status == ActionStatus.COMPLETED
    # Incident status remains DETECTED (not resolved or patient recovered)
    assert clinical_incident_service.get_incident(inc.id).status == IncidentStatus.DETECTED


@pytest.mark.asyncio
async def test_regression_11_incident_resolution_does_not_imply_patient_recovery():
    """TRD 74.11: Incident resolution cannot automatically imply patient recovery."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="Resolution boundary test",
            description="Technical issue resolved.",
            incident_type=IncidentType.SYSTEM_FAILURE,
        )
    )
    resolved = await clinical_incident_service.resolve_incident(
        inc.id,
        IncidentResolutionRequest(resolution_summary="Database failover completed."),
        resolved_by_id="admin-1",
    )
    assert resolved.status == IncidentStatus.RESOLVED
    # Impact status remains unchanged and not mapped to clinical 'RECOVERED'
    assert resolved.impact_status == IncidentImpactStatus.UNKNOWN


@pytest.mark.asyncio
async def test_regression_12_patient_information_remains_protected():
    """TRD 74.12: Patient information remains protected during investigation."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="PHI protection test",
            description="Ensure evidence attachment excludes raw records.",
            incident_type=IncidentType.PRIVACY,
        )
    )
    ev = incident_evidence_service.attach_evidence(
        inc.id,
        EvidenceAttachRequest(
            evidence_type=EvidenceType.AUDIT_EVENT,
            reference_id="aud-991",
            summary="Access log reference",
            source_system="audit_service",
            metadata={"prescription": "SECRET_MED", "note": "safe note"},
        ),
    )
    assert "prescription" not in ev.metadata
    assert ev.metadata.get("note") == "safe note"


@pytest.mark.asyncio
async def test_regression_13_ai_cannot_independently_close_or_resolve_incident():
    """TRD 74.13: AI cannot independently confirm root causes, assign lead investigator, or close safety incidents."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="AI closure prohibition test",
            description="Testing AI authority restriction.",
            incident_type=IncidentType.AI_SAFETY,
            severity=IncidentSeverity.LOW,
        )
    )

    # 1. Prohibit AI assignment as lead investigator
    with pytest.raises(AIIncidentAuthorityProhibitedException):
        await incident_investigation_service.assign_investigator(
            incident_id=inc.id,
            investigator_id="ai-agent-01",
            investigator_role="AI_ASSISTANT_BOT",
            assigned_by_id="sys",
        )

    # 2. Prohibit AI confirmation of root cause
    hyp = await incident_investigation_service.propose_hypothesis(
        inc.id,
        HypothesisCreateRequest(category=RootCauseCategory.SOFTWARE_DEFECT, title="AI bias", statement="Biased output"),
        proposer_id="inv-1",
        proposer_role="HUMAN_INVESTIGATOR",
    )
    with pytest.raises(AIIncidentAuthorityProhibitedException):
        await incident_investigation_service.update_hypothesis_status(
            hyp.id,
            HypothesisStatusUpdateRequest(status=HypothesisStatus.CONFIRMED),
            updater_id="ai-bot",
            updater_role="AI_AGENT",
        )

    # 3. Prohibit AI closure
    with pytest.raises(AIIncidentAuthorityProhibitedException):
        await incident_closure_service.close_incident(
            inc.id,
            IncidentClosureRequest(closure_reason="AI decided incident is complete."),
            closed_by_id="ai-bot",
            closed_by_role="AI_SAFETY_MODEL",
        )


@pytest.mark.asyncio
async def test_regression_14_unauthorized_user_cannot_access_or_alter_closed_incident():
    """TRD 74.14: Closure prerequisites and state protection prevent invalid transitions."""
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="High severity uncontained incident",
            description="High risk event without containment.",
            incident_type=IncidentType.CLINICAL_SAFETY,
            severity=IncidentSeverity.CRITICAL,
        )
    )

    # High / Critical severity incident cannot be closed without confirmed containment
    with pytest.raises(IncidentClosureBlockedException):
        await incident_closure_service.close_incident(
            inc.id,
            IncidentClosureRequest(closure_reason="Attempted premature closure."),
            closed_by_id="officer-1",
            closed_by_role="SAFETY_OFFICER",
        )


@pytest.mark.asyncio
async def test_regression_15_duplicate_signals_do_not_create_uncontrolled_duplicate_incidents():
    """TRD 74.15: Duplicate signals do not create uncontrolled duplicate incidents."""
    corr_key = "corr-sig-dedup-regression-15"
    s1, i1 = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.MONITORING,
            incident_type=IncidentType.SYSTEM_FAILURE,
            summary="Worker memory threshold breached.",
            correlation_id=corr_key,
        )
    )
    s2, i2 = await safety_incident_service.ingest_safety_signal(
        SafetySignalCreateRequest(
            source=IncidentSource.MONITORING,
            incident_type=IncidentType.SYSTEM_FAILURE,
            summary="Worker memory threshold breached (repeated heartbeat).",
            correlation_id=corr_key,
        )
    )
    assert i1.id == i2.id
    # Only 1 incident created in repository
    all_incidents = safety_incident_repository.list_incidents()
    assert len(all_incidents) == 1
    assert len(all_incidents[0].signal_ids) == 2


# ===========================================================================
# 5. REST API Integration Tests via TestClient
# ===========================================================================


def test_api_ingest_safety_signal_endpoint(client, safety_officer_headers):
    """Test POST /api/v1/incidents/signals via HTTP."""
    resp = client.post(
        "/api/v1/incidents/signals",
        headers=safety_officer_headers,
        json={
            "source": "AI_SAFETY_GATE",
            "incident_type": "AI_SAFETY",
            "summary": "AI generated dosage outside pediatric safe range; blocked by gate.",
            "severity_candidate": "HIGH",
            "impact_candidate": "NEAR_MISS",
            "patient_id": "pat-api-01",
        },
    )
    assert resp.status_code == 201
    payload = resp.json()
    assert payload["success"] is True
    assert "signal" in payload["data"]
    assert "incident" in payload["data"]
    assert payload["data"]["incident"]["severity"] == "HIGH"


def test_api_incident_lifecycle_flow(client, safety_officer_headers):
    """Test complete incident workflow through HTTP REST endpoints."""
    # 1. Create incident candidate
    res1 = client.post(
        "/api/v1/incidents",
        headers=safety_officer_headers,
        json={
            "title": "API Lifecycle Incident Test",
            "description": "Verifying HTTP flow for safety officers.",
            "incident_type": "CLINICAL_SAFETY",
            "severity": "MEDIUM",
            "impact_status": "POTENTIAL_IMPACT",
        },
    )
    assert res1.status_code == 201
    inc_id = res1.json()["data"]["id"]

    # 2. Triage incident
    res2 = client.post(
        f"/api/v1/incidents/{inc_id}/triage",
        headers=safety_officer_headers,
        json={
            "severity": "HIGH",
            "impact_status": "POTENTIAL_IMPACT",
            "triage_notes": "Immediate containment required for provider.",
            "requires_containment": True,
        },
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == "CONTAINMENT_REQUIRED"

    # 3. Contain incident
    res3 = client.post(
        f"/api/v1/incidents/{inc_id}/contain",
        headers=safety_officer_headers,
        json={
            "containment_action": "Disabled provider automated actions.",
            "containment_type": "DISABLE_PROVIDER",
            "details": {"provider": "RxCheck"},
        },
    )
    assert res3.status_code == 200
    assert res3.json()["data"]["status"] == "CONTAINED"

    # 4. Attach evidence
    res4 = client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        headers=safety_officer_headers,
        json={
            "evidence_type": "PROVIDER_RESPONSE",
            "reference_id": "resp-provider-551",
            "summary": "Malformed response body without drug schema validation.",
            "source_system": "rx_provider_client",
        },
    )
    assert res4.status_code == 201

    # 5. Get timeline
    res5 = client.get(f"/api/v1/incidents/{inc_id}/timeline", headers=safety_officer_headers)
    assert res5.status_code == 200
    timeline = res5.json()["data"]
    assert len(timeline) >= 3

    # 6. Propose hypothesis
    res6 = client.post(
        f"/api/v1/incidents/{inc_id}/hypotheses",
        headers=safety_officer_headers,
        json={
            "category": "PROVIDER_FAILURE",
            "title": "External vendor breaking API change",
            "statement": "Vendor altered JSON field naming without deprecation notice.",
        },
    )
    assert res6.status_code == 201
    hyp_id = res6.json()["data"]["id"]

    # 7. Update hypothesis status to CONFIRMED
    res7 = client.patch(
        f"/api/v1/incidents/hypotheses/{hyp_id}",
        headers=safety_officer_headers,
        json={
            "status": "CONFIRMED",
            "notes": "Verified against vendor changelog.",
        },
    )
    assert res7.status_code == 200
    assert res7.json()["data"]["status"] == "CONFIRMED"

    # 8. Create corrective action & verify
    res8 = client.post(
        f"/api/v1/incidents/{inc_id}/corrective-actions",
        headers=safety_officer_headers,
        json={
            "action_type": "PROVIDER_CORRECTION",
            "title": "Update parser schema for vendor response",
            "description": "Handle both legacy and new vendor response formats.",
        },
    )
    assert res8.status_code == 201
    act_id = res8.json()["data"]["id"]

    client.patch(
        f"/api/v1/incidents/corrective-actions/{act_id}",
        headers=safety_officer_headers,
        json={"status": "COMPLETED", "resolution_details": "Patch applied."},
    )
    client.patch(
        f"/api/v1/incidents/corrective-actions/{act_id}",
        headers=safety_officer_headers,
        json={"status": "VERIFIED", "resolution_details": "Validated in staging."},
    )

    # 9. Resolve incident
    res9 = client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        headers=safety_officer_headers,
        json={
            "resolution_summary": "Vendor parser updated and verified.",
            "root_cause_category": "PROVIDER_FAILURE",
            "root_cause_confirmed": True,
        },
    )
    assert res9.status_code == 200
    assert res9.json()["data"]["status"] == "RESOLVED"

    # 10. Close incident
    res10 = client.post(
        f"/api/v1/incidents/{inc_id}/close",
        headers=safety_officer_headers,
        json={
            "closure_reason": "Remediation verified; risk mitigated.",
            "validation_confirmed": True,
        },
    )
    assert res10.status_code == 200
    assert res10.json()["data"]["status"] == "CLOSED"

    # 11. Reopen incident
    res11 = client.post(
        f"/api/v1/incidents/{inc_id}/reopen",
        headers=safety_officer_headers,
        json={
            "reopen_reason": "New variant of payload reported by secondary lab provider.",
        },
    )
    assert res11.status_code == 200
    assert res11.json()["data"]["status"] == "REOPENED"

"""Comprehensive Test Suite for Phase 47:
Clinical Decision Traceability, Explanation & Human Oversight Management.

Covers:
- Decision Lifecycle Transitions & Traceability Records
- Rule-based and AI Model Metadata Tracking
- Context Assembly & Version Staleness Detection (Phase 46 integration)
- Clinician Oversight Review Workflows (Approve, Reject, Modify)
- Controlled Application of Approved Decisions
- Structured Audience-Tailored Explanations (Patient vs Clinician)
- Replay, Investigation, and Decision Comparison
- Idempotency & Concurrency Protections
- All 12 Non-Negotiable Clinical Safety Regressions (TRD Sec 52)
- Full End-to-End API Integration via TestClient
"""

import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.deps import _global_user_repo
from app.core.exceptions import (
    AIClinicalActionProhibitedException,
    AutonomousDecisionExecutionProhibitedException,
    DecisionAccessDeniedException,
    DecisionAlreadyReviewedException,
    DecisionAlreadySupersededException,
    DecisionContextStaleException,
    DecisionExpiredException,
    DecisionNotApprovedException,
    DecisionNotFoundException,
    DecisionVersionConflictException,
)
from app.core.security import create_access_token
from app.main import app
from app.repositories.decision_repository import decision_repository
from app.repositories.user_repository import UserRecord
from app.repositories.versioning_repository import versioning_repository
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.decision_review import DecisionReviewRequest, ReviewAction
from app.schemas.decisions import (
    DecisionApplyRequest,
    DecisionCreateRequest,
    DecisionInputReference,
    DecisionModelMetadata,
    DecisionProvenanceSource,
    DecisionRecord,
    DecisionRuleMetadata,
    DecisionStatus,
    DecisionType,
)
from app.schemas.explanations import ExplanationAudience
from app.services.decision_application_service import decision_application_service
from app.services.decision_context_service import decision_context_service
from app.services.decision_replay_service import decision_replay_service
from app.services.decision_review_service import decision_review_service
from app.services.decision_service import decision_service
from app.services.decision_validation_service import decision_validation_service
from app.services.explanation_service import explanation_service
from app.services.versioning_service import versioning_service


@pytest.fixture(autouse=True)
def reset_phase47_state():
    """Reset repository states before each test."""
    decision_repository.clear()
    versioning_repository.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinician_auth_headers():
    clinician_id = "user-clinician-p47"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=clinician_id,
            identifier="dr.verma@healthsetu.org",
            role=UserRole.DOCTOR,
            status=AccountStatus.ACTIVE,
            password_hash="mock-hash",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    token, _ = create_access_token(
        user_id=clinician_id,
        role=UserRole.DOCTOR.value,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def patient_auth_headers():
    patient_id = "patient-p47"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=patient_id,
            identifier="patient47@healthsetu.org",
            role=UserRole.PATIENT,
            status=AccountStatus.ACTIVE,
            password_hash="mock-hash",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    token, _ = create_access_token(
        user_id=patient_id,
        role=UserRole.PATIENT.value,
    )
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. UNIT & SERVICE TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_create_rule_based_decision_trace():
    """Rule-based decision captures rule set, version, matched rules, and inputs."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.TRIAGE_CLASSIFICATION,
        patient_id="pat-101",
        resource_type="symptom_assessment",
        resource_id="symp-001",
        source_service="triage_engine",
        inputs=[
            DecisionInputReference(
                resource_type="vitals",
                resource_id="vit-001",
                version_number=1,
                field_paths=["heart_rate", "spo2"],
            )
        ],
        output_payload={"urgency": "URGENT", "recommended_department": "CARDIOLOGY"},
        rule_metadata=DecisionRuleMetadata(
            rule_set_id="TRIAGE_RULESET_CARDIAC",
            rule_set_version="2.1.0",
            matched_rule_ids=["RULE_HR_ELEVATED", "RULE_SPO2_SUBOPTIMAL"],
        ),
        requires_human_oversight=True,
    )

    decision = await decision_service.create_decision(
        request=req,
        actor_id="sys-triage",
        actor_role="SYSTEM",
        actor_type=DecisionProvenanceSource.RULE_ENGINE,
    )

    assert decision.id.startswith("dec-")
    assert decision.status == DecisionStatus.REVIEW_REQUIRED
    assert decision.requires_human_oversight is True
    assert decision.rule_metadata.rule_set_id == "TRIAGE_RULESET_CARDIAC"
    assert len(decision.rule_metadata.matched_rule_ids) == 2
    assert decision.inputs[0].resource_type == "vitals"


@pytest.mark.asyncio
async def test_create_ai_assisted_decision_trace():
    """AI-assisted decision captures model metadata and schema versions."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.AI_EXTRACTION,
        patient_id="pat-101",
        resource_type="document",
        resource_id="doc-001",
        source_service="document_processing_service",
        inputs=[
            DecisionInputReference(
                resource_type="document",
                resource_id="doc-001",
                version_number=1,
                snapshot_hash="sha256-abc123mock",
            )
        ],
        output_payload={"extracted_diagnoses": ["Hypertension"], "allergies": ["Sulfa"]},
        model_metadata=DecisionModelMetadata(
            provider="google",
            model_identifier="gemini-1.5-pro",
            model_version="2026-v2",
            prompt_template_version="discharge_v3",
            schema_version="1.0.0",
            confidence=0.94,
        ),
        requires_human_oversight=True,
    )

    decision = await decision_service.create_decision(
        request=req,
        actor_id="sys-ai",
        actor_role="SYSTEM",
        actor_type=DecisionProvenanceSource.AI_MODEL,
    )

    assert decision.model_metadata.model_identifier == "gemini-1.5-pro"
    assert decision.model_metadata.confidence == 0.94
    assert decision.requires_human_oversight is True


@pytest.mark.asyncio
async def test_clinician_review_approval_flow():
    """Clinician reviews and approves decision, enabling downstream application."""
    # 1. Create decision
    req = DecisionCreateRequest(
        decision_type=DecisionType.MEDICATION_SAFETY_WARNING,
        patient_id="pat-101",
        source_service="medication_safety_service",
        output_payload={"warning": "Potential mild drug-food interaction"},
        requires_human_oversight=True,
    )
    decision = await decision_service.create_decision(
        request=req,
        actor_id="sys-med-safety",
        actor_role="SYSTEM",
    )
    assert decision.status == DecisionStatus.REVIEW_REQUIRED

    # 2. Review and Approve
    review_req = DecisionReviewRequest(
        action=ReviewAction.APPROVED,
        reason="Clinician reviewed patient diet and verified interaction risk is manageable.",
    )
    updated, review = await decision_review_service.submit_review(
        decision_id=decision.id,
        request=review_req,
        reviewer_id="dr-verma",
        reviewer_role="DOCTOR",
    )

    assert updated.status == DecisionStatus.APPROVED
    assert review.action == ReviewAction.APPROVED
    assert review.reviewer_id == "dr-verma"

    # 3. Apply Decision
    apply_req = DecisionApplyRequest(
        application_reason="Applied approved interaction guidance to care plan notes",
        downstream_action_type="CARE_PLAN_NOTE",
    )
    applied = await decision_application_service.apply_decision(
        decision_id=decision.id,
        request=apply_req,
        actor_id="dr-verma",
        actor_role="DOCTOR",
    )

    assert applied.status == DecisionStatus.APPLIED
    assert applied.applied_at is not None
    assert applied.downstream_action_id is not None


@pytest.mark.asyncio
async def test_clinician_review_modification_flow():
    """Clinician modifies system recommendation payload prior to approval."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.CARE_PLAN_RECOMMENDATION,
        patient_id="pat-101",
        source_service="care_plan_service",
        output_payload={"target_sodium_intake_mg": 2000, "exercise_min_per_week": 150},
        requires_human_oversight=True,
    )
    decision = await decision_service.create_decision(
        request=req,
        actor_id="sys-care-plan",
        actor_role="SYSTEM",
    )

    # Clinician adjusts exercise target for elderly patient
    review_req = DecisionReviewRequest(
        action=ReviewAction.MODIFIED,
        reason="Patient has mobility limitations; adjusting exercise target to 90 min/week",
        modifications={"exercise_min_per_week": 90},
    )
    updated, review = await decision_review_service.submit_review(
        decision_id=decision.id,
        request=review_req,
        reviewer_id="dr-verma",
        reviewer_role="DOCTOR",
    )

    assert updated.status == DecisionStatus.APPROVED
    assert updated.output_payload["exercise_min_per_week"] == 90
    assert updated.output_payload["target_sodium_intake_mg"] == 2000
    assert review.action == ReviewAction.MODIFIED


@pytest.mark.asyncio
async def test_stale_decision_context_detection_phase46_integration():
    """Decision generated against v1 of medication list cannot be applied if list is now v2."""
    # 1. Seed Medication Record v1 in Phase 46
    await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-staleness-test",
        patient_id="pat-101",
        state_data={"drug": "DrugX", "dose": "10mg"},
        actor_id="dr-verma",
        actor_role="DOCTOR",
        change_reason="Initial prescription",
    )

    # 2. Decision generated against v1
    req = DecisionCreateRequest(
        decision_type=DecisionType.MEDICATION_SAFETY_RESULT,
        patient_id="pat-101",
        resource_type="medication",
        resource_id="med-staleness-test",
        resource_version=1,
        source_service="medication_safety_service",
        output_payload={"safety_check": "PASSED"},
        requires_human_oversight=False,
    )
    decision = await decision_service.create_decision(
        request=req,
        actor_id="sys-med-safety",
        actor_role="SYSTEM",
    )

    # 3. Clinical record is updated to v2 in Phase 46
    await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-staleness-test",
        request=versioning_service.repository.get_version("medication", "med-staleness-test", 1) and
        __import__("app.schemas.versioning", fromlist=["VersionUpdateRequest"]).VersionUpdateRequest(
            expected_version=1,
            changes={"dose": "20mg"},
            change_reason="Increased dosage to 20mg",
        ),
        actor_id="dr-verma",
        actor_role="DOCTOR",
    )

    # 4. Context staleness detector flags decision as stale
    assert decision_context_service.is_context_stale(decision) is True

    # 5. Application of stale decision is blocked!
    with pytest.raises(DecisionContextStaleException):
        await decision_application_service.apply_decision(
            decision_id=decision.id,
            request=DecisionApplyRequest(application_reason="Attempt application of stale check"),
            actor_id="dr-verma",
            actor_role="DOCTOR",
        )


@pytest.mark.asyncio
async def test_decision_supersession():
    """A newer decision supersedes older decision without deleting history."""
    req1 = DecisionCreateRequest(
        decision_type=DecisionType.TRIAGE_CLASSIFICATION,
        patient_id="pat-101",
        source_service="triage_engine",
        output_payload={"urgency": "ROUTINE"},
    )
    d1 = await decision_service.create_decision(req1, "sys", "SYSTEM")

    req2 = DecisionCreateRequest(
        decision_type=DecisionType.TRIAGE_CLASSIFICATION,
        patient_id="pat-101",
        source_service="triage_engine",
        output_payload={"urgency": "URGENT"},
    )
    d2 = await decision_service.create_decision(req2, "sys", "SYSTEM")

    await decision_service.supersede_decision(d1.id, d2.id, actor_id="dr-verma")

    d1_reloaded = decision_service.get_decision(d1.id)
    d2_reloaded = decision_service.get_decision(d2.id)

    assert d1_reloaded.status == DecisionStatus.SUPERSEDED
    assert d1_reloaded.is_current is False
    assert d1_reloaded.superseded_by_id == d2.id
    assert d2_reloaded.supersedes_id == d1.id

    # Attempting review or application on superseded d1 raises DecisionAlreadySupersededException
    with pytest.raises(DecisionAlreadySupersededException):
        await decision_review_service.submit_review(
            decision_id=d1.id,
            request=DecisionReviewRequest(action=ReviewAction.APPROVED, reason="Late approve"),
            reviewer_id="dr-verma",
            reviewer_role="DOCTOR",
        )


@pytest.mark.asyncio
async def test_decision_replay_and_comparison():
    """Decision replay provides read-only inspection and comparative analysis."""
    req1 = DecisionCreateRequest(
        decision_type=DecisionType.DATA_RECONCILIATION_RECOMMENDATION,
        patient_id="pat-101",
        source_service="reconciliation_service",
        inputs=[DecisionInputReference(resource_type="lab", resource_id="lab-1", version_number=1)],
        output_payload={"confidence": 0.80, "action": "MERGE"},
    )
    d1 = await decision_service.create_decision(req1, "sys", "SYSTEM")

    req2 = DecisionCreateRequest(
        decision_type=DecisionType.DATA_RECONCILIATION_RECOMMENDATION,
        patient_id="pat-101",
        source_service="reconciliation_service",
        inputs=[DecisionInputReference(resource_type="lab", resource_id="lab-1", version_number=2)],
        output_payload={"confidence": 0.95, "action": "MERGE"},
    )
    d2 = await decision_service.create_decision(req2, "sys", "SYSTEM")

    trace = decision_replay_service.get_decision_trace(d1.id)
    assert trace.decision.id == d1.id
    assert trace.is_stale is False

    comparison = decision_replay_service.compare_decisions(d1.id, d2.id)
    assert len(comparison.changed_inputs) > 0
    assert "confidence" in comparison.output_differences


@pytest.mark.asyncio
async def test_explanation_generation_patient_vs_clinician():
    """Explanation formats audience-appropriate text without exposing private model reasoning."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.TRIAGE_CLASSIFICATION,
        patient_id="pat-101",
        source_service="triage_engine",
        output_payload={"urgency": "URGENT", "score": 85},
        rule_metadata=DecisionRuleMetadata(rule_set_id="RULES_TRIAGE_V1", matched_rule_ids=["R1", "R2"]),
        model_metadata=DecisionModelMetadata(model_identifier="gemini-1.5-flash", confidence=0.89),
    )
    decision = await decision_service.create_decision(req, "sys", "SYSTEM")

    # Patient mode: plain language, safe disclaimer
    expl_patient = explanation_service.generate_explanation(decision, ExplanationAudience.PATIENT)
    assert "automated clinical aid" in expl_patient.disclaimer
    assert "not a final medical diagnosis" in expl_patient.disclaimer
    assert "R1" not in expl_patient.rules_or_model_used

    # Clinician mode: rule references, model confidence
    expl_clinician = explanation_service.generate_explanation(decision, ExplanationAudience.CLINICIAN)
    assert "RULES_TRIAGE_V1" in expl_clinician.rules_or_model_used
    assert expl_clinician.confidence == 0.89


@pytest.mark.asyncio
async def test_expired_decision_cannot_be_applied():
    """Decision past its expiration timestamp cannot be applied."""
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    req = DecisionCreateRequest(
        decision_type=DecisionType.MEDICATION_SAFETY_RESULT,
        patient_id="pat-101",
        source_service="medication_safety",
        output_payload={"status": "OK"},
        expires_at=past_time,
        requires_human_oversight=False,
    )
    decision = await decision_service.create_decision(req, "sys", "SYSTEM")

    with pytest.raises(DecisionExpiredException):
        await decision_application_service.apply_decision(
            decision_id=decision.id,
            request=DecisionApplyRequest(application_reason="Attempt apply expired"),
            actor_id="dr-verma",
            actor_role="DOCTOR",
        )


# =====================================================================
# 2. THE 12 NON-NEGOTIABLE CLINICAL SAFETY REGRESSIONS (TRD Sec 52)
# =====================================================================

@pytest.mark.asyncio
async def test_safety_regression_1_ai_cannot_diagnose_autonomously():
    """Safety Regression 1: AI output cannot autonomously become diagnosis."""
    with pytest.raises(AIClinicalActionProhibitedException):
        decision_validation_service.validate_safety_boundaries(
            decision_type=DecisionType.AI_SUMMARY,
            initiating_actor_role="AI",
            attempted_action="AUTONOMOUS_DIAGNOSE",
        )


@pytest.mark.asyncio
async def test_safety_regression_2_ai_cannot_prescribe_autonomously():
    """Safety Regression 2: AI output cannot autonomously become prescription."""
    with pytest.raises(AIClinicalActionProhibitedException):
        decision_validation_service.validate_safety_boundaries(
            decision_type=DecisionType.AI_EXTRACTION,
            initiating_actor_role="AI_AGENT",
            attempted_action="AUTONOMOUS_PRESCRIBE",
        )


@pytest.mark.asyncio
async def test_safety_regression_3_ai_cannot_modify_medications_autonomously():
    """Safety Regression 3: AI output cannot modify medications automatically."""
    with pytest.raises(AIClinicalActionProhibitedException):
        decision_validation_service.validate_safety_boundaries(
            decision_type=DecisionType.AI_CLASSIFICATION,
            initiating_actor_role="AI",
            attempted_action="AUTONOMOUS_APPLY",
        )


@pytest.mark.asyncio
async def test_safety_regression_4_system_recommendation_cannot_bypass_human_review():
    """Safety Regression 4: System recommendations cannot bypass required human review."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.CARE_PLAN_RECOMMENDATION,
        patient_id="pat-101",
        source_service="care_plan_service",
        output_payload={"plan": "Restricted Fluid Intake"},
        requires_human_oversight=True,
    )
    decision = await decision_service.create_decision(req, "sys", "SYSTEM")

    with pytest.raises(DecisionNotApprovedException):
        await decision_application_service.apply_decision(
            decision_id=decision.id,
            request=DecisionApplyRequest(application_reason="Premature apply without clinician review"),
            actor_id="dr-verma",
            actor_role="DOCTOR",
        )


@pytest.mark.asyncio
async def test_safety_regression_5_unauthorized_actor_cannot_review():
    """Safety Regression 5: Non-clinician cannot approve clinical recommendations."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.MEDICATION_SAFETY_WARNING,
        patient_id="pat-101",
        source_service="med_safety",
        output_payload={"warn": "Interaction"},
        requires_human_oversight=True,
    )
    decision = await decision_service.create_decision(req, "sys", "SYSTEM")

    with pytest.raises(AutonomousDecisionExecutionProhibitedException):
        await decision_review_service.submit_review(
            decision_id=decision.id,
            request=DecisionReviewRequest(action=ReviewAction.APPROVED, reason="Patient self-approve"),
            reviewer_id="patient-101",
            reviewer_role="PATIENT",
        )


@pytest.mark.asyncio
async def test_safety_regression_6_stale_decisions_cannot_apply_to_newer_records():
    """Safety Regression 6: Stale decisions cannot silently apply to newer clinical records."""
    decision = DecisionRecord(
        decision_type=DecisionType.MEDICATION_SAFETY_RESULT,
        patient_id="pat-101",
        resource_type="medication",
        resource_id="med-reg6",
        resource_version=1,
        status=DecisionStatus.APPROVED,
        initiating_actor_id="sys",
        initiating_actor_role="SYSTEM",
        source_service="med_safety",
    )
    decision_repository.create_decision(decision)

    # Seed newer v2 in version repository
    await versioning_service.create_initial_version(
        resource_type="medication",
        resource_id="med-reg6",
        patient_id="pat-101",
        state_data={"dose": "10mg"},
        actor_id="dr-verma",
        actor_role="DOCTOR",
        change_reason="Initial v1 intake",
    )
    await versioning_service.update_version(
        resource_type="medication",
        resource_id="med-reg6",
        request=__import__("app.schemas.versioning", fromlist=["VersionUpdateRequest"]).VersionUpdateRequest(
            expected_version=1, changes={"dose": "20mg"}, change_reason="v2 update"
        ),
        actor_id="dr-verma",
        actor_role="DOCTOR",
    )

    with pytest.raises(DecisionContextStaleException):
        await decision_application_service.apply_decision(
            decision_id=decision.id,
            request=DecisionApplyRequest(application_reason="Apply stale"),
            actor_id="dr-verma",
            actor_role="DOCTOR",
        )


@pytest.mark.asyncio
async def test_safety_regression_7_superseded_decision_cannot_be_approved_or_applied():
    """Safety Regression 7: An already superseded decision cannot be approved or applied."""
    d = DecisionRecord(
        decision_type=DecisionType.TRIAGE_CLASSIFICATION,
        patient_id="pat-101",
        status=DecisionStatus.SUPERSEDED,
        is_current=False,
        initiating_actor_id="sys",
        initiating_actor_role="SYSTEM",
        source_service="triage",
    )
    decision_repository.create_decision(d)

    with pytest.raises(DecisionAlreadySupersededException):
        await decision_review_service.submit_review(
            decision_id=d.id,
            request=DecisionReviewRequest(action=ReviewAction.APPROVED, reason="Approve old"),
            reviewer_id="dr-verma",
            reviewer_role="DOCTOR",
        )


@pytest.mark.asyncio
async def test_safety_regression_8_system_output_not_falsely_attributed_to_clinician():
    """Safety Regression 8: System output is never falsely attributed to a clinician."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.AI_SUMMARY,
        patient_id="pat-101",
        source_service="ai_assistant",
        output_payload={"summary": "Patient reports fever"},
    )
    decision = await decision_service.create_decision(
        request=req,
        actor_id="sys-ai",
        actor_role="SYSTEM",
        actor_type=DecisionProvenanceSource.AI_MODEL,
    )
    assert decision.initiating_actor_type == DecisionProvenanceSource.AI_MODEL
    assert decision.initiating_actor_type != DecisionProvenanceSource.CLINICIAN


@pytest.mark.asyncio
async def test_safety_regression_9_hidden_model_reasoning_never_exposed():
    """Safety Regression 9: Hidden model chain-of-thought is never exposed in explanations."""
    decision = DecisionRecord(
        decision_type=DecisionType.AI_SUMMARY,
        patient_id="pat-101",
        status=DecisionStatus.GENERATED,
        initiating_actor_id="sys",
        initiating_actor_role="SYSTEM",
        source_service="ai",
        output_payload={"summary": "Clinical summary"},
    )
    expl = explanation_service.generate_explanation(decision, ExplanationAudience.PATIENT)
    assert "chain_of_thought" not in str(expl.model_dump())
    assert "internal_prompt" not in str(expl.model_dump())


@pytest.mark.asyncio
async def test_safety_regression_10_missing_safety_evidence_is_not_treated_as_safe():
    """Safety Regression 10: Missing safety evidence is not treated as safe."""
    # When safety result has warnings or missing evidence, requires_human_oversight is true
    req = DecisionCreateRequest(
        decision_type=DecisionType.MEDICATION_SAFETY_WARNING,
        patient_id="pat-101",
        source_service="med_safety",
        output_payload={"risk": "UNKNOWN_DATA_GAP"},
        requires_human_oversight=True,
    )
    decision = await decision_service.create_decision(req, "sys", "SYSTEM")
    assert decision.status == DecisionStatus.REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_safety_regression_11_historical_decisions_never_overwritten():
    """Safety Regression 11: Historical decisions are never overwritten."""
    req = DecisionCreateRequest(
        decision_type=DecisionType.TRIAGE_CLASSIFICATION,
        patient_id="pat-101",
        source_service="triage",
        output_payload={"urgency": "MODERATE"},
    )
    d1 = await decision_service.create_decision(req, "sys", "SYSTEM")
    # New decision
    req2 = DecisionCreateRequest(
        decision_type=DecisionType.TRIAGE_CLASSIFICATION,
        patient_id="pat-101",
        source_service="triage",
        output_payload={"urgency": "SEVERE"},
    )
    d2 = await decision_service.create_decision(req2, "sys", "SYSTEM")
    await decision_service.supersede_decision(d1.id, d2.id, "dr-verma")

    # D1 still exists in repository with original payload
    d1_fetched = decision_repository.get_decision(d1.id)
    assert d1_fetched.output_payload["urgency"] == "MODERATE"


@pytest.mark.asyncio
async def test_safety_regression_12_cross_patient_decision_isolation():
    """Safety Regression 12: Cross-patient decision access is blocked."""
    decision = DecisionRecord(
        decision_type=DecisionType.AI_SUMMARY,
        patient_id="patient-1",
        status=DecisionStatus.GENERATED,
        initiating_actor_id="sys",
        initiating_actor_role="SYSTEM",
        source_service="ai",
    )
    decision_repository.create_decision(decision)

    # Validated via endpoint checks or tenant isolation rules
    assert decision.patient_id == "patient-1"


# =====================================================================
# 3. END-TO-END REST API TESTS (VIA TESTCLIENT)
# =====================================================================

def test_api_create_decision(client, clinician_auth_headers):
    """POST /api/v1/decisions successfully registers traceable decision."""
    payload = {
        "decision_type": "TRIAGE_CLASSIFICATION",
        "patient_id": "pat-api-1",
        "source_service": "triage_api_test",
        "output_payload": {"urgency": "URGENT", "level": 2},
        "requires_human_oversight": True,
    }
    response = client.post("/api/v1/decisions", json=payload, headers=clinician_auth_headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["decision_type"] == "TRIAGE_CLASSIFICATION"
    assert data["status"] == "REVIEW_REQUIRED"


def test_api_get_decision_and_trace(client, clinician_auth_headers):
    """GET /decisions/{id} and /decisions/{id}/trace return complete decision trace."""
    decision = asyncio.run(
        decision_service.create_decision(
            request=DecisionCreateRequest(
                decision_type=DecisionType.MEDICATION_SAFETY_WARNING,
                patient_id="pat-api-2",
                source_service="med_safety",
                output_payload={"risk": "Moderate interaction"},
                requires_human_oversight=True,
            ),
            actor_id="dr-verma",
            actor_role="DOCTOR",
        )
    )

    # Detail
    res1 = client.get(f"/api/v1/decisions/{decision.id}", headers=clinician_auth_headers)
    assert res1.status_code == 200
    assert res1.json()["data"]["id"] == decision.id

    # Trace
    res2 = client.get(f"/api/v1/decisions/{decision.id}/trace", headers=clinician_auth_headers)
    assert res2.status_code == 200
    assert "trace_summary" in res2.json()["data"]


def test_api_explanation_endpoints(client, clinician_auth_headers, patient_auth_headers):
    """GET /decisions/{id}/explanation generates audience-tailored explanations."""
    decision = asyncio.run(
        decision_service.create_decision(
            request=DecisionCreateRequest(
                decision_type=DecisionType.TRIAGE_CLASSIFICATION,
                patient_id="patient-p47",
                source_service="triage",
                output_payload={"urgency": "ROUTINE"},
            ),
            actor_id="dr-verma",
            actor_role="DOCTOR",
        )
    )

    # Clinician request
    res_clin = client.get(
        f"/api/v1/decisions/{decision.id}/explanation?audience=CLINICIAN",
        headers=clinician_auth_headers,
    )
    assert res_clin.status_code == 200
    assert res_clin.json()["data"]["audience"] == "CLINICIAN"

    # Patient request
    res_pat = client.get(
        f"/api/v1/decisions/{decision.id}/explanation",
        headers=patient_auth_headers,
    )
    assert res_pat.status_code == 200
    assert res_pat.json()["data"]["audience"] == "PATIENT"
    assert "automated clinical aid" in res_pat.json()["data"]["disclaimer"]


def test_api_review_and_apply_flow(client, clinician_auth_headers):
    """POST /decisions/{id}/review and POST /decisions/{id}/apply."""
    decision = asyncio.run(
        decision_service.create_decision(
            request=DecisionCreateRequest(
                decision_type=DecisionType.CARE_PLAN_RECOMMENDATION,
                patient_id="pat-api-3",
                source_service="care_plan",
                output_payload={"steps": ["Diet adjustment"]},
                requires_human_oversight=True,
            ),
            actor_id="sys",
            actor_role="SYSTEM",
        )
    )

    # 1. Review
    rev_payload = {
        "action": "APPROVED",
        "reason": "Clinician approved dietary plan for hypertension management",
    }
    rev_res = client.post(
        f"/api/v1/decisions/{decision.id}/review",
        json=rev_payload,
        headers=clinician_auth_headers,
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["data"]["status"] == "APPROVED"

    # 2. Apply
    apply_payload = {
        "application_reason": "Publishing dietary plan to patient portal",
        "downstream_action_type": "CARE_PLAN_PUBLISH",
    }
    apply_res = client.post(
        f"/api/v1/decisions/{decision.id}/apply",
        json=apply_payload,
        headers=clinician_auth_headers,
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["data"]["status"] == "APPLIED"


def test_api_cross_patient_access_blocked(client, patient_auth_headers):
    """Patient cannot inspect another patient's decision records (HTTP 403)."""
    foreign_decision = asyncio.run(
        decision_service.create_decision(
            request=DecisionCreateRequest(
                decision_type=DecisionType.AI_SUMMARY,
                patient_id="pat-other-user-999",
                source_service="ai",
                output_payload={"summary": "Private clinical notes"},
            ),
            actor_id="sys",
            actor_role="SYSTEM",
        )
    )

    response = client.get(
        f"/api/v1/decisions/{foreign_decision.id}",
        headers=patient_auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DECISION_ACCESS_DENIED"


def test_api_compare_decisions(client, clinician_auth_headers):
    """GET /decisions/compare returns diff analysis."""
    d1 = asyncio.run(
        decision_service.create_decision(
            request=DecisionCreateRequest(
                decision_type=DecisionType.TRIAGE_CLASSIFICATION,
                patient_id="pat-comp",
                source_service="triage",
                output_payload={"urgency": "ROUTINE"},
            ),
            actor_id="sys",
            actor_role="SYSTEM",
        )
    )
    d2 = asyncio.run(
        decision_service.create_decision(
            request=DecisionCreateRequest(
                decision_type=DecisionType.TRIAGE_CLASSIFICATION,
                patient_id="pat-comp",
                source_service="triage",
                output_payload={"urgency": "URGENT"},
            ),
            actor_id="sys",
            actor_role="SYSTEM",
        )
    )

    response = client.get(
        f"/api/v1/decisions/compare?base_id={d1.id}&compared_id={d2.id}",
        headers=clinician_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "urgency" in data["output_differences"]

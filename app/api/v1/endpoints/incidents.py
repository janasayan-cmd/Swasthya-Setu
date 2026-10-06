"""Clinical Safety Incident Management, Investigation & Corrective Action APIs (Phase 49).

Endpoints:
- POST /incidents/signals: Ingest safety signals from gates, providers, or workflows
- POST /incidents: Register an incident candidate directly
- GET /incidents: Filter and list safety incidents
- GET /incidents/{incident_id}: Get incident details
- GET /incidents/{incident_id}/timeline: Chronological reconstructed timeline
- GET /incidents/{incident_id}/evidence: List attached evidence references
- POST /incidents/{incident_id}/evidence: Attach foreign evidence reference
- GET /incidents/{incident_id}/investigation: Consolidated investigation record
- POST /incidents/{incident_id}/triage: Assess severity, impact, and containment necessity
- POST /incidents/{incident_id}/assign: Assign lead safety investigator
- POST /incidents/{incident_id}/contain: Apply active risk containment
- POST /incidents/{incident_id}/hypotheses: Propose root-cause hypothesis
- PATCH /incidents/hypotheses/{hypothesis_id}: Update hypothesis status (SUPPORTED, CONFIRMED, etc.)
- GET /incidents/{incident_id}/corrective-actions: List remediation actions
- POST /incidents/{incident_id}/corrective-actions: Create remediation action
- PATCH /incidents/corrective-actions/{action_id}: Update corrective action status
- POST /incidents/{incident_id}/resolve: Mark incident resolved with findings
- POST /incidents/{incident_id}/close: Validate prerequisites and formally close incident
- POST /incidents/{incident_id}/reopen: Reopen incident upon recurrence or new findings
- GET /patients/{patient_id}/incidents: List safety incidents linked to patient
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_clinical_incident_service,
    get_corrective_action_service,
    get_current_user,
    get_incident_closure_service,
    get_incident_containment_service,
    get_incident_evidence_service,
    get_incident_investigation_service,
    get_safety_incident_service,
)
from app.core.logging import request_id_ctx_var
from app.schemas.corrective_actions import (
    CorrectiveActionCreateRequest,
    CorrectiveActionRecord,
    CorrectiveActionStatusUpdateRequest,
)
from app.schemas.incident_evidence import (
    EvidenceAttachRequest,
    EvidenceReference,
    IncidentTimelineEntry,
)
from app.schemas.incident_investigation import (
    HypothesisCreateRequest,
    HypothesisStatusUpdateRequest,
    InvestigationRecord,
    RootCauseHypothesis,
)
from app.schemas.incidents import (
    IncidentAssignmentRequest,
    IncidentClosureRequest,
    IncidentContainmentRequest,
    IncidentCreateRequest,
    IncidentRecord,
    IncidentReopenRequest,
    IncidentResolutionRequest,
    IncidentStatus,
    IncidentTriageRequest,
    IncidentType,
    SafetySignal,
    SafetySignalCreateRequest,
)
from app.schemas.response import StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.corrective_action_service import (
    CorrectiveActionService,
    corrective_action_service,
)
from app.services.incident_closure_service import (
    IncidentClosureService,
    incident_closure_service,
)
from app.services.incident_containment_service import (
    IncidentContainmentService,
    incident_containment_service,
)
from app.services.incident_evidence_service import (
    IncidentEvidenceService,
    incident_evidence_service,
)
from app.services.incident_investigation_service import (
    IncidentInvestigationService,
    incident_investigation_service,
)
from app.services.clinical_incident_service import (
    ClinicalIncidentService,
    clinical_incident_service,
)
from app.services.safety_incident_service import (
    SafetyIncidentService,
    safety_incident_service,
)

router = APIRouter(tags=["Clinical Safety Incident Management & Investigation"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


# ---------------------------------------------------------------------------
# 1. Safety Signal Intake
# ---------------------------------------------------------------------------


@router.post(
    "/incidents/signals",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Safety Signal",
    description="Captures runtime safety signals from gates, external providers, workflows, or clinicians.",
)
async def ingest_safety_signal(
    http_request: Request,
    request_body: SafetySignalCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    safety_svc: Annotated[SafetyIncidentService, Depends(get_safety_incident_service)] = None,
) -> StandardSuccessResponse[Dict[str, Any]]:
    svc = safety_svc or safety_incident_service
    req_id = _req_id(http_request)

    signal, incident = await svc.ingest_safety_signal(
        request=request_body,
        actor_id=current_user.user_id,
        request_id=req_id,
    )

    data = {
        "signal": signal.model_dump(mode="json"),
        "incident": incident.model_dump(mode="json") if incident else None,
        "is_duplicate": len(incident.signal_ids) > 1 if incident else False,
    }

    return StandardSuccessResponse(
        success=True,
        data=data,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 2. Incident Intake & Queries
# ---------------------------------------------------------------------------


@router.post(
    "/incidents",
    response_model=StandardSuccessResponse[IncidentRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Safety Incident Candidate",
    description="Registers an incident candidate directly for formal triage.",
)
async def create_incident(
    http_request: Request,
    request_body: IncidentCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inc_svc: Annotated[ClinicalIncidentService, Depends(get_clinical_incident_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = inc_svc or clinical_incident_service
    req_id = _req_id(http_request)

    incident = await svc.create_incident(
        request=request_body,
        actor_id=current_user.user_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


@router.get(
    "/incidents",
    response_model=StandardSuccessResponse[List[IncidentRecord]],
    summary="List Safety Incidents",
    description="Filter and retrieve safety incidents by status or incident type.",
)
async def list_incidents(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_id: Optional[str] = Query(default=None, description="Filter by patient ID"),
    incident_type: Optional[IncidentType] = Query(default=None, description="Filter by incident type"),
    incident_status: Optional[IncidentStatus] = Query(default=None, alias="status", description="Filter by status"),
    inc_svc: Annotated[ClinicalIncidentService, Depends(get_clinical_incident_service)] = None,
) -> StandardSuccessResponse[List[IncidentRecord]]:
    svc = inc_svc or clinical_incident_service
    req_id = _req_id(http_request)

    incidents = svc.list_incidents(
        patient_id=patient_id,
        incident_type=incident_type,
        status=incident_status,
    )

    return StandardSuccessResponse(
        success=True,
        data=incidents,
        request_id=req_id,
    )


@router.get(
    "/incidents/{incident_id}",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Get Safety Incident",
    description="Retrieve a safety incident by ID.",
)
async def get_incident(
    http_request: Request,
    incident_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inc_svc: Annotated[ClinicalIncidentService, Depends(get_clinical_incident_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = inc_svc or clinical_incident_service
    req_id = _req_id(http_request)

    incident = svc.get_incident(incident_id)

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 3. Incident Lifecycle Transitions (Triage, Contain, Resolve, Close, Reopen)
# ---------------------------------------------------------------------------


@router.post(
    "/incidents/{incident_id}/triage",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Triage Incident",
    description="Updates assessed severity and marks whether immediate risk containment is required.",
)
async def triage_incident(
    http_request: Request,
    incident_id: str,
    request_body: IncidentTriageRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inc_svc: Annotated[ClinicalIncidentService, Depends(get_clinical_incident_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = inc_svc or clinical_incident_service
    req_id = _req_id(http_request)

    incident = await svc.triage_incident(
        incident_id=incident_id,
        request=request_body,
        triaged_by_id=current_user.user_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/assign",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Assign Lead Investigator",
    description="Assigns an authorized safety investigator. AI agents are prohibited from being lead investigators.",
)
async def assign_investigator(
    http_request: Request,
    incident_id: str,
    request_body: IncidentAssignmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inv_svc: Annotated[IncidentInvestigationService, Depends(get_incident_investigation_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = inv_svc or incident_investigation_service
    req_id = _req_id(http_request)

    incident = await svc.assign_investigator(
        incident_id=incident_id,
        investigator_id=request_body.investigator_id,
        investigator_role=request_body.investigator_role,
        assigned_by_id=current_user.user_id,
        notes=request_body.assignment_notes,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/contain",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Record Containment Action",
    description="Applies active risk mitigation (e.g., disabling failing provider, pausing workflow).",
)
async def record_containment(
    http_request: Request,
    incident_id: str,
    request_body: IncidentContainmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    contain_svc: Annotated[IncidentContainmentService, Depends(get_incident_containment_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = contain_svc or incident_containment_service
    req_id = _req_id(http_request)

    incident = await svc.record_containment(
        incident_id=incident_id,
        request=request_body,
        contained_by_id=current_user.user_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Resolve Incident",
    description="Marks the incident resolved with documented remediation findings prior to closure.",
)
async def resolve_incident(
    http_request: Request,
    incident_id: str,
    request_body: IncidentResolutionRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inc_svc: Annotated[ClinicalIncidentService, Depends(get_clinical_incident_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = inc_svc or clinical_incident_service
    req_id = _req_id(http_request)

    incident = await svc.resolve_incident(
        incident_id=incident_id,
        request=request_body,
        resolved_by_id=current_user.user_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/close",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Close Incident",
    description="Validates containment and corrective actions before formal closure. AI cannot autonomously close.",
)
async def close_incident(
    http_request: Request,
    incident_id: str,
    request_body: IncidentClosureRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    closure_svc: Annotated[IncidentClosureService, Depends(get_incident_closure_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = closure_svc or incident_closure_service
    req_id = _req_id(http_request)

    user_role = getattr(current_user, "role", "SAFETY_OFFICER")
    incident = await svc.close_incident(
        incident_id=incident_id,
        request=request_body,
        closed_by_id=current_user.user_id,
        closed_by_role=str(user_role),
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/reopen",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Reopen Incident",
    description="Reopens a previously resolved or closed incident upon recurrence or new findings.",
)
async def reopen_incident(
    http_request: Request,
    incident_id: str,
    request_body: IncidentReopenRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inc_svc: Annotated[ClinicalIncidentService, Depends(get_clinical_incident_service)] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    svc = inc_svc or clinical_incident_service
    req_id = _req_id(http_request)

    incident = await svc.reopen_incident(
        incident_id=incident_id,
        request=request_body,
        reopened_by_id=current_user.user_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=incident,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 4. Evidence & Chronological Timeline
# ---------------------------------------------------------------------------


@router.get(
    "/incidents/{incident_id}/timeline",
    response_model=StandardSuccessResponse[List[IncidentTimelineEntry]],
    summary="Get Chronological Incident Timeline",
    description="Reconstructs timeline distinguishing occurred, detected, recorded, contained, and closed times.",
)
async def get_incident_timeline(
    http_request: Request,
    incident_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ev_svc: Annotated[IncidentEvidenceService, Depends(get_incident_evidence_service)] = None,
) -> StandardSuccessResponse[List[IncidentTimelineEntry]]:
    svc = ev_svc or incident_evidence_service
    req_id = _req_id(http_request)

    timeline = svc.reconstruct_timeline(incident_id)

    return StandardSuccessResponse(
        success=True,
        data=timeline,
        request_id=req_id,
    )


@router.get(
    "/incidents/{incident_id}/evidence",
    response_model=StandardSuccessResponse[List[EvidenceReference]],
    summary="List Incident Evidence References",
    description="Lists external evidence pointers linked to the incident without exposing raw PHI.",
)
async def list_incident_evidence(
    http_request: Request,
    incident_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ev_svc: Annotated[IncidentEvidenceService, Depends(get_incident_evidence_service)] = None,
) -> StandardSuccessResponse[List[EvidenceReference]]:
    svc = ev_svc or incident_evidence_service
    req_id = _req_id(http_request)

    evidence_list = svc.list_evidence(incident_id)

    return StandardSuccessResponse(
        success=True,
        data=evidence_list,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/evidence",
    response_model=StandardSuccessResponse[EvidenceReference],
    status_code=status.HTTP_201_CREATED,
    summary="Attach Evidence Reference",
    description="Attaches a foreign subsystem pointer (e.g. decision ID, audit event, log hash) to the incident.",
)
async def attach_evidence(
    http_request: Request,
    incident_id: str,
    request_body: EvidenceAttachRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ev_svc: Annotated[IncidentEvidenceService, Depends(get_incident_evidence_service)] = None,
) -> StandardSuccessResponse[EvidenceReference]:
    svc = ev_svc or incident_evidence_service
    req_id = _req_id(http_request)

    evidence = svc.attach_evidence(
        incident_id=incident_id,
        request=request_body,
        recorded_by_id=current_user.user_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=evidence,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 5. Investigation & Root-Cause Hypotheses
# ---------------------------------------------------------------------------


@router.get(
    "/incidents/{incident_id}/investigation",
    response_model=StandardSuccessResponse[InvestigationRecord],
    summary="Get Investigation State",
    description="Retrieves consolidated investigation findings, hypotheses, and assigned investigators.",
)
async def get_investigation(
    http_request: Request,
    incident_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inv_svc: Annotated[IncidentInvestigationService, Depends(get_incident_investigation_service)] = None,
) -> StandardSuccessResponse[InvestigationRecord]:
    svc = inv_svc or incident_investigation_service
    req_id = _req_id(http_request)

    record = svc.get_investigation_record(incident_id)

    return StandardSuccessResponse(
        success=True,
        data=record,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/hypotheses",
    response_model=StandardSuccessResponse[RootCauseHypothesis],
    status_code=status.HTTP_201_CREATED,
    summary="Propose Root-Cause Hypothesis",
    description="Documents a proposed root cause candidate, strictly preserving hypothesis uncertainty.",
)
async def propose_hypothesis(
    http_request: Request,
    incident_id: str,
    request_body: HypothesisCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inv_svc: Annotated[IncidentInvestigationService, Depends(get_incident_investigation_service)] = None,
) -> StandardSuccessResponse[RootCauseHypothesis]:
    svc = inv_svc or incident_investigation_service
    req_id = _req_id(http_request)

    user_role = getattr(current_user, "role", "SAFETY_INVESTIGATOR")
    hypothesis = await svc.propose_hypothesis(
        incident_id=incident_id,
        request=request_body,
        proposer_id=current_user.user_id,
        proposer_role=str(user_role),
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=hypothesis,
        request_id=req_id,
    )


@router.patch(
    "/incidents/hypotheses/{hypothesis_id}",
    response_model=StandardSuccessResponse[RootCauseHypothesis],
    summary="Update Hypothesis Status",
    description="Validates or rejects a hypothesis. AI cannot autonomously confirm root cause.",
)
async def update_hypothesis_status(
    http_request: Request,
    hypothesis_id: str,
    request_body: HypothesisStatusUpdateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inv_svc: Annotated[IncidentInvestigationService, Depends(get_incident_investigation_service)] = None,
) -> StandardSuccessResponse[RootCauseHypothesis]:
    svc = inv_svc or incident_investigation_service
    req_id = _req_id(http_request)

    user_role = getattr(current_user, "role", "SAFETY_INVESTIGATOR")
    hypothesis = await svc.update_hypothesis_status(
        hypothesis_id=hypothesis_id,
        request=request_body,
        updater_id=current_user.user_id,
        updater_role=str(user_role),
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=hypothesis,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 6. Corrective & Preventive Actions
# ---------------------------------------------------------------------------


@router.get(
    "/incidents/{incident_id}/corrective-actions",
    response_model=StandardSuccessResponse[List[CorrectiveActionRecord]],
    summary="List Corrective Actions",
    description="Lists all remediation and preventive actions tracked for this safety incident.",
)
async def list_corrective_actions(
    http_request: Request,
    incident_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    action_svc: Annotated[CorrectiveActionService, Depends(get_corrective_action_service)] = None,
) -> StandardSuccessResponse[List[CorrectiveActionRecord]]:
    svc = action_svc or corrective_action_service
    req_id = _req_id(http_request)

    actions = svc.list_actions(incident_id)

    return StandardSuccessResponse(
        success=True,
        data=actions,
        request_id=req_id,
    )


@router.post(
    "/incidents/{incident_id}/corrective-actions",
    response_model=StandardSuccessResponse[CorrectiveActionRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Corrective Action",
    description="Creates a corrective or preventive remediation action linked to the safety incident.",
)
async def create_corrective_action(
    http_request: Request,
    incident_id: str,
    request_body: CorrectiveActionCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    action_svc: Annotated[CorrectiveActionService, Depends(get_corrective_action_service)] = None,
) -> StandardSuccessResponse[CorrectiveActionRecord]:
    svc = action_svc or corrective_action_service
    req_id = _req_id(http_request)

    action = await svc.create_action(
        incident_id=incident_id,
        request=request_body,
        created_by_id=current_user.user_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.patch(
    "/incidents/corrective-actions/{action_id}",
    response_model=StandardSuccessResponse[CorrectiveActionRecord],
    summary="Update Corrective Action Status",
    description="Updates status of a corrective action (e.g. COMPLETED, VERIFIED).",
)
async def update_corrective_action_status(
    http_request: Request,
    action_id: str,
    request_body: CorrectiveActionStatusUpdateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    action_svc: Annotated[CorrectiveActionService, Depends(get_corrective_action_service)] = None,
) -> StandardSuccessResponse[CorrectiveActionRecord]:
    svc = action_svc or corrective_action_service
    req_id = _req_id(http_request)

    action = svc.update_action_status(
        action_id=action_id,
        request=request_body,
        updated_by_id=current_user.user_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 7. Patient-Scoped Incidents Query
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/incidents",
    response_model=StandardSuccessResponse[List[IncidentRecord]],
    summary="Get Patient Safety Incidents",
    description="Retrieves safety incidents linked to a patient for authorized clinical/safety personnel.",
)
async def get_patient_incidents(
    http_request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    inc_svc: Annotated[ClinicalIncidentService, Depends(get_clinical_incident_service)] = None,
) -> StandardSuccessResponse[List[IncidentRecord]]:
    svc = inc_svc or clinical_incident_service
    req_id = _req_id(http_request)

    incidents = svc.list_incidents(patient_id=patient_id)

    return StandardSuccessResponse(
        success=True,
        data=incidents,
        request_id=req_id,
    )

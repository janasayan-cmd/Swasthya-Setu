"""Phase 51: Clinical Safety Governance, Risk Acceptance & Controlled Safety Change Management APIs.

Endpoints:
- POST /safety-governance/risks: Register a clinical safety risk
- GET  /safety-governance/risks: List and filter governed risks
- GET  /safety-governance/risks/{risk_id}: Get risk details
- GET  /safety-governance/risks/{risk_id}/history: Chronological risk audit timeline
- GET  /safety-governance/risks/{risk_id}/evidence: Attached risk evidence references
- GET  /safety-governance/risks/{risk_id}/assessments: Risk assessments history
- POST /safety-governance/risks/{risk_id}/assess: Conduct structured risk assessment
- POST /safety-governance/risks/{risk_id}/mitigate: Create planned mitigation
- POST /safety-governance/risks/{risk_id}/accept: Explicit residual risk acceptance
- POST /safety-governance/risks/{risk_id}/reject: Reject proposed risk or residual risk
- POST /safety-governance/risks/{risk_id}/reassess: Trigger formal risk reassessment
- POST /safety-governance/risks/{risk_id}/reopen: Reopen closed risk with history preserved
- POST /safety-governance/risks/{risk_id}/close: Formally close risk after prerequisite validation
- GET  /safety-governance/change-requests: List safety change requests
- POST /safety-governance/change-requests: Initiate safety change request
- GET  /safety-governance/change-requests/{change_id}: Get safety change details
- GET  /safety-governance/change-requests/{change_id}/history: Safety change audit history
- POST /safety-governance/change-requests/{change_id}/approve: Approve/Reject change request
- POST /safety-governance/change-requests/{change_id}/reject: Explicitly reject change request
- POST /safety-governance/change-requests/{change_id}/implement: Execute implementation gate & deploy
- POST /safety-governance/change-requests/{change_id}/validate: Record post-change validation outcome
- POST /safety-governance/change-requests/{change_id}/rollback: Execute controlled rollback
- POST /safety-governance/change-requests/{change_id}/close: Formally complete validated change
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_risk_acceptance_service,
    get_risk_assessment_service,
    get_risk_governance_service,
    get_risk_mitigation_service,
    get_safety_change_approval_service,
    get_safety_change_implementation_service,
    get_safety_change_service,
    get_safety_change_validation_service,
    get_safety_reassessment_service,
    get_safety_rollback_service,
)
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.risk import (
    RiskCloseRequest,
    RiskCreateRequest,
    RiskHistoryEntry,
    RiskRecord,
    RiskReopenRequest,
    RiskReassessRequest,
)
from app.schemas.risk_assessment import (
    RiskAssessmentCreateRequest,
    RiskAssessmentRecord,
)
from app.schemas.risk_mitigation import (
    MitigationCreateRequest,
    MitigationRecord,
)
from app.schemas.safety_approval import (
    RiskAcceptanceRecord,
    RiskAcceptanceRequest,
    SafetyChangeApprovalRecord,
    SafetyChangeApprovalRequest,
)
from app.schemas.safety_change import (
    SafetyChangeCreateRequest,
    SafetyChangeRecord,
)
from app.schemas.safety_governance import (
    ChangeRequestState,
    RiskCategory,
    RiskState,
)
from app.schemas.safety_rollback import (
    SafetyChangeImplementationRecord,
    SafetyChangeImplementationRequest,
    SafetyChangeRollbackRecord,
    SafetyChangeRollbackRequest,
)
from app.schemas.safety_validation import (
    SafetyChangeValidationRecord,
    SafetyChangeValidationRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.risk_acceptance_service import (
    RiskAcceptanceService,
    risk_acceptance_service,
)
from app.services.risk_assessment_service import (
    RiskAssessmentService,
    risk_assessment_service,
)
from app.services.risk_governance_service import (
    RiskGovernanceService,
    risk_governance_service,
)
from app.services.risk_mitigation_service import (
    RiskMitigationService,
    risk_mitigation_service,
)
from app.services.safety_change_approval_service import (
    SafetyChangeApprovalService,
    safety_change_approval_service,
)
from app.services.safety_change_implementation_service import (
    SafetyChangeImplementationService,
    safety_change_implementation_service,
)
from app.services.safety_change_service import (
    SafetyChangeService,
    safety_change_service,
)
from app.services.safety_change_validation_service import (
    SafetyChangeValidationService,
    safety_change_validation_service,
)
from app.services.safety_reassessment_service import (
    SafetyReassessmentService,
    safety_reassessment_service,
)
from app.services.safety_rollback_service import (
    SafetyRollbackService,
    safety_rollback_service,
)

router = APIRouter(prefix="/safety-governance", tags=["Clinical Safety Governance & Controlled Change Management"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


# ===========================================================================
# 1. Risk Registration & Lifecycle Management
# ===========================================================================


@router.post(
    "/risks",
    response_model=StandardSuccessResponse[RiskRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Register Clinical Safety Risk",
    description="Registers a safety finding into the governed risk management lifecycle.",
)
async def register_safety_risk(
    http_request: Request,
    request_body: RiskCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    risk_svc: Annotated[RiskGovernanceService, Depends(get_risk_governance_service)] = None,
) -> StandardSuccessResponse[RiskRecord]:
    svc = risk_svc or risk_governance_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)
    facility_id = getattr(current_user, "facility_id", None)

    risk = await svc.create_risk(
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        facility_id=facility_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=risk, request_id=req_id)


@router.get(
    "/risks",
    response_model=StandardSuccessResponse[List[RiskRecord]],
    summary="List Governed Risks",
    description="List and filter clinical safety risks within the authenticated organization boundary.",
)
async def list_safety_risks(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    category: Optional[RiskCategory] = Query(None),
    state: Optional[RiskState] = Query(None),
    risk_svc: Annotated[RiskGovernanceService, Depends(get_risk_governance_service)] = None,
) -> StandardSuccessResponse[List[RiskRecord]]:
    svc = risk_svc or risk_governance_service
    req_id = _req_id(http_request)
    org_id = getattr(current_user, "organization_id", None)

    risks = svc.list_risks(actor_org_id=org_id, category=category, state=state)
    return StandardSuccessResponse(success=True, data=risks, request_id=req_id)


@router.get(
    "/risks/{risk_id}",
    response_model=StandardSuccessResponse[RiskRecord],
    summary="Get Risk Details",
    description="Retrieve details of a governed clinical safety risk.",
)
async def get_safety_risk(
    http_request: Request,
    risk_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    risk_svc: Annotated[RiskGovernanceService, Depends(get_risk_governance_service)] = None,
) -> StandardSuccessResponse[RiskRecord]:
    svc = risk_svc or risk_governance_service
    req_id = _req_id(http_request)
    org_id = getattr(current_user, "organization_id", None)

    risk = svc.get_risk(risk_id, actor_org_id=org_id)
    return StandardSuccessResponse(success=True, data=risk, request_id=req_id)


@router.get(
    "/risks/{risk_id}/history",
    response_model=StandardSuccessResponse[List[RiskHistoryEntry]],
    summary="Get Risk History",
    description="Retrieve chronological audit history for a risk.",
)
async def get_risk_history(
    http_request: Request,
    risk_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    risk_svc: Annotated[RiskGovernanceService, Depends(get_risk_governance_service)] = None,
) -> StandardSuccessResponse[List[RiskHistoryEntry]]:
    svc = risk_svc or risk_governance_service
    req_id = _req_id(http_request)
    org_id = getattr(current_user, "organization_id", None)

    history = svc.get_risk_history(risk_id, actor_org_id=org_id)
    return StandardSuccessResponse(success=True, data=history, request_id=req_id)


@router.get(
    "/risks/{risk_id}/evidence",
    response_model=StandardSuccessResponse[List[Dict[str, Any]]],
    summary="Get Risk Evidence",
    description="List all attached supporting evidence for a risk.",
)
async def get_risk_evidence(
    http_request: Request,
    risk_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    risk_svc: Annotated[RiskGovernanceService, Depends(get_risk_governance_service)] = None,
) -> StandardSuccessResponse[List[Dict[str, Any]]]:
    svc = risk_svc or risk_governance_service
    req_id = _req_id(http_request)
    org_id = getattr(current_user, "organization_id", None)

    risk = svc.get_risk(risk_id, actor_org_id=org_id)
    return StandardSuccessResponse(success=True, data=risk.evidence_references, request_id=req_id)


@router.get(
    "/risks/{risk_id}/assessments",
    response_model=StandardSuccessResponse[List[RiskAssessmentRecord]],
    summary="Get Risk Assessments",
    description="List all structured assessments performed for a risk.",
)
async def get_risk_assessments(
    http_request: Request,
    risk_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    assessment_svc: Annotated[RiskAssessmentService, Depends(get_risk_assessment_service)] = None,
) -> StandardSuccessResponse[List[RiskAssessmentRecord]]:
    svc = assessment_svc or risk_assessment_service
    req_id = _req_id(http_request)

    assessments = svc.list_assessments(risk_id)
    return StandardSuccessResponse(success=True, data=assessments, request_id=req_id)


@router.post(
    "/risks/{risk_id}/assess",
    response_model=StandardSuccessResponse[RiskAssessmentRecord],
    summary="Conduct Structured Risk Assessment",
    description="Explicitly assesses hazard likelihood, impact, existing controls, and residual risk.",
)
async def assess_safety_risk(
    http_request: Request,
    risk_id: str,
    request_body: RiskAssessmentCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    assessment_svc: Annotated[RiskAssessmentService, Depends(get_risk_assessment_service)] = None,
) -> StandardSuccessResponse[RiskAssessmentRecord]:
    svc = assessment_svc or risk_assessment_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    assessment = await svc.assess_risk(
        risk_id=risk_id,
        request=request_body,
        assessor_id=current_user.user_id,
        assessor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=assessment, request_id=req_id)


@router.post(
    "/risks/{risk_id}/mitigate",
    response_model=StandardSuccessResponse[MitigationRecord],
    summary="Create Risk Mitigation Plan",
    description="Defines an authorized mitigation plan with validation criteria and owner.",
)
async def create_risk_mitigation(
    http_request: Request,
    risk_id: str,
    request_body: MitigationCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    mitigation_svc: Annotated[RiskMitigationService, Depends(get_risk_mitigation_service)] = None,
) -> StandardSuccessResponse[MitigationRecord]:
    svc = mitigation_svc or risk_mitigation_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    mitigation = await svc.create_mitigation(
        risk_id=risk_id,
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=mitigation, request_id=req_id)


@router.post(
    "/risks/{risk_id}/accept",
    response_model=StandardSuccessResponse[RiskAcceptanceRecord],
    summary="Accept Residual Clinical Risk",
    description="Authorized safety authority explicitly accepts residual risk with bounded expiry.",
)
async def accept_safety_risk(
    http_request: Request,
    risk_id: str,
    request_body: RiskAcceptanceRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    acceptance_svc: Annotated[RiskAcceptanceService, Depends(get_risk_acceptance_service)] = None,
) -> StandardSuccessResponse[RiskAcceptanceRecord]:
    svc = acceptance_svc or risk_acceptance_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    acceptance = await svc.accept_risk(
        risk_id=risk_id,
        request=request_body,
        authority_id=current_user.user_id,
        authority_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=acceptance, request_id=req_id)


@router.post(
    "/risks/{risk_id}/reject",
    response_model=StandardSuccessResponse[RiskRecord],
    summary="Reject Proposed Risk",
    description="Formally rejects risk or proposed mitigation, requiring redesign or escalation.",
)
async def reject_safety_risk(
    http_request: Request,
    risk_id: str,
    request_body: Dict[str, str],
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    acceptance_svc: Annotated[RiskAcceptanceService, Depends(get_risk_acceptance_service)] = None,
) -> StandardSuccessResponse[RiskRecord]:
    svc = acceptance_svc or risk_acceptance_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)
    reason = request_body.get("reason", "Risk rejected under governance review")

    risk = await svc.reject_risk(
        risk_id=risk_id,
        reason=reason,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=risk, request_id=req_id)


@router.post(
    "/risks/{risk_id}/reassess",
    response_model=StandardSuccessResponse[RiskRecord],
    summary="Trigger Risk Reassessment",
    description="Triggers formal reassessment upon new incident findings, expired acceptance, or shift in controls.",
)
async def trigger_risk_reassessment(
    http_request: Request,
    risk_id: str,
    request_body: RiskReassessRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    reassess_svc: Annotated[SafetyReassessmentService, Depends(get_safety_reassessment_service)] = None,
) -> StandardSuccessResponse[RiskRecord]:
    svc = reassess_svc or safety_reassessment_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    risk = await svc.trigger_reassessment(
        risk_id=risk_id,
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=risk, request_id=req_id)


@router.post(
    "/risks/{risk_id}/reopen",
    response_model=StandardSuccessResponse[RiskRecord],
    summary="Reopen Closed Risk",
    description="Reopens a closed risk upon recurrence or new evidence while preserving previous history.",
)
async def reopen_safety_risk(
    http_request: Request,
    risk_id: str,
    request_body: RiskReopenRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    risk_svc: Annotated[RiskGovernanceService, Depends(get_risk_governance_service)] = None,
) -> StandardSuccessResponse[RiskRecord]:
    svc = risk_svc or risk_governance_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    risk = await svc.reopen_risk(
        risk_id=risk_id,
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=risk, request_id=req_id)


@router.post(
    "/risks/{risk_id}/close",
    response_model=StandardSuccessResponse[RiskRecord],
    summary="Formally Close Governed Risk",
    description="Closes risk after satisfying all governance prerequisites (assessment, mitigations, changes).",
)
async def close_safety_risk(
    http_request: Request,
    risk_id: str,
    request_body: RiskCloseRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    risk_svc: Annotated[RiskGovernanceService, Depends(get_risk_governance_service)] = None,
) -> StandardSuccessResponse[RiskRecord]:
    svc = risk_svc or risk_governance_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    risk = await svc.close_risk(
        risk_id=risk_id,
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=risk, request_id=req_id)


# ===========================================================================
# 2. Controlled Safety Change Request & Lifecycle Management
# ===========================================================================


@router.get(
    "/change-requests",
    response_model=StandardSuccessResponse[List[SafetyChangeRecord]],
    summary="List Safety Change Requests",
    description="List and filter controlled safety change requests.",
)
async def list_safety_changes(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    risk_id: Optional[str] = Query(None),
    state: Optional[ChangeRequestState] = Query(None),
    change_svc: Annotated[SafetyChangeService, Depends(get_safety_change_service)] = None,
) -> StandardSuccessResponse[List[SafetyChangeRecord]]:
    svc = change_svc or safety_change_service
    req_id = _req_id(http_request)
    org_id = getattr(current_user, "organization_id", None)

    changes = svc.list_changes(risk_id=risk_id, state=state, organization_id=org_id)
    return StandardSuccessResponse(success=True, data=changes, request_id=req_id)


@router.post(
    "/change-requests",
    response_model=StandardSuccessResponse[SafetyChangeRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Safety Change Request",
    description="Initiates a controlled safety change request bound to a governed risk.",
)
async def create_safety_change(
    http_request: Request,
    request_body: SafetyChangeCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    change_svc: Annotated[SafetyChangeService, Depends(get_safety_change_service)] = None,
) -> StandardSuccessResponse[SafetyChangeRecord]:
    svc = change_svc or safety_change_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)
    facility_id = getattr(current_user, "facility_id", None)

    change = await svc.create_change_request(
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        facility_id=facility_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=change, request_id=req_id)


@router.get(
    "/change-requests/{change_id}",
    response_model=StandardSuccessResponse[SafetyChangeRecord],
    summary="Get Safety Change Request Details",
    description="Retrieves details and status of a controlled safety change request.",
)
async def get_safety_change(
    http_request: Request,
    change_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    change_svc: Annotated[SafetyChangeService, Depends(get_safety_change_service)] = None,
) -> StandardSuccessResponse[SafetyChangeRecord]:
    svc = change_svc or safety_change_service
    req_id = _req_id(http_request)
    org_id = getattr(current_user, "organization_id", None)

    change = svc.get_change(change_id, actor_org_id=org_id)
    return StandardSuccessResponse(success=True, data=change, request_id=req_id)


@router.get(
    "/change-requests/{change_id}/history",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get Safety Change Audit History",
    description="Retrieves approvals, implementations, validations, and rollbacks for a change.",
)
async def get_safety_change_history(
    http_request: Request,
    change_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    change_svc: Annotated[SafetyChangeService, Depends(get_safety_change_service)] = None,
) -> StandardSuccessResponse[Dict[str, Any]]:
    svc = change_svc or safety_change_service
    req_id = _req_id(http_request)
    org_id = getattr(current_user, "organization_id", None)

    change = svc.get_change(change_id, actor_org_id=org_id)
    repo = svc.repository

    history_data = {
        "change_id": change.id,
        "current_state": change.state.value,
        "approvals": repo.list_approvals(change.id),
        "implementations": repo.list_implementations(change.id),
        "validations": repo.list_validations(change.id),
        "rollbacks": repo.list_rollbacks(change.id),
    }

    return StandardSuccessResponse(success=True, data=history_data, request_id=req_id)


@router.post(
    "/change-requests/{change_id}/approve",
    response_model=StandardSuccessResponse[SafetyChangeApprovalRecord],
    summary="Approve Safety Change Request",
    description="Explicitly approves or rejects a safety change, binding versions and verifying separation of duties.",
)
async def approve_safety_change(
    http_request: Request,
    change_id: str,
    request_body: SafetyChangeApprovalRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    approval_svc: Annotated[SafetyChangeApprovalService, Depends(get_safety_change_approval_service)] = None,
) -> StandardSuccessResponse[SafetyChangeApprovalRecord]:
    svc = approval_svc or safety_change_approval_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    approval = await svc.approve_change(
        change_id=change_id,
        request=request_body,
        approver_id=current_user.user_id,
        approver_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=approval, request_id=req_id)


@router.post(
    "/change-requests/{change_id}/reject",
    response_model=StandardSuccessResponse[SafetyChangeApprovalRecord],
    summary="Reject Safety Change Request",
    description="Formally rejects a safety change request with reason.",
)
async def reject_safety_change(
    http_request: Request,
    change_id: str,
    request_body: Dict[str, Any],
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    approval_svc: Annotated[SafetyChangeApprovalService, Depends(get_safety_change_approval_service)] = None,
) -> StandardSuccessResponse[SafetyChangeApprovalRecord]:
    svc = approval_svc or safety_change_approval_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    change = svc.repository.get_change(change_id)
    bound_risk_ver = 1
    bound_chg_ver = change.version if change else 1
    if change:
        risk = svc.repository.get_risk(change.risk_id)
        if risk:
            bound_risk_ver = risk.version

    approval_req = SafetyChangeApprovalRequest(
        decision="REJECT",
        notes=request_body.get("reason", "Change rejected by safety governance authority"),
        bound_risk_version=bound_risk_ver,
        bound_change_version=bound_chg_ver,
    )

    approval = await svc.approve_change(
        change_id=change_id,
        request=approval_req,
        approver_id=current_user.user_id,
        approver_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=approval, request_id=req_id)


@router.post(
    "/change-requests/{change_id}/implement",
    response_model=StandardSuccessResponse[SafetyChangeImplementationRecord],
    summary="Implement Approved Safety Change",
    description="Enforces the implementation gate and deploys change via authoritative subsystem.",
)
async def implement_safety_change(
    http_request: Request,
    change_id: str,
    request_body: SafetyChangeImplementationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    impl_svc: Annotated[SafetyChangeImplementationService, Depends(get_safety_change_implementation_service)] = None,
) -> StandardSuccessResponse[SafetyChangeImplementationRecord]:
    svc = impl_svc or safety_change_implementation_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    impl = await svc.implement_change(
        change_id=change_id,
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=impl, request_id=req_id)


@router.post(
    "/change-requests/{change_id}/validate",
    response_model=StandardSuccessResponse[SafetyChangeValidationRecord],
    summary="Validate Implemented Safety Change",
    description="Verifies empirical clinical safety and records validation outcome.",
)
async def validate_safety_change(
    http_request: Request,
    change_id: str,
    request_body: SafetyChangeValidationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    validation_svc: Annotated[SafetyChangeValidationService, Depends(get_safety_change_validation_service)] = None,
) -> StandardSuccessResponse[SafetyChangeValidationRecord]:
    svc = validation_svc or safety_change_validation_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    val = await svc.validate_change(
        change_id=change_id,
        request=request_body,
        validator_id=current_user.user_id,
        validator_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=val, request_id=req_id)


@router.post(
    "/change-requests/{change_id}/rollback",
    response_model=StandardSuccessResponse[SafetyChangeRollbackRecord],
    summary="Rollback Safety Change",
    description="Executes a controlled rollback to restore previous verified safety baseline without history deletion.",
)
async def rollback_safety_change(
    http_request: Request,
    change_id: str,
    request_body: SafetyChangeRollbackRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    rollback_svc: Annotated[SafetyRollbackService, Depends(get_safety_rollback_service)] = None,
) -> StandardSuccessResponse[SafetyChangeRollbackRecord]:
    svc = rollback_svc or safety_rollback_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)

    rbk = await svc.rollback_change(
        change_id=change_id,
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(success=True, data=rbk, request_id=req_id)


@router.post(
    "/change-requests/{change_id}/close",
    response_model=StandardSuccessResponse[SafetyChangeRecord],
    summary="Formally Complete Safety Change",
    description="Marks a validated and monitored safety change COMPLETED.",
)
async def close_safety_change(
    http_request: Request,
    change_id: str,
    request_body: Dict[str, str],
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    change_svc: Annotated[SafetyChangeService, Depends(get_safety_change_service)] = None,
) -> StandardSuccessResponse[SafetyChangeRecord]:
    svc = change_svc or safety_change_service
    req_id = _req_id(http_request)
    user_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    org_id = getattr(current_user, "organization_id", None)
    reason = request_body.get("reason", "Safety change completed and verified")

    change = await svc.close_change(
        change_id=change_id,
        reason=reason,
        actor_id=current_user.user_id,
        actor_role=user_role,
        organization_id=org_id,
    )

    return StandardSuccessResponse(success=True, data=change, request_id=req_id)

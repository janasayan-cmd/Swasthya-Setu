"""Phase 72: Clinical Safety Governance Management Review REST API Endpoints.

Provides comprehensive HTTP APIs for:
- Management review programmes and operational reviews
- Participant invitations, attendance confirmations, and authority validation
- Agenda items, input collection from Phases 49-71, and review package compilation
- Discussion minutes and authoritative decision recording
- Actionable commitment tracking, verification, and leadership escalation
- Comprehensive review reports, closure gating, and executive review intelligence

Base Path: /api/v1/governance-management-reviews
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.management_review_programme import (
    ApproveReviewProgrammeRequest,
    CreateReviewProgrammeRequest,
    ManagementReviewProgrammeRecord,
    UpdateReviewProgrammeRequest,
)
from app.schemas.management_review_scheduling import (
    AddParticipantRequest,
    CancelReviewRequest,
    ConfirmAttendanceRequest,
    CreateManagementReviewRequest,
    ManagementReviewRecord,
    RescheduleReviewRequest,
    ReviewParticipantRecord,
    ScheduleReviewRequest,
    UpdateManagementReviewRequest,
    UpdateParticipantRequest,
)
from app.schemas.management_review_agenda import (
    CollectInputsRequest,
    ConsolidatedInputRecord,
    CreateAgendaItemRequest,
    GenerateReviewPackageRequest,
    ReadinessCheckResponse,
    ReviewAgendaItemRecord,
    ReviewPackageRecord,
    UpdateAgendaItemRequest,
)
from app.schemas.management_review_decisions import (
    ApproveDecisionRequest,
    CommitmentEscalationRecord,
    CreateDiscussionRecordRequest,
    CreateManagementCommitmentRequest,
    CreateManagementDecisionRequest,
    DeferDecisionRequest,
    DiscussionRecord,
    EscalateCommitmentRequest,
    ManagementCommitmentRecord,
    ManagementDecisionRecord,
    SubmitCommitmentVerificationRequest,
    SupersedeDecisionRequest,
    UpdateCommitmentProgressRequest,
    VerifyCommitmentRequest,
)
from app.schemas.management_review_reports_analytics import (
    ApproveReviewReportRequest,
    CloseManagementReviewRequest,
    GenerateManagementReviewReportRequest,
    ManagementReviewAnalyticsResponse,
    ManagementReviewReportRecord,
    ReopenManagementReviewRequest,
    ReviewClosureCheckResponse,
)
from app.services.management_review_programme_service import (
    ManagementReviewProgrammeService,
)
from app.services.management_review_scheduling_service import (
    ManagementReviewSchedulingService,
)
from app.services.management_review_agenda_service import (
    ManagementReviewAgendaService,
)
from app.services.management_review_decision_service import (
    ManagementReviewDecisionService,
)
from app.services.management_review_closure_service import (
    ManagementReviewClosureService,
)

router = APIRouter(
    prefix="/governance-management-reviews",
    tags=["Phase 72 - Clinical Safety Governance Management Reviews"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforce that patient role cannot access management review governance endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access clinical safety governance management review features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _get_services():
    return (
        ManagementReviewProgrammeService(),
        ManagementReviewSchedulingService(),
        ManagementReviewAgendaService(),
        ManagementReviewDecisionService(),
        ManagementReviewClosureService(),
    )


# =============================================================================
# 1. ANALYTICS & METRICS
# =============================================================================

@router.get(
    "/analytics/overview",
    response_model=ManagementReviewAnalyticsResponse,
    summary="Get executive management review metrics and governance analytics",
)
def get_analytics_overview(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewAnalyticsResponse:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.get_analytics_overview(current_user.organization_id)


# =============================================================================
# 2. MANAGEMENT REVIEW PROGRAMMES
# =============================================================================

@router.post(
    "/programmes",
    response_model=ManagementReviewProgrammeRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new management review programme",
)
def create_programme(
    request: CreateReviewProgrammeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewProgrammeRecord:
    _ensure_not_patient(current_user)
    prog_svc, _, _, _, _ = _get_services()
    return prog_svc.create_programme(
        request=request,
        creator_id=str(current_user.user_id),
        creator_role=str(current_user.role.value if hasattr(current_user.role, "value") else current_user.role),
        organization_id=current_user.organization_id,
    )


@router.get(
    "/programmes",
    response_model=List[ManagementReviewProgrammeRecord],
    summary="List management review programmes for tenant",
)
def list_programmes(
    facility_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ManagementReviewProgrammeRecord]:
    _ensure_not_patient(current_user)
    prog_svc, _, _, _, _ = _get_services()
    return prog_svc.list_programmes(
        organization_id=current_user.organization_id,
        facility_id=facility_id,
        status_filter=status_filter,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/programmes/{programme_id}",
    response_model=ManagementReviewProgrammeRecord,
    summary="Get a management review programme by ID",
)
def get_programme(
    programme_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewProgrammeRecord:
    _ensure_not_patient(current_user)
    prog_svc, _, _, _, _ = _get_services()
    return prog_svc.get_programme(programme_id)


@router.put(
    "/programmes/{programme_id}",
    response_model=ManagementReviewProgrammeRecord,
    summary="Update an existing management review programme",
)
def update_programme(
    programme_id: str,
    request: UpdateReviewProgrammeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewProgrammeRecord:
    _ensure_not_patient(current_user)
    prog_svc, _, _, _, _ = _get_services()
    return prog_svc.update_programme(
        programme_id=programme_id,
        request=request,
        updater_id=str(current_user.user_id),
    )


@router.post(
    "/programmes/{programme_id}/approve",
    response_model=ManagementReviewProgrammeRecord,
    summary="Formally approve and activate a review programme",
)
def approve_programme(
    programme_id: str,
    request: ApproveReviewProgrammeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewProgrammeRecord:
    _ensure_not_patient(current_user)
    prog_svc, _, _, _, _ = _get_services()
    return prog_svc.approve_programme(
        programme_id=programme_id,
        request=request,
        approver_id=str(current_user.user_id),
    )


# =============================================================================
# 3. MANAGEMENT REVIEWS (MEETINGS) & LIFECYCLE
# =============================================================================

@router.post(
    "/reviews",
    response_model=ManagementReviewRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a management review meeting under a programme",
)
def create_review(
    request: CreateManagementReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.create_review(
        request=request,
        creator_id=str(current_user.user_id),
        organization_id=current_user.organization_id,
    )


@router.get(
    "/reviews",
    response_model=List[ManagementReviewRecord],
    summary="List reviews filtered by programme or status",
)
def list_reviews(
    facility_id: Optional[str] = Query(None),
    programme_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ManagementReviewRecord]:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.list_reviews(
        organization_id=current_user.organization_id,
        facility_id=facility_id,
        programme_id=programme_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/reviews/{review_id}",
    response_model=ManagementReviewRecord,
    summary="Get details of a review meeting",
)
def get_review(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.get_review(review_id)


@router.put(
    "/reviews/{review_id}",
    response_model=ManagementReviewRecord,
    summary="Update review meeting parameters",
)
def update_review(
    review_id: str,
    request: UpdateManagementReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.update_review(review_id=review_id, request=request)


@router.post(
    "/reviews/{review_id}/schedule",
    response_model=ManagementReviewRecord,
    summary="Advance review meeting status to SCHEDULED",
)
def schedule_review(
    review_id: str,
    request: ScheduleReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.schedule_review(review_id=review_id, request=request)


@router.post(
    "/reviews/{review_id}/reschedule",
    response_model=ManagementReviewRecord,
    summary="Reschedule or postpone a review meeting",
)
def reschedule_review(
    review_id: str,
    request: RescheduleReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.reschedule_review(review_id=review_id, request=request)


@router.post(
    "/reviews/{review_id}/cancel",
    response_model=ManagementReviewRecord,
    summary="Cancel a review meeting",
)
def cancel_review(
    review_id: str,
    request: CancelReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.cancel_review(review_id=review_id, request=request)


@router.post(
    "/reviews/{review_id}/start",
    response_model=ManagementReviewRecord,
    summary="Start review meeting, moving status to IN_PROGRESS",
)
def start_review(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.start_review(review_id=review_id)


@router.get(
    "/reviews/{review_id}/readiness",
    response_model=ReadinessCheckResponse,
    summary="Evaluate meeting prerequisites, quorum, and readiness",
)
def validate_readiness(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReadinessCheckResponse:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.validate_readiness(review_id=review_id)


@router.get(
    "/reviews/{review_id}/closure-check",
    response_model=ReviewClosureCheckResponse,
    summary="Check conditions and blockers for closing a review",
)
def check_closure_readiness(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewClosureCheckResponse:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.check_closure_readiness(review_id=review_id)


@router.post(
    "/reviews/{review_id}/close",
    response_model=ManagementReviewRecord,
    summary="Close review meeting after verifying all closure criteria",
)
def close_review(
    review_id: str,
    request: CloseManagementReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.close_review(
        review_id=review_id,
        request=request,
        closer_id=str(current_user.user_id),
    )


@router.post(
    "/reviews/{review_id}/reopen",
    response_model=ManagementReviewRecord,
    summary="Reopen a completed review for additional follow-through",
)
def reopen_review(
    review_id: str,
    request: ReopenManagementReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.reopen_review(review_id=review_id, request=request)


# =============================================================================
# 4. REVIEW PARTICIPANTS & ATTENDANCE
# =============================================================================

@router.post(
    "/reviews/{review_id}/participants",
    response_model=ReviewParticipantRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add or invite a participant to a review meeting",
)
def add_participant(
    review_id: str,
    request: AddParticipantRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewParticipantRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.add_participant(review_id=review_id, request=request)


@router.get(
    "/reviews/{review_id}/participants",
    response_model=List[ReviewParticipantRecord],
    summary="List all participants registered for a review",
)
def list_participants(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ReviewParticipantRecord]:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.list_participants(review_id=review_id)


@router.get(
    "/participants/{participant_id}",
    response_model=ReviewParticipantRecord,
    summary="Get single participant record",
)
def get_participant(
    participant_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewParticipantRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.get_participant(participant_id=participant_id)


@router.put(
    "/participants/{participant_id}",
    response_model=ReviewParticipantRecord,
    summary="Update participant role, authority, or conflict declarations",
)
def update_participant(
    participant_id: str,
    request: UpdateParticipantRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewParticipantRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.update_participant(participant_id=participant_id, request=request)


@router.post(
    "/reviews/{review_id}/confirm-attendance",
    response_model=ReviewParticipantRecord,
    summary="Confirm attendance and record conflict declarations for review",
)
def confirm_attendance(
    review_id: str,
    request: ConfirmAttendanceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewParticipantRecord:
    _ensure_not_patient(current_user)
    _, sched_svc, _, _, _ = _get_services()
    return sched_svc.confirm_attendance(
        review_id=review_id,
        user_id=str(current_user.user_id),
        request=request,
    )


# =============================================================================
# 5. AGENDA ITEMS & CROSS-PHASE INPUT CONSOLIDATION
# =============================================================================

@router.post(
    "/reviews/{review_id}/agenda-items",
    response_model=ReviewAgendaItemRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add an agenda topic to a review meeting",
)
def create_agenda_item(
    review_id: str,
    request: CreateAgendaItemRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewAgendaItemRecord:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.create_agenda_item(review_id=review_id, request=request)


@router.get(
    "/reviews/{review_id}/agenda-items",
    response_model=List[ReviewAgendaItemRecord],
    summary="List agenda items for a review meeting",
)
def list_agenda_items(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ReviewAgendaItemRecord]:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.list_agenda_items(review_id=review_id)


@router.get(
    "/agenda-items/{agenda_item_id}",
    response_model=ReviewAgendaItemRecord,
    summary="Get single agenda item",
)
def get_agenda_item(
    agenda_item_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewAgendaItemRecord:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.get_agenda_item(agenda_item_id=agenda_item_id)


@router.put(
    "/agenda-items/{agenda_item_id}",
    response_model=ReviewAgendaItemRecord,
    summary="Update agenda topic properties or discussion status",
)
def update_agenda_item(
    agenda_item_id: str,
    request: UpdateAgendaItemRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewAgendaItemRecord:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.update_agenda_item(agenda_item_id=agenda_item_id, request=request)


@router.delete(
    "/agenda-items/{agenda_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agenda item",
)
def delete_agenda_item(
    agenda_item_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    agenda_svc.delete_agenda_item(agenda_item_id=agenda_item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/reviews/{review_id}/inputs/collect",
    response_model=ConsolidatedInputRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Index evidence/input from upstream governance phases (Phases 49-71)",
)
def collect_inputs(
    review_id: str,
    request: CollectInputsRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ConsolidatedInputRecord:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.collect_inputs(
        review_id=review_id,
        request=request,
        collector_id=str(current_user.user_id),
    )


@router.get(
    "/reviews/{review_id}/inputs",
    response_model=List[ConsolidatedInputRecord],
    summary="List consolidated inputs gathered for a review",
)
def list_consolidated_inputs(
    review_id: str,
    source_phase: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ConsolidatedInputRecord]:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.list_consolidated_inputs(review_id=review_id, source_phase=source_phase)


# =============================================================================
# 6. REVIEW PACKAGES
# =============================================================================

@router.post(
    "/reviews/{review_id}/packages/generate",
    response_model=ReviewPackageRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Compile reproducible review package from current agenda and inputs",
)
def generate_review_package(
    review_id: str,
    request: GenerateReviewPackageRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewPackageRecord:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.generate_package(
        review_id=review_id,
        request=request,
        compiler_id=str(current_user.user_id),
    )


@router.get(
    "/reviews/{review_id}/packages",
    response_model=List[ReviewPackageRecord],
    summary="List review package versions for a review meeting",
)
def list_review_packages(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ReviewPackageRecord]:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.list_packages(review_id=review_id)


@router.get(
    "/packages/{package_id}",
    response_model=ReviewPackageRecord,
    summary="Get a review package by ID",
)
def get_review_package(
    package_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewPackageRecord:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.get_package(package_id=package_id)


@router.post(
    "/packages/{package_id}/lock",
    response_model=ReviewPackageRecord,
    summary="Lock a review package against further changes",
)
def lock_review_package(
    package_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewPackageRecord:
    _ensure_not_patient(current_user)
    _, _, agenda_svc, _, _ = _get_services()
    return agenda_svc.lock_package(
        package_id=package_id, locker_id=str(current_user.user_id)
    )


# =============================================================================
# 7. MEETING DISCUSSIONS & MINUTES
# =============================================================================

@router.post(
    "/reviews/{review_id}/discussions",
    response_model=DiscussionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record meeting discussion notes or minute points",
)
def record_discussion(
    review_id: str,
    request: CreateDiscussionRecordRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DiscussionRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.record_discussion(
        review_id=review_id,
        request=request,
        speaker_id=str(current_user.user_id),
    )


@router.get(
    "/reviews/{review_id}/discussions",
    response_model=List[DiscussionRecord],
    summary="List discussion records for a review meeting",
)
def list_discussions(
    review_id: str,
    agenda_item_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[DiscussionRecord]:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.list_discussions(review_id=review_id, agenda_item_id=agenda_item_id)


# =============================================================================
# 8. MANAGEMENT DECISIONS & AUTHORIZATION
# =============================================================================

@router.post(
    "/reviews/{review_id}/decisions",
    response_model=ManagementDecisionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record an authoritative management decision, validating decision authority",
)
def record_decision(
    review_id: str,
    request: CreateManagementDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementDecisionRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    role_str = str(current_user.role.value if hasattr(current_user.role, "value") else current_user.role)
    return decision_svc.record_decision(
        review_id=review_id,
        request=request,
        decider_id=str(current_user.user_id),
        decider_role=role_str,
        organization_id=current_user.organization_id,
    )


@router.get(
    "/decisions",
    response_model=List[ManagementDecisionRecord],
    summary="List management decisions",
)
def list_decisions(
    review_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ManagementDecisionRecord]:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.list_decisions(
        review_id=review_id,
        organization_id=current_user.organization_id,
        status_filter=status_filter,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/decisions/{decision_id}",
    response_model=ManagementDecisionRecord,
    summary="Get single management decision by ID",
)
def get_decision(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementDecisionRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.get_decision(decision_id=decision_id)


@router.post(
    "/decisions/{decision_id}/approve",
    response_model=ManagementDecisionRecord,
    summary="Approve a proposed decision",
)
def approve_decision(
    decision_id: str,
    request: ApproveDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementDecisionRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.approve_decision(decision_id=decision_id, request=request)


@router.post(
    "/decisions/{decision_id}/defer",
    response_model=ManagementDecisionRecord,
    summary="Defer a decision for subsequent review",
)
def defer_decision(
    decision_id: str,
    request: DeferDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementDecisionRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.defer_decision(decision_id=decision_id, request=request)


@router.post(
    "/decisions/{decision_id}/supersede",
    response_model=ManagementDecisionRecord,
    summary="Supersede an existing decision",
)
def supersede_decision(
    decision_id: str,
    request: SupersedeDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementDecisionRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.supersede_decision(decision_id=decision_id, request=request)


# =============================================================================
# 9. MANAGEMENT COMMITMENTS & ESCALATIONS
# =============================================================================

@router.post(
    "/commitments",
    response_model=ManagementCommitmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create an actionable follow-through commitment linked to a decision",
)
def create_commitment(
    request: CreateManagementCommitmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementCommitmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.create_commitment(request=request)


@router.get(
    "/commitments",
    response_model=List[ManagementCommitmentRecord],
    summary="List commitments with filters",
)
def list_commitments(
    review_id: Optional[str] = Query(None),
    decision_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_overdue: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ManagementCommitmentRecord]:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.list_commitments(
        review_id=review_id,
        decision_id=decision_id,
        owner_id=owner_id,
        status_filter=status_filter,
        is_overdue=is_overdue,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/commitments/{commitment_id}",
    response_model=ManagementCommitmentRecord,
    summary="Get single commitment by ID",
)
def get_commitment(
    commitment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementCommitmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.get_commitment(commitment_id=commitment_id)


@router.post(
    "/commitments/{commitment_id}/progress",
    response_model=ManagementCommitmentRecord,
    summary="Record progress and implementation notes on a commitment",
)
def update_commitment_progress(
    commitment_id: str,
    request: UpdateCommitmentProgressRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementCommitmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.update_commitment_progress(
        commitment_id=commitment_id,
        request=request,
        updater_id=str(current_user.user_id),
    )


@router.post(
    "/commitments/{commitment_id}/submit-verification",
    response_model=ManagementCommitmentRecord,
    summary="Submit commitment for formal verification of completion",
)
def submit_commitment_verification(
    commitment_id: str,
    request: SubmitCommitmentVerificationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementCommitmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.submit_verification(commitment_id=commitment_id, request=request)


@router.post(
    "/commitments/{commitment_id}/verify",
    response_model=ManagementCommitmentRecord,
    summary="Verify or reject completed implementation of a commitment",
)
def verify_commitment(
    commitment_id: str,
    request: VerifyCommitmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementCommitmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.verify_commitment(
        commitment_id=commitment_id,
        request=request,
        verifier_id=str(current_user.user_id),
    )


@router.post(
    "/commitments/{commitment_id}/escalate",
    response_model=CommitmentEscalationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Escalate an overdue or blocked commitment to executive leadership",
)
def escalate_commitment(
    commitment_id: str,
    request: EscalateCommitmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CommitmentEscalationRecord:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.escalate_commitment(
        commitment_id=commitment_id,
        request=request,
        escalator_id=str(current_user.user_id),
    )


@router.get(
    "/commitments/{commitment_id}/escalations",
    response_model=List[CommitmentEscalationRecord],
    summary="List escalations for a commitment",
)
def list_commitment_escalations(
    commitment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[CommitmentEscalationRecord]:
    _ensure_not_patient(current_user)
    _, _, _, decision_svc, _ = _get_services()
    return decision_svc.list_escalations(commitment_id=commitment_id)


# =============================================================================
# 10. MANAGEMENT REVIEW REPORTS & PREVIOUS DECISION RECONCILIATION
# =============================================================================

@router.post(
    "/reviews/{review_id}/reports/generate",
    response_model=ManagementReviewReportRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a formal management review summary report from review artifacts",
)
def generate_review_report(
    review_id: str,
    request: GenerateManagementReviewReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewReportRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.generate_report(
        review_id=review_id,
        request=request,
        preparer_id=str(current_user.user_id),
    )


@router.get(
    "/reviews/{review_id}/reports",
    response_model=ManagementReviewReportRecord,
    summary="Get report for a management review",
)
def get_report_by_review(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewReportRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.get_report_by_review(review_id=review_id)


@router.get(
    "/reports/{report_id}",
    response_model=ManagementReviewReportRecord,
    summary="Get management review report by ID",
)
def get_report(
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewReportRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.get_report(report_id=report_id)


@router.post(
    "/reports/{report_id}/approve",
    response_model=ManagementReviewReportRecord,
    summary="Formally approve a management review report",
)
def approve_report(
    report_id: str,
    request: ApproveReviewReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewReportRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.approve_report(
        report_id=report_id,
        request=request,
        approver_id=str(current_user.user_id),
    )


@router.post(
    "/reports/{report_id}/finalize",
    response_model=ManagementReviewReportRecord,
    summary="Finalize and lock an approved management review report",
)
def finalize_report(
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ManagementReviewReportRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.finalize_report(
        report_id=report_id,
        finalizer_id=str(current_user.user_id),
    )


@router.get(
    "/reviews/{review_id}/reconcile-previous",
    response_model=List[Dict[str, Any]],
    summary="Reconcile decisions and commitments from previous reviews under the same programme",
)
def reconcile_previous_decisions(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    _ensure_not_patient(current_user)
    _, _, _, _, closure_svc = _get_services()
    return closure_svc.reconcile_previous_decisions(review_id=review_id)

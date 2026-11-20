"""Phase 72: Clinical Safety Governance Management Review Scheduling & Participant Service.

Handles:
- Management review meeting lifecycle management
- Scheduling, rescheduling, postponement, and cancellation
- Participant roster management, attendance tracking, and conflict declarations
- Meeting readiness evaluation and quorum verification
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_management_review_repository import (
    GovernanceManagementReviewRepository,
    get_governance_management_review_repository,
)
from app.schemas.management_review_programme import ReviewProgrammeStatus
from app.schemas.management_review_scheduling import (
    AddParticipantRequest,
    AttendanceStatus,
    CancelReviewRequest,
    ConfirmAttendanceRequest,
    CreateManagementReviewRequest,
    ManagementReviewRecord,
    ManagementReviewStatus,
    ParticipantRole,
    RescheduleReviewRequest,
    ReviewParticipantRecord,
    ScheduleReviewRequest,
    UpdateManagementReviewRequest,
    UpdateParticipantRequest,
)
from app.schemas.management_review_agenda import (
    ReadinessCheckResponse,
    ReadinessOutcome,
)


class ManagementReviewSchedulingService:
    """Service governing management review meeting scheduling and attendance."""

    def __init__(
        self, repository: Optional[GovernanceManagementReviewRepository] = None
    ) -> None:
        self.repository = repository or get_governance_management_review_repository()

    # -------------------------------------------------------------------------
    # Review Meeting Lifecycle
    # -------------------------------------------------------------------------

    def create_review(
        self,
        request: CreateManagementReviewRequest,
        creator_id: str,
        organization_id: str,
    ) -> ManagementReviewRecord:
        """Initializes a new management review under an existing programme."""
        programme = self.repository.get_programme(request.programme_id)
        if not programme:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_PROGRAMME_NOT_FOUND,
                message=f"Management review programme '{request.programme_id}' not found.",
            )

        review = ManagementReviewRecord(
            programme_id=request.programme_id,
            title=request.title,
            objectives=request.objectives or [],
            status=ManagementReviewStatus.DRAFT,
            planned_date=request.planned_date,
            time_zone=request.time_zone or "UTC",
            duration_minutes=request.duration_minutes or 60,
            chairperson_id=request.chairperson_id,
            meeting_owner_id=creator_id,
            agenda_preparation_deadline=request.agenda_preparation_deadline,
            evidence_preparation_deadline=request.evidence_preparation_deadline,
            organization_id=organization_id,
            facility_id=request.facility_id or programme.facility_id,
            created_by=creator_id,
            metadata=request.metadata or {},
        )
        saved_review = self.repository.save_review(review)

        # If chairperson was designated at creation, add as participant
        if request.chairperson_id:
            chair_participant = ReviewParticipantRecord(
                review_id=saved_review.review_id,
                user_id=request.chairperson_id,
                role=ParticipantRole.CHAIRPERSON,
                has_decision_authority=True,
            )
            self.repository.save_participant(chair_participant)

        return saved_review

    def get_review(self, review_id: str) -> ManagementReviewRecord:
        """Retrieves an existing review meeting record."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )
        return review

    def list_reviews(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        programme_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementReviewRecord]:
        """Lists reviews filtered by tenant and optional parameters."""
        return self.repository.list_reviews(
            organization_id=organization_id,
            facility_id=facility_id,
            programme_id=programme_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

    def update_review(
        self,
        review_id: str,
        request: UpdateManagementReviewRequest,
    ) -> ManagementReviewRecord:
        """Updates basic review details."""
        review = self.get_review(review_id)
        if review.status in [
            ManagementReviewStatus.COMPLETED,
            ManagementReviewStatus.CANCELLED,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot modify review in status '{review.status.value}'.",
            )

        if request.title is not None:
            review.title = request.title
        if request.objectives is not None:
            review.objectives = request.objectives
        if request.planned_date is not None:
            review.planned_date = request.planned_date
        if request.duration_minutes is not None:
            review.duration_minutes = request.duration_minutes
        if request.chairperson_id is not None:
            review.chairperson_id = request.chairperson_id
        if request.metadata is not None:
            review.metadata.update(request.metadata)

        return self.repository.save_review(review)

    def schedule_review(
        self, review_id: str, request: ScheduleReviewRequest
    ) -> ManagementReviewRecord:
        """Advances review status to SCHEDULED."""
        review = self.get_review(review_id)
        if review.status not in [
            ManagementReviewStatus.DRAFT,
            ManagementReviewStatus.APPROVED,
            ManagementReviewStatus.PREPARATION,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot schedule review from current status '{review.status.value}'.",
            )

        review.planned_date = request.planned_date
        review.chairperson_id = request.chairperson_id
        review.status = ManagementReviewStatus.SCHEDULED
        if request.notes:
            review.metadata["scheduling_notes"] = request.notes

        return self.repository.save_review(review)

    def reschedule_review(
        self, review_id: str, request: RescheduleReviewRequest
    ) -> ManagementReviewRecord:
        """Postpones or reschedules an existing review meeting."""
        review = self.get_review(review_id)
        if review.status in [
            ManagementReviewStatus.COMPLETED,
            ManagementReviewStatus.CANCELLED,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot reschedule review in terminal status '{review.status.value}'.",
            )

        review.planned_date = request.new_planned_date
        review.rescheduled_reason = request.rescheduled_reason
        review.metadata["last_rescheduled_at"] = datetime.now(timezone.utc).isoformat()
        return self.repository.save_review(review)

    def cancel_review(
        self, review_id: str, request: CancelReviewRequest
    ) -> ManagementReviewRecord:
        """Cancels a scheduled or draft review."""
        review = self.get_review(review_id)
        if review.status == ManagementReviewStatus.COMPLETED:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message="Cannot cancel an already completed review.",
            )

        review.status = ManagementReviewStatus.CANCELLED
        review.cancellation_reason = request.cancellation_reason
        return self.repository.save_review(review)

    def start_review(self, review_id: str) -> ManagementReviewRecord:
        """Transitions review meeting to IN_PROGRESS."""
        review = self.get_review(review_id)
        if review.status not in [
            ManagementReviewStatus.DRAFT,
            ManagementReviewStatus.SCHEDULED,
            ManagementReviewStatus.READY_FOR_REVIEW,
            ManagementReviewStatus.PREPARATION,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot start review from status '{review.status.value}'.",
            )

        review.status = ManagementReviewStatus.IN_PROGRESS
        review.actual_start_time = datetime.now(timezone.utc)
        return self.repository.save_review(review)

    # -------------------------------------------------------------------------
    # Participants & Decision Authorities
    # -------------------------------------------------------------------------

    def add_participant(
        self, review_id: str, request: AddParticipantRequest
    ) -> ReviewParticipantRecord:
        """Adds or invites a participant to the review meeting."""
        review = self.get_review(review_id)
        if review.status in [
            ManagementReviewStatus.COMPLETED,
            ManagementReviewStatus.CANCELLED,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message="Cannot add participants to a completed or cancelled review.",
            )

        existing = self.repository.find_participant_by_user(review_id, request.user_id)
        if existing:
            # Update role and authority
            existing.role = request.role
            if request.has_decision_authority is not None:
                existing.has_decision_authority = request.has_decision_authority
            if request.user_name:
                existing.user_name = request.user_name
            return self.repository.save_participant(existing)

        participant = ReviewParticipantRecord(
            review_id=review_id,
            user_id=request.user_id,
            user_name=request.user_name,
            role=request.role,
            has_decision_authority=bool(request.has_decision_authority),
            delegated_from_id=request.delegated_from_id,
            conflict_declared=bool(request.conflict_declared),
            conflict_details=request.conflict_details,
            metadata=request.metadata or {},
        )
        return self.repository.save_participant(participant)

    def list_participants(self, review_id: str) -> List[ReviewParticipantRecord]:
        """Lists all participants registered for a review."""
        self.get_review(review_id)
        return self.repository.list_participants(review_id)

    def get_participant(self, participant_id: str) -> ReviewParticipantRecord:
        """Retrieves a single participant record."""
        part = self.repository.get_participant(participant_id)
        if not part:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.REVIEW_PARTICIPANT_NOT_FOUND,
                message=f"Participant record '{participant_id}' not found.",
            )
        return part

    def update_participant(
        self, participant_id: str, request: UpdateParticipantRequest
    ) -> ReviewParticipantRecord:
        """Updates participant details, authority, or conflict declarations."""
        part = self.get_participant(participant_id)
        if request.role is not None:
            part.role = request.role
        if request.has_decision_authority is not None:
            part.has_decision_authority = request.has_decision_authority
        if request.conflict_declared is not None:
            part.conflict_declared = request.conflict_declared
        if request.conflict_details is not None:
            part.conflict_details = request.conflict_details

        return self.repository.save_participant(part)

    def confirm_attendance(
        self, review_id: str, user_id: str, request: ConfirmAttendanceRequest
    ) -> ReviewParticipantRecord:
        """Confirms attendance and records any conflict declarations."""
        self.get_review(review_id)
        part = self.repository.find_participant_by_user(review_id, user_id)
        if not part:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.REVIEW_PARTICIPANT_NOT_FOUND,
                message=f"User '{user_id}' is not an invited participant of review '{review_id}'.",
            )

        part.attendance_status = request.attendance_status
        part.attendance_confirmed_at = datetime.now(timezone.utc)
        if request.conflict_declared is not None:
            part.conflict_declared = request.conflict_declared
        if request.conflict_details is not None:
            part.conflict_details = request.conflict_details

        return self.repository.save_participant(part)

    # -------------------------------------------------------------------------
    # Readiness Evaluation
    # -------------------------------------------------------------------------

    def validate_readiness(self, review_id: str) -> ReadinessCheckResponse:
        """Evaluates whether all prerequisites for the review meeting are met."""
        review = self.get_review(review_id)
        programme = self.repository.get_programme(review.programme_id)
        participants = self.repository.list_participants(review_id)
        agenda_items = self.repository.list_agenda_items(review_id)
        packages = self.repository.list_packages(review_id)

        checks = {
            "programme_approved": bool(
                programme and programme.status == ReviewProgrammeStatus.APPROVED
            ),
            "chairperson_assigned": bool(review.chairperson_id),
            "decision_maker_present": any(
                p.has_decision_authority
                for p in participants
                if p.attendance_status in [AttendanceStatus.CONFIRMED, AttendanceStatus.ATTENDED, AttendanceStatus.INVITED]
            ),
            "quorum_participants": len(participants) >= 2,
            "agenda_defined": len(agenda_items) > 0,
            "package_available": len(packages) > 0,
        }

        deficiencies = []
        recommendations = []

        if not checks["programme_approved"]:
            deficiencies.append("Review programme is not yet formally approved.")
        if not checks["chairperson_assigned"]:
            deficiencies.append("No chairperson assigned to lead the review.")
        if not checks["decision_maker_present"]:
            deficiencies.append("No participant with formal decision authority is assigned.")
        if not checks["quorum_participants"]:
            deficiencies.append("Minimum quorum of 2 participants not met.")
        if not checks["agenda_defined"]:
            deficiencies.append("No agenda items defined for this review.")
        if not checks["package_available"]:
            recommendations.append("Compiled review package not yet generated.")

        # Determine outcome
        if not checks["programme_approved"] or not checks["chairperson_assigned"] or not checks["agenda_defined"]:
            outcome = ReadinessOutcome.NOT_READY
            is_ready = False
        elif deficiencies:
            outcome = ReadinessOutcome.READY_WITH_LIMITATIONS
            is_ready = True
        else:
            outcome = ReadinessOutcome.READY
            is_ready = True

        # If fully ready or ready with limitations, advance status to READY_FOR_REVIEW if currently SCHEDULED
        if is_ready and review.status in [ManagementReviewStatus.SCHEDULED, ManagementReviewStatus.PREPARATION]:
            review.status = ManagementReviewStatus.READY_FOR_REVIEW
            self.repository.save_review(review)

        return ReadinessCheckResponse(
            review_id=review_id,
            outcome=outcome,
            is_ready=is_ready,
            checks=checks,
            deficiencies=deficiencies,
            recommendations=recommendations,
        )

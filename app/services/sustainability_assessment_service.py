"""Phase 74: Operational Sustainability Assessment Service.

Coordinates:
- Multi-dimensional sustainability evaluations across operational scopes
- Assessment submission and approval lifecycle
- Strict Clinical Safety Boundary: Operational sustainability does not replace Phase 55 clinical effectiveness
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_adoption_repository import (
    GovernanceChangeAdoptionRepository,
    get_governance_change_adoption_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.drift_sustainability_consequences import (
    ApproveSustainabilityAssessmentRequest,
    CreateSustainabilityAssessmentRequest,
    SubmitSustainabilityAssessmentRequest,
    SustainabilityAssessmentRecord,
    SustainabilityAssessmentStatus,
    SustainabilityDisposition,
)


class SustainabilityAssessmentService:
    """Service governing operational sustainability assessments."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def create_assessment(
        self,
        registration_id: str,
        request: CreateSustainabilityAssessmentRequest,
        current_user: AuthenticatedUserContext,
    ) -> SustainabilityAssessmentRecord:
        """Creates a sustainability assessment evaluating routine integration."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        assessment_id = f"sus_{uuid.uuid4().hex[:12]}"

        record = SustainabilityAssessmentRecord(
            assessment_id=assessment_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            baseline_version=request.baseline_version,
            monitoring_period=request.monitoring_period,
            operational_scope=request.operational_scope,
            dimension_scores=request.dimension_scores,
            evidence_references=request.evidence_references,
            unresolved_limitations=request.unresolved_limitations,
            disposition=request.disposition,
            status=SustainabilityAssessmentStatus.DRAFT,
            assessor_id=current_user.user_id,
            submitted_by=None,
            submitted_at=None,
            approved_by=None,
            approved_at=None,
            approval_comments=None,
            follow_up_requirements=request.follow_up_requirements,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_sustainability_assessment(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.sustainability_created",
            actor_id=current_user.user_id,
            summary=f"Sustainability assessment created for period '{saved.monitoring_period}'.",
            details={"assessment_id": saved.assessment_id, "disposition": saved.disposition.value},
        )
        return saved

    def get_assessment(
        self, assessment_id: str, current_user: AuthenticatedUserContext
    ) -> SustainabilityAssessmentRecord:
        """Retrieves a sustainability assessment with tenant isolation."""
        assessment = self.repo.get_sustainability_assessment(assessment_id)
        if not assessment or assessment.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.SUSTAINABILITY_ASSESSMENT_NOT_FOUND,
                message=f"Sustainability assessment '{assessment_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return assessment

    def list_assessments_for_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> List[SustainabilityAssessmentRecord]:
        """Lists sustainability assessments for an adoption initiative."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_sustainability_assessments_for_registration(
            registration_id, current_user.tenant_id
        )

    def submit_assessment(
        self,
        assessment_id: str,
        request: SubmitSustainabilityAssessmentRequest,
        current_user: AuthenticatedUserContext,
    ) -> SustainabilityAssessmentRecord:
        """Submits a sustainability assessment for review and approval."""
        assessment = self.get_assessment(assessment_id, current_user)
        if assessment.status != SustainabilityAssessmentStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_SUSTAINABILITY_ASSESSMENT_STATE,
                message=f"Assessment cannot be submitted from status '{assessment.status.value}'. Must be DRAFT.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = assessment.model_dump()
        updated_dict["status"] = SustainabilityAssessmentStatus.SUBMITTED
        updated_dict["submitted_by"] = current_user.user_id
        updated_dict["submitted_at"] = now
        updated_dict["updated_at"] = now

        saved = self.repo.save_sustainability_assessment(SustainabilityAssessmentRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=assessment.registration_id,
            event_type="governance_change_adoption.sustainability_submitted",
            actor_id=current_user.user_id,
            summary=f"Sustainability assessment submitted for period '{saved.monitoring_period}'.",
            details={"submission_notes": request.submission_notes},
        )
        return saved

    def approve_assessment(
        self,
        assessment_id: str,
        request: ApproveSustainabilityAssessmentRequest,
        current_user: AuthenticatedUserContext,
    ) -> SustainabilityAssessmentRecord:
        """Approves a submitted sustainability assessment."""
        assessment = self.get_assessment(assessment_id, current_user)
        if assessment.status != SustainabilityAssessmentStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_SUSTAINABILITY_ASSESSMENT_STATE,
                message=f"Assessment cannot be approved from status '{assessment.status.value}'. Must be SUBMITTED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = assessment.model_dump()
        updated_dict["status"] = SustainabilityAssessmentStatus.APPROVED
        updated_dict["approved_by"] = current_user.user_id
        updated_dict["approved_at"] = now
        updated_dict["approval_comments"] = request.approval_comments
        updated_dict["updated_at"] = now

        saved = self.repo.save_sustainability_assessment(SustainabilityAssessmentRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=assessment.registration_id,
            event_type="governance_change_adoption.sustainability_approved",
            actor_id=current_user.user_id,
            summary=f"Sustainability assessment approved as {saved.disposition.value}.",
            details={"comments": request.approval_comments},
        )
        return saved

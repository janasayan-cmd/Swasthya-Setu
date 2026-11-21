"""Phase 77: Governance Assurance Review & Management Package Service.

Coordinates independent assessment reviews, enforces conflict of interest and
separation of duties controls, and packages management dossiers for Phase 72 referral.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_maturity_assessment import AssessmentStatus
from app.schemas.governance_maturity_framework import CLINICAL_SAFETY_DISCLAIMER
from app.schemas.governance_assurance_review import (
    AssignReviewerRequest,
    AssuranceReviewRecord,
    AssuranceReviewStatus,
    PrepareReviewPackageRequest,
    ReferToPhase72Request,
    StrategicManagementReviewPackageRecord,
    SubmitReviewDecisionRequest,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceAssuranceReviewService:
    """Manages independent reviews, separation of duties, and Phase 72 referrals."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def assign_reviewer(
        self,
        tenant_id: str,
        assessment_id: str,
        assigned_by: str,
        request: AssignReviewerRequest,
    ) -> AssuranceReviewRecord:
        assessment = self.repository.get_assessment(assessment_id)
        if not assessment or assessment.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: Assessor cannot review their own assessment
        if assessment.assessor_id == request.reviewer_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Assessor cannot be assigned as independent reviewer.",
                status_code=403,
            )

        # Conflict of interest must be explicitly confirmed cleared
        if not request.conflict_of_interest_cleared:
            raise AppException(
                code=ErrorCode.ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Conflict of interest must be explicitly confirmed as cleared before assignment.",
                status_code=403,
            )

        now = _get_utc_now_str()
        review = AssuranceReviewRecord(
            review_id=f"rev-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            assigned_reviewer_id=request.reviewer_id,
            assigned_by=assigned_by,
            assigned_at=now,
            status=AssuranceReviewStatus.IN_REVIEW,
            conflict_of_interest_cleared=request.conflict_of_interest_cleared,
            review_notes=None,
            completed_at=None,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )
        saved_review = self.repository.save_review(review)

        # Update assessment status
        assessment = assessment.model_copy(
            update={
                "status": AssessmentStatus.UNDER_REVIEW,
                "independent_review_id": saved_review.review_id,
                "updated_at": now,
            }
        )
        self.repository.save_assessment(assessment)
        return saved_review

    def submit_review_decision(
        self,
        tenant_id: str,
        review_id: str,
        reviewer_id: str,
        request: SubmitReviewDecisionRequest,
    ) -> AssuranceReviewRecord:
        review = self.repository.get_review(review_id)
        if not review or review.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_REVIEW_NOT_FOUND,
                message=f"Review '{review_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: Only the assigned reviewer can submit the decision
        if review.assigned_reviewer_id != reviewer_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Only the assigned independent reviewer can submit review decisions.",
                status_code=403,
            )

        assessment = self.repository.get_assessment(review.assessment_id)
        if not assessment:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{review.assessment_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        review = review.model_copy(
            update={
                "status": request.decision,
                "review_notes": request.review_notes,
                "completed_at": now,
            }
        )
        saved_review = self.repository.save_review(review)

        # Update assessment based on decision
        if request.decision == AssuranceReviewStatus.ACCEPTED:
            asmt_status = AssessmentStatus.APPROVED
        elif request.decision == AssuranceReviewStatus.CHANGES_REQUESTED:
            asmt_status = AssessmentStatus.IN_PROGRESS
        else:
            asmt_status = AssessmentStatus.DRAFT

        assessment = assessment.model_copy(
            update={
                "status": asmt_status,
                "updated_at": now,
            }
        )
        self.repository.save_assessment(assessment)
        return saved_review

    def prepare_review_package(
        self,
        tenant_id: str,
        prepared_by: str,
        request: PrepareReviewPackageRequest,
    ) -> StrategicManagementReviewPackageRecord:
        if not request.included_assessment_ids:
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_REVIEW_STATE,
                message="Cannot assemble review package without included assessment IDs.",
                status_code=400,
            )

        for asmt_id in request.included_assessment_ids:
            asmt = self.repository.get_assessment(asmt_id)
            if not asmt or asmt.tenant_id != tenant_id:
                raise AppException(
                    code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                    message=f"Included assessment '{asmt_id}' not found.",
                    status_code=404,
                )

        now = _get_utc_now_str()

        # Find linked gaps and improvement plans
        all_gaps = self.repository.list_gaps(tenant_id=tenant_id)
        relevant_gaps = [
            {"gap_id": g.gap_id, "title": g.title, "classification": g.classification.value, "status": g.status.value}
            for g in all_gaps
            if any(asmt_id in g.originating_assessment_ids for asmt_id in request.included_assessment_ids)
        ]

        all_plans = self.repository.list_plans(tenant_id=tenant_id)
        relevant_plans = [
            {"plan_id": p.plan_id, "title": p.title, "status": p.status.value, "target_level": p.target_level.value}
            for p in all_plans
        ]

        package = StrategicManagementReviewPackageRecord(
            package_id=f"smrp-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            title=request.title,
            reporting_period=request.reporting_period,
            executive_summary=request.executive_summary,
            included_assessment_ids=request.included_assessment_ids,
            systemic_gaps=relevant_gaps,
            proposed_improvement_plans=relevant_plans,
            prepared_by=prepared_by,
            phase_72_referral_id=None,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
            created_at=now,
        )
        return self.repository.save_package(package)

    def refer_to_phase72(
        self,
        tenant_id: str,
        package_id: str,
        request: ReferToPhase72Request,
    ) -> StrategicManagementReviewPackageRecord:
        package = self.repository.get_package(package_id)
        if not package or package.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_REVIEW_NOT_FOUND,
                message=f"Review package '{package_id}' was not found.",
                status_code=404,
            )

        ref_id = request.phase_72_meeting_id or f"p72-ref-{uuid.uuid4().hex[:8]}"
        package = package.model_copy(
            update={"phase_72_referral_id": ref_id}
        )
        return self.repository.save_package(package)

    def get_package(
        self,
        tenant_id: str,
        package_id: str,
    ) -> StrategicManagementReviewPackageRecord:
        package = self.repository.get_package(package_id)
        if not package or package.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_REVIEW_NOT_FOUND,
                message=f"Review package '{package_id}' was not found.",
                status_code=404,
            )
        return package

    def list_packages(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicManagementReviewPackageRecord]:
        return self.repository.list_packages(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
        )

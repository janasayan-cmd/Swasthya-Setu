"""Phase 84: Capability Assessment Lifecycle Service.

Coordinates individual capability assessment lifecycles, scheduling, evidence review,
and independent verification gates.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_capability_assessment import (
    AssessmentLifecycleState,
    AssessmentOutcome,
    CapabilityAssessmentRecord,
    CreateAssessmentRequest,
    ReviewAssessmentRequest,
    ScheduleAssessmentRequest,
    SubmitAssessmentEvidenceRequest,
    VerifyAssessmentRequest,
)


class GovernanceResilienceCapabilityAssessmentService:
    """Service managing capability assessment lifecycle, evidence, and verification."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def create_assessment(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateAssessmentRequest,
    ) -> CapabilityAssessmentRecord:
        framework = self.repository.get_framework(request.framework_id, tenant_id)
        if not framework:
            raise AppException(
                code=ErrorCode.CAPABILITY_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{request.framework_id}' not found.",
                status_code=404,
            )

        assessment_id = f"ass-{uuid.uuid4().hex[:10]}"
        record = CapabilityAssessmentRecord(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            framework_id=request.framework_id,
            framework_version=request.framework_version,
            applicable_role=request.applicable_role,
            subject_user_id=request.subject_user_id,
            lifecycle_state=AssessmentLifecycleState.PLANNED,
            scheduled_date=request.scheduled_date,
        )
        return self.repository.save_assessment(record)

    def get_assessment(self, tenant_id: str, assessment_id: str) -> CapabilityAssessmentRecord:
        record = self.repository.get_assessment(assessment_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPABILITY_ASSESSMENT_NOT_FOUND,
                message=f"Capability assessment '{assessment_id}' not found.",
                status_code=404,
            )
        return record

    def schedule_assessment(
        self,
        tenant_id: str,
        assessment_id: str,
        user_id: str,
        request: ScheduleAssessmentRequest,
    ) -> CapabilityAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)

        # Subject cannot be their own assessor
        if request.assessor_id == record.subject_user_id:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Subject cannot be assigned as their own capability assessor.",
                status_code=400,
            )

        record.lifecycle_state = AssessmentLifecycleState.SCHEDULED
        record.scheduled_date = request.scheduled_date
        record.assessor_id = request.assessor_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_assessment(record)

    def submit_evidence(
        self,
        tenant_id: str,
        assessment_id: str,
        user_id: str,
        request: SubmitAssessmentEvidenceRequest,
    ) -> CapabilityAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)

        if record.lifecycle_state in [
            AssessmentLifecycleState.VERIFIED,
            AssessmentLifecycleState.CANCELLED,
            AssessmentLifecycleState.SUPERSEDED,
        ]:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_ASSESSMENT_STATE,
                message=f"Cannot submit evidence for assessment in state '{record.lifecycle_state}'.",
                status_code=400,
            )

        record.evidence_references.extend(request.evidence_references)
        record.lifecycle_state = AssessmentLifecycleState.EVIDENCE_SUBMITTED
        record.updated_at = datetime.utcnow()
        return self.repository.save_assessment(record)

    def review_assessment(
        self,
        tenant_id: str,
        assessment_id: str,
        assessor_id: str,
        request: ReviewAssessmentRequest,
    ) -> CapabilityAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)

        # Subject cannot review/assess themselves
        if assessor_id == record.subject_user_id:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Subject cannot assess their own capability outcome.",
                status_code=400,
            )

        record.lifecycle_state = AssessmentLifecycleState.ASSESSED
        record.assessment_outcome = request.assessment_outcome
        record.criteria_evaluated = request.criteria_evaluated
        record.limitations = request.limitations
        record.reviewer_comments = request.reviewer_comments
        record.assessor_id = assessor_id
        record.assessed_at = datetime.utcnow()
        record.updated_at = datetime.utcnow()
        return self.repository.save_assessment(record)

    def verify_assessment(
        self,
        tenant_id: str,
        assessment_id: str,
        verifier_id: str,
        request: VerifyAssessmentRequest,
    ) -> CapabilityAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)

        # Separation of duties: Verifier cannot be assessor OR subject
        if verifier_id in [record.subject_user_id, record.assessor_id]:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Independent verifier cannot be the assessment subject or assessor.",
                status_code=400,
            )

        if record.lifecycle_state != AssessmentLifecycleState.ASSESSED:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_ASSESSMENT_STATE,
                message=f"Assessment must be in ASSESSED state before verification. Current: '{record.lifecycle_state}'.",
                status_code=400,
            )

        if request.verified:
            record.lifecycle_state = AssessmentLifecycleState.VERIFIED
            record.verifier_id = verifier_id
            record.verified_at = datetime.utcnow()
            record.next_assessment_due = request.next_assessment_due
        else:
            record.lifecycle_state = AssessmentLifecycleState.CHANGES_REQUESTED
            record.reviewer_comments = f"Verification rejected: {request.verification_notes}"

        record.updated_at = datetime.utcnow()
        return self.repository.save_assessment(record)

    def list_assessments(
        self,
        tenant_id: str,
        subject_user_id: Optional[str] = None,
        applicable_role: Optional[str] = None,
        lifecycle_state: Optional[AssessmentLifecycleState] = None,
        outcome: Optional[AssessmentOutcome] = None,
    ) -> List[CapabilityAssessmentRecord]:
        return self.repository.list_assessments(
            tenant_id=tenant_id,
            subject_user_id=subject_user_id,
            applicable_role=applicable_role,
            lifecycle_state=lifecycle_state,
            outcome=outcome,
        )

    def get_assessment_history(
        self, tenant_id: str, assessment_id: str
    ) -> List[CapabilityAssessmentRecord]:
        self.get_assessment(tenant_id, assessment_id)
        return self.repository.get_assessment_history(assessment_id, tenant_id)


_assessment_service = GovernanceResilienceCapabilityAssessmentService()


def get_governance_resilience_capability_assessment_service() -> GovernanceResilienceCapabilityAssessmentService:
    return _assessment_service

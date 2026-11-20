"""Phase 73: Implementation Milestones, Evidence & Independent Verification Service.

Handles:
- Milestone lifecycle (creation, updates, progress, submission)
- Referencing implementation evidence and review for contradictory evidence
- Independent milestone verification enforcing separation of duties
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_implementation_repository import (
    GovernanceDecisionImplementationRepository,
    get_governance_decision_implementation_repository,
)
from app.schemas.decision_implementation_milestones_evidence import (
    CreateMilestoneRequest,
    ImplementationEvidenceRecord,
    ImplementationMilestoneRecord,
    ImplementationVerificationRecord,
    MilestoneStatus,
    ReviewEvidenceRequest,
    SubmitEvidenceRequest,
    SubmitMilestoneRequest,
    UpdateMilestoneRequest,
    VerificationOutcome,
    VerifyMilestoneRequest,
)


class ImplementationMilestoneService:
    """Service governing milestone progression, evidence indexing, and independent verification."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )

    # -------------------------------------------------------------------------
    # Milestones
    # -------------------------------------------------------------------------

    def create_milestone(
        self,
        implementation_id: str,
        request: CreateMilestoneRequest,
    ) -> ImplementationMilestoneRecord:
        """Adds a milestone to an implementation plan."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        milestone = ImplementationMilestoneRecord(
            implementation_id=implementation_id,
            title=request.title,
            description=request.description,
            responsible_owner_id=request.responsible_owner_id,
            start_date=request.start_date,
            target_date=request.target_date,
            status=MilestoneStatus.NOT_STARTED,
            expected_output=request.expected_output,
            required_evidence_types=request.required_evidence_types or [],
            dependency_ids=request.dependency_ids or [],
            metadata=request.metadata or {},
        )

        return self.repository.save_milestone(milestone)

    def get_milestone(
        self, milestone_id: str
    ) -> ImplementationMilestoneRecord:
        """Retrieves a milestone by ID."""
        milestone = self.repository.get_milestone(milestone_id)
        if not milestone:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMPLEMENTATION_MILESTONE_NOT_FOUND,
                message=f"Implementation milestone '{milestone_id}' not found.",
            )
        return milestone

    def list_milestones(
        self,
        implementation_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        is_overdue: Optional[bool] = None,
    ) -> List[ImplementationMilestoneRecord]:
        """Lists milestones matching query criteria."""
        return self.repository.list_milestones(
            implementation_id=implementation_id,
            status=status_filter,
            is_overdue=is_overdue,
        )

    def update_milestone(
        self, milestone_id: str, request: UpdateMilestoneRequest
    ) -> ImplementationMilestoneRecord:
        """Modifies milestone parameters."""
        milestone = self.get_milestone(milestone_id)
        if request.title is not None:
            milestone.title = request.title
        if request.description is not None:
            milestone.description = request.description
        if request.target_date is not None:
            milestone.target_date = request.target_date
        if request.status is not None:
            milestone.status = request.status
        if request.expected_output is not None:
            milestone.expected_output = request.expected_output
        if request.metadata is not None:
            milestone.metadata.update(request.metadata)

        return self.repository.save_milestone(milestone)

    def submit_milestone(
        self,
        milestone_id: str,
        request: SubmitMilestoneRequest,
        submitter_id: str,
    ) -> ImplementationMilestoneRecord:
        """Submits completed work for independent verification.

        INVARIANT: Submitting completed work does NOT mark the milestone as VERIFIED.
        """
        milestone = self.get_milestone(milestone_id)
        milestone.status = MilestoneStatus.SUBMITTED
        milestone.submission_notes = request.submission_notes
        milestone.submitted_at = datetime.now(timezone.utc)
        milestone.metadata["submitted_by"] = submitter_id
        if request.evidence_refs:
            milestone.metadata["evidence_refs"] = request.evidence_refs

        return self.repository.save_milestone(milestone)

    # -------------------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------------------

    def attach_evidence(
        self,
        implementation_id: str,
        request: SubmitEvidenceRequest,
        submitter_id: str,
    ) -> ImplementationEvidenceRecord:
        """Attaches an evidence reference to an implementation or milestone."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        evidence = ImplementationEvidenceRecord(
            implementation_id=implementation_id,
            milestone_id=request.milestone_id,
            source_record_ref=request.source_record_ref,
            evidence_type=request.evidence_type,
            version=request.version or "1.0",
            owner_id=submitter_id,
            access_classification=request.access_classification or "STANDARD",
            review_status="PENDING_REVIEW",
            metadata=request.metadata or {},
        )

        return self.repository.save_evidence(evidence)

    def get_evidence(self, evidence_id: str) -> ImplementationEvidenceRecord:
        """Retrieves an evidence record by ID."""
        evidence = self.repository.get_evidence(evidence_id)
        if not evidence:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMPLEMENTATION_EVIDENCE_NOT_FOUND,
                message=f"Implementation evidence '{evidence_id}' not found.",
            )
        return evidence

    def list_evidence(
        self, implementation_id: str, milestone_id: Optional[str] = None
    ) -> List[ImplementationEvidenceRecord]:
        """Lists evidence attached to an implementation or milestone."""
        return self.repository.list_evidence(
            implementation_id=implementation_id, milestone_id=milestone_id
        )

    def review_evidence(
        self,
        evidence_id: str,
        request: ReviewEvidenceRequest,
        reviewer_id: str,
    ) -> ImplementationEvidenceRecord:
        """Reviews evidence for validity or flags contradictory evidence."""
        evidence = self.get_evidence(evidence_id)
        evidence.review_status = request.review_status
        evidence.reviewed_by = reviewer_id
        evidence.review_comments = request.review_comments

        return self.repository.save_evidence(evidence)

    # -------------------------------------------------------------------------
    # Independent Verification
    # -------------------------------------------------------------------------

    def verify_milestone(
        self,
        milestone_id: str,
        request: VerifyMilestoneRequest,
        verifier_id: str,
        verifier_role: str,
    ) -> ImplementationVerificationRecord:
        """Conducts independent verification on a submitted milestone, enforcing separation of duties."""
        milestone = self.get_milestone(milestone_id)
        imp = self.repository.get_implementation(milestone.implementation_id)

        # Separation of duties:
        # Verifier CANNOT be the milestone responsible owner or implementation lead
        if verifier_id in [milestone.responsible_owner_id, imp.responsible_owner_id]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.SEPARATION_OF_DUTIES_VIOLATION,
                message=(
                    f"Separation of duties violation: User '{verifier_id}' is the owner of this work item "
                    f"and cannot independently verify their own implementation."
                ),
            )

        verification = ImplementationVerificationRecord(
            implementation_id=milestone.implementation_id,
            milestone_id=milestone_id,
            verification_criteria=request.verification_criteria or [],
            evidence_reviewed=request.evidence_reviewed or [],
            outcome=request.outcome,
            verifier_id=verifier_id,
            verifier_role=verifier_role,
            rationale=request.rationale,
            outstanding_deficiencies=request.outstanding_deficiencies or [],
            required_remediation=request.required_remediation,
        )
        saved_verification = self.repository.save_verification(verification)

        # Update milestone status based on independent verification outcome
        if request.outcome == VerificationOutcome.VERIFIED:
            milestone.status = MilestoneStatus.VERIFIED
            milestone.verification_status = "VERIFIED"
            milestone.completion_date = datetime.now(timezone.utc)
        elif request.outcome == VerificationOutcome.REJECTED:
            milestone.status = MilestoneStatus.REJECTED
            milestone.verification_status = "REJECTED"
        else:
            milestone.status = MilestoneStatus.UNDER_REVIEW
            milestone.verification_status = request.outcome.value

        self.repository.save_milestone(milestone)
        return saved_verification

    def list_verifications(
        self, implementation_id: str, milestone_id: Optional[str] = None
    ) -> List[ImplementationVerificationRecord]:
        """Lists verification history."""
        return self.repository.list_verifications(
            implementation_id=implementation_id, milestone_id=milestone_id
        )

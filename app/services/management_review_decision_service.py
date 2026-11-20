"""Phase 72: Clinical Safety Governance Management Review Decision & Commitment Service.

Handles:
- Recording meeting discussions and minutes
- Authoritative decision formalization and decision authority verification
- Actionable commitment assignment, progress monitoring, and verification
- Escalation of overdue or blocked commitments to executive leadership
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_management_review_repository import (
    GovernanceManagementReviewRepository,
    get_governance_management_review_repository,
)
from app.schemas.management_review_scheduling import (
    ManagementReviewStatus,
    ParticipantRole,
)
from app.schemas.management_review_decisions import (
    ApproveDecisionRequest,
    CommitmentEscalationRecord,
    CommitmentPriority,
    CommitmentStatus,
    CreateDiscussionRecordRequest,
    CreateManagementCommitmentRequest,
    CreateManagementDecisionRequest,
    DeferDecisionRequest,
    DiscussionRecord,
    EscalateCommitmentRequest,
    ManagementCommitmentRecord,
    ManagementDecisionCategory,
    ManagementDecisionRecord,
    ManagementDecisionStatus,
    SubmitCommitmentVerificationRequest,
    SupersedeDecisionRequest,
    UpdateCommitmentProgressRequest,
    VerifyCommitmentRequest,
)


class ManagementReviewDecisionService:
    """Service governing review discussions, authoritative decisions, and follow-through commitments."""

    def __init__(
        self, repository: Optional[GovernanceManagementReviewRepository] = None
    ) -> None:
        self.repository = repository or get_governance_management_review_repository()

    # -------------------------------------------------------------------------
    # Discussions & Minutes
    # -------------------------------------------------------------------------

    def record_discussion(
        self,
        review_id: str,
        request: CreateDiscussionRecordRequest,
        speaker_id: str,
    ) -> DiscussionRecord:
        """Records meeting discussion notes."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )

        if review.status in [
            ManagementReviewStatus.COMPLETED,
            ManagementReviewStatus.CANCELLED,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot record discussion on review in status '{review.status.value}'.",
            )

        rec = DiscussionRecord(
            review_id=review_id,
            agenda_item_id=request.agenda_item_id,
            speaker_id=speaker_id,
            speaker_name=request.speaker_name,
            topic=request.topic,
            discussion_notes=request.discussion_notes,
            key_points=request.key_points or [],
            metadata=request.metadata or {},
        )
        return self.repository.save_discussion(rec)

    def list_discussions(
        self, review_id: str, agenda_item_id: Optional[str] = None
    ) -> List[DiscussionRecord]:
        """Lists discussions recorded for a review."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )
        return self.repository.list_discussions(review_id, agenda_item_id)

    # -------------------------------------------------------------------------
    # Management Decisions & Authority Verification
    # -------------------------------------------------------------------------

    def record_decision(
        self,
        review_id: str,
        request: CreateManagementDecisionRequest,
        decider_id: str,
        decider_role: str,
        organization_id: str,
    ) -> ManagementDecisionRecord:
        """Records an authoritative management decision, enforcing decision authority."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )

        if review.status in [
            ManagementReviewStatus.COMPLETED,
            ManagementReviewStatus.CANCELLED,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot record decisions for review in status '{review.status.value}'.",
            )

        # Authority verification: Participant has decision authority OR caller is ADMIN or DOCTOR
        participant = self.repository.find_participant_by_user(review_id, decider_id)
        has_authority = False
        if participant and participant.has_decision_authority:
            has_authority = True
        elif decider_role in ["ADMIN", "DOCTOR", "GOVERNANCE_OFFICER", "EXECUTIVE"]:
            has_authority = True

        if not has_authority:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code=ErrorCode.DECISION_AUTHORIZATION_FAILED,
                message=f"User '{decider_id}' does not possess decision authority for review '{review_id}'. Attendance alone does not confer decision-making rights.",
            )

        decision = ManagementDecisionRecord(
            review_id=review_id,
            agenda_item_id=request.agenda_item_id,
            title=request.title,
            category=request.category,
            status=ManagementDecisionStatus.APPROVED,
            rationale=request.rationale,
            decided_by_id=decider_id,
            decided_by_role=decider_role,
            supporting_evidence_refs=request.supporting_evidence_refs or [],
            supersedes_decision_id=request.supersedes_decision_id,
            organization_id=organization_id,
            facility_id=request.facility_id or review.facility_id,
            metadata=request.metadata or {},
        )
        saved_decision = self.repository.save_decision(decision)

        # Handle supersession if specified
        if request.supersedes_decision_id:
            prior_decision = self.repository.get_decision(request.supersedes_decision_id)
            if prior_decision:
                prior_decision.status = ManagementDecisionStatus.SUPERSEDED
                prior_decision.superseded_by_id = saved_decision.decision_id
                prior_decision.superseded_reason = f"Superseded by decision {saved_decision.decision_id}: {request.title}"
                self.repository.save_decision(prior_decision)

        return saved_decision

    def get_decision(self, decision_id: str) -> ManagementDecisionRecord:
        """Retrieves a single management decision."""
        decision = self.repository.get_decision(decision_id)
        if not decision:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_DECISION_NOT_FOUND,
                message=f"Management decision '{decision_id}' not found.",
            )
        return decision

    def list_decisions(
        self,
        review_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementDecisionRecord]:
        """Lists decisions filtered by review, tenant, status, or category."""
        return self.repository.list_decisions(
            review_id=review_id,
            organization_id=organization_id,
            status=status_filter,
            category=category,
            limit=limit,
            offset=offset,
        )

    def approve_decision(
        self, decision_id: str, request: ApproveDecisionRequest
    ) -> ManagementDecisionRecord:
        """Approves a proposed decision."""
        decision = self.get_decision(decision_id)
        decision.status = ManagementDecisionStatus.APPROVED
        if request.approval_notes:
            decision.metadata["approval_notes"] = request.approval_notes
        return self.repository.save_decision(decision)

    def defer_decision(
        self, decision_id: str, request: DeferDecisionRequest
    ) -> ManagementDecisionRecord:
        """Defers a decision for subsequent review."""
        decision = self.get_decision(decision_id)
        decision.status = ManagementDecisionStatus.DEFERRED
        decision.metadata["deferral_reason"] = request.deferral_reason
        return self.repository.save_decision(decision)

    def supersede_decision(
        self, decision_id: str, request: SupersedeDecisionRequest
    ) -> ManagementDecisionRecord:
        """Formally supersedes a previously recorded decision."""
        decision = self.get_decision(decision_id)
        decision.status = ManagementDecisionStatus.SUPERSEDED
        decision.superseded_by_id = request.superseding_decision_id
        decision.superseded_reason = request.superseded_reason
        return self.repository.save_decision(decision)

    # -------------------------------------------------------------------------
    # Management Commitments & Follow-Through
    # -------------------------------------------------------------------------

    def create_commitment(
        self,
        request: CreateManagementCommitmentRequest,
    ) -> ManagementCommitmentRecord:
        """Instantiates an assigned follow-through commitment linked to a decision."""
        decision = self.repository.get_decision(request.decision_id)
        if not decision:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_DECISION_NOT_FOUND,
                message=f"Management decision '{request.decision_id}' not found.",
            )

        commitment = ManagementCommitmentRecord(
            decision_id=request.decision_id,
            review_id=decision.review_id,
            title=request.title,
            description=request.description,
            responsible_owner_id=request.responsible_owner_id,
            accountable_lead_id=request.accountable_lead_id,
            status=CommitmentStatus.ASSIGNED,
            priority=request.priority or CommitmentPriority.MEDIUM,
            due_date=request.due_date,
            linked_capa_id=request.linked_capa_id,
            linked_effectiveness_id=request.linked_effectiveness_id,
            linked_risk_review_id=request.linked_risk_review_id,
            linked_escalation_id=request.linked_escalation_id,
            metadata=request.metadata or {},
        )
        saved_commitment = self.repository.save_commitment(commitment)

        decision.commitments_count += 1
        self.repository.save_decision(decision)

        return saved_commitment

    def get_commitment(self, commitment_id: str) -> ManagementCommitmentRecord:
        """Retrieves a single commitment record."""
        commitment = self.repository.get_commitment(commitment_id)
        if not commitment:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_COMMITMENT_NOT_FOUND,
                message=f"Management commitment '{commitment_id}' not found.",
            )
        return commitment

    def list_commitments(
        self,
        review_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        is_overdue: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementCommitmentRecord]:
        """Lists commitments matching query criteria."""
        return self.repository.list_commitments(
            review_id=review_id,
            decision_id=decision_id,
            owner_id=owner_id,
            status=status_filter,
            is_overdue=is_overdue,
            limit=limit,
            offset=offset,
        )

    def update_commitment_progress(
        self, commitment_id: str, request: UpdateCommitmentProgressRequest, updater_id: str
    ) -> ManagementCommitmentRecord:
        """Updates implementation progress and notes for a commitment."""
        commitment = self.get_commitment(commitment_id)
        if commitment.status in [CommitmentStatus.CLOSED, CommitmentStatus.CANCELLED]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot update commitment in status '{commitment.status.value}'.",
            )

        commitment.progress_percentage = request.progress_percentage
        note_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "updater_id": updater_id,
            "progress_percentage": request.progress_percentage,
            "note": request.note,
        }
        commitment.progress_notes.append(note_entry)
        if request.completion_evidence_refs:
            commitment.completion_evidence_refs.extend(request.completion_evidence_refs)

        if commitment.status == CommitmentStatus.ASSIGNED and request.progress_percentage > 0:
            commitment.status = CommitmentStatus.IN_PROGRESS

        return self.repository.save_commitment(commitment)

    def submit_verification(
        self, commitment_id: str, request: SubmitCommitmentVerificationRequest
    ) -> ManagementCommitmentRecord:
        """Submits an action commitment for formal verification of implementation."""
        commitment = self.get_commitment(commitment_id)
        commitment.status = CommitmentStatus.PENDING_VERIFICATION
        commitment.completion_evidence_refs.extend(request.completion_evidence_refs)
        commitment.metadata["summary_of_implementation"] = request.summary_of_implementation
        commitment.metadata["submitted_for_verification_at"] = datetime.now(timezone.utc).isoformat()
        return self.repository.save_commitment(commitment)

    def verify_commitment(
        self,
        commitment_id: str,
        request: VerifyCommitmentRequest,
        verifier_id: str,
    ) -> ManagementCommitmentRecord:
        """Formally verifies or rejects implementation of a commitment."""
        commitment = self.get_commitment(commitment_id)
        if commitment.status not in [
            CommitmentStatus.PENDING_VERIFICATION,
            CommitmentStatus.UNDER_REVIEW,
            CommitmentStatus.IN_PROGRESS,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.COMMITMENT_VERIFICATION_FAILED,
                message=f"Commitment in status '{commitment.status.value}' cannot be verified.",
            )

        if request.verified:
            commitment.status = CommitmentStatus.VERIFIED
            commitment.progress_percentage = 100
            commitment.verified_by = verifier_id
            commitment.verified_at = datetime.now(timezone.utc)
            commitment.verification_notes = request.verification_notes
        else:
            commitment.status = CommitmentStatus.IN_PROGRESS
            commitment.verification_notes = f"Verification rejected by {verifier_id}: {request.verification_notes}"

        return self.repository.save_commitment(commitment)

    def escalate_commitment(
        self,
        commitment_id: str,
        request: EscalateCommitmentRequest,
        escalator_id: str,
    ) -> CommitmentEscalationRecord:
        """Escalates an overdue or impeded commitment to executive leadership."""
        commitment = self.get_commitment(commitment_id)
        commitment.status = CommitmentStatus.ESCALATED
        self.repository.save_commitment(commitment)

        escalation = CommitmentEscalationRecord(
            commitment_id=commitment_id,
            review_id=commitment.review_id,
            escalated_by=escalator_id,
            escalated_to=request.escalated_to,
            escalation_reason=request.escalation_reason,
            urgency=request.urgency or "HIGH",
        )
        return self.repository.save_escalation(escalation)

    def list_escalations(
        self, commitment_id: Optional[str] = None, review_id: Optional[str] = None
    ) -> List[CommitmentEscalationRecord]:
        """Lists escalations for commitments."""
        return self.repository.list_escalations(commitment_id, review_id)

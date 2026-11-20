"""Phase 74: Operational Adoption Evidence Service.

Coordinates:
- Structured evidence intake, indexing, verification, and rejection
- Strict separation of duties (submitting actor cannot verify their own evidence)
- Validity and expiration handling
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
from app.schemas.adoption_evidence_indicators import (
    AdoptionEvidenceRecord,
    EvidenceVerificationStatus,
    RejectAdoptionEvidenceRequest,
    SubmitAdoptionEvidenceRequest,
    VerifyAdoptionEvidenceRequest,
)


class AdoptionEvidenceService:
    """Service governing operational adoption evidence lifecycle."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def submit_evidence(
        self,
        registration_id: str,
        request: SubmitAdoptionEvidenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionEvidenceRecord:
        """Submits operational evidence for adoption monitoring."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        evidence_id = f"evi_{uuid.uuid4().hex[:12]}"

        record = AdoptionEvidenceRecord(
            evidence_id=evidence_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            baseline_version=request.baseline_version,
            title=request.title,
            description=request.description,
            category=request.category,
            organizational_scope=request.organizational_scope,
            source_system=request.source_system,
            source_reference=request.source_reference,
            collected_at=request.collected_at,
            submitted_at=now,
            submitting_actor_id=current_user.user_id,
            verification_status=EvidenceVerificationStatus.SUBMITTED,
            reviewer_id=None,
            verified_at=None,
            rejection_reason=None,
            valid_until=request.valid_until,
            integrity_hash=request.integrity_hash,
            provenance_metadata=request.provenance_metadata,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_evidence(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.evidence_submitted",
            actor_id=current_user.user_id,
            summary=f"Evidence '{saved.title}' submitted (Category: {saved.category.value}).",
            details={"evidence_id": saved.evidence_id, "source_ref": saved.source_reference},
        )
        return saved

    def get_evidence(
        self, evidence_id: str, current_user: AuthenticatedUserContext
    ) -> AdoptionEvidenceRecord:
        """Retrieves an evidence item with tenant isolation."""
        evidence = self.repo.get_evidence(evidence_id)
        if not evidence or evidence.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.ADOPTION_EVIDENCE_NOT_FOUND,
                message=f"Adoption evidence '{evidence_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return evidence

    def list_evidence_for_registration(
        self,
        registration_id: str,
        current_user: AuthenticatedUserContext,
        status_filter: Optional[EvidenceVerificationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AdoptionEvidenceRecord]:
        """Lists evidence submitted for an adoption registration."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_evidence_for_registration(
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            status=status_filter,
            skip=skip,
            limit=limit,
        )

    def verify_evidence(
        self,
        evidence_id: str,
        request: VerifyAdoptionEvidenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionEvidenceRecord:
        """Verifies submitted operational evidence.
        
        Strictly enforces Separation of Duties: Submitter cannot verify their own evidence.
        """
        evidence = self.get_evidence(evidence_id, current_user)
        if evidence.verification_status not in [
            EvidenceVerificationStatus.SUBMITTED,
            EvidenceVerificationStatus.PENDING_VERIFICATION,
        ]:
            raise AppException(
                code=ErrorCode.INVALID_ADOPTION_EVIDENCE_STATE,
                message=f"Evidence cannot be verified from status '{evidence.verification_status.value}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce separation of duties
        if current_user.user_id == evidence.submitting_actor_id:
            raise AppException(
                code=ErrorCode.ADOPTION_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: submitting actor cannot verify their own evidence.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = evidence.model_dump()
        updated_dict["verification_status"] = EvidenceVerificationStatus.VERIFIED
        updated_dict["reviewer_id"] = current_user.user_id
        updated_dict["verified_at"] = now
        updated_dict["updated_at"] = now

        saved = self.repo.save_evidence(AdoptionEvidenceRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=evidence.registration_id,
            event_type="governance_change_adoption.evidence_verified",
            actor_id=current_user.user_id,
            summary=f"Evidence '{saved.title}' verified by {current_user.user_id}.",
            details={"comments": request.verification_comments},
        )
        return saved

    def reject_evidence(
        self,
        evidence_id: str,
        request: RejectAdoptionEvidenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionEvidenceRecord:
        """Rejects submitted operational evidence with a stated reason."""
        evidence = self.get_evidence(evidence_id, current_user)
        if evidence.verification_status not in [
            EvidenceVerificationStatus.SUBMITTED,
            EvidenceVerificationStatus.PENDING_VERIFICATION,
        ]:
            raise AppException(
                code=ErrorCode.INVALID_ADOPTION_EVIDENCE_STATE,
                message=f"Evidence cannot be rejected from status '{evidence.verification_status.value}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = evidence.model_dump()
        updated_dict["verification_status"] = EvidenceVerificationStatus.REJECTED
        updated_dict["reviewer_id"] = current_user.user_id
        updated_dict["rejection_reason"] = request.rejection_reason
        updated_dict["updated_at"] = now

        saved = self.repo.save_evidence(AdoptionEvidenceRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=evidence.registration_id,
            event_type="governance_change_adoption.evidence_rejected",
            actor_id=current_user.user_id,
            summary=f"Evidence '{saved.title}' rejected: {request.rejection_reason}",
            details={"rejection_reason": request.rejection_reason},
        )
        return saved

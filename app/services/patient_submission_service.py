"""HealthSetu Phase 42 - Patient Submission Service.

Orchestrates submissions, corrections, document links, appointment confirmations,
care-plan receipt acknowledgements, and explicit refusals.

NON-NEGOTIABLE CLINICAL SAFETY BOUNDARIES:
- PATIENT SUBMISSION != VERIFIED MEDICAL DATA
- PATIENT REPORTED SYMPTOM != TRIAGE RESULT
- PATIENT MEDICATION ENTRY != VERIFIED MEDICATION
- PATIENT ALLERGY ENTRY != VERIFIED ALLERGY
- PATIENT ACKNOWLEDGEMENT != CLINICAL ADHERENCE OR UNDERSTANDING
- PATIENT CONFIRMATION != CLINICAL ENCOUNTER COMPLETION
- CORRECTION PRESERVES HISTORICAL DATA (Submission 1 -> Submission 2)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    DocumentSubmissionInvalidException,
    PatientActionAlreadySubmittedException,
    PatientActionIdempotencyConflictException,
    PatientActionInvalidStateException,
)
from app.repositories.patient_action_repository import PatientActionRepository
from app.schemas.patient_action import (
    ActionStatus,
    PatientActionHistoryRecord,
    PatientActionRecord,
)
from app.schemas.patient_submission import (
    DocumentSubmissionRecord,
    PatientSubmissionRecord,
    SubmissionProvenance,
    SubmissionType,
)


class PatientSubmissionService:
    """Manages patient submissions with provenance and idempotency."""

    def __init__(self, action_repo: PatientActionRepository) -> None:
        self.repo = action_repo

    async def submit_action(
        self,
        action: PatientActionRecord,
        actor_id: str,
        actor_role: str,
        responses: Dict[str, Any],
        document_ids: List[str] = [],
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        submission_type: SubmissionType = SubmissionType.ACTION_SUBMISSION,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientSubmissionRecord:
        """Process an authoritative patient action submission."""
        # 1. Idempotency check
        if idempotency_key:
            existing = await self.repo.get_submission_by_idempotency_key(idempotency_key)
            if existing:
                # Return authoritative existing submission without duplicate processing
                return existing

        provenance = SubmissionProvenance(
            actor_id=actor_id,
            actor_role=actor_role,
            submitted_at=datetime.now(timezone.utc),
            client_ip=client_ip,
            user_agent=user_agent,
        )

        submission = PatientSubmissionRecord(
            action_id=action.id,
            patient_id=action.patient_id,
            submission_version=1,
            submission_type=submission_type,
            responses=responses,
            document_ids=document_ids,
            notes=notes,
            idempotency_key=idempotency_key,
            is_correction=False,
            provenance=provenance,
        )
        saved_submission = await self.repo.save_submission(submission)

        # Update action state
        action.status = ActionStatus.SUBMITTED
        action.submitted_at = datetime.now(timezone.utc)
        await self.repo.save_action(action)

        # Record history
        await self.repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=action.id,
                from_status=ActionStatus.AVAILABLE,
                to_status=ActionStatus.SUBMITTED,
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Patient submitted response.",
                details={"submission_id": saved_submission.id, "version": 1},
            )
        )
        return saved_submission

    async def submit_correction(
        self,
        action: PatientActionRecord,
        actor_id: str,
        actor_role: str,
        reason: str,
        corrected_responses: Dict[str, Any],
        document_ids: List[str] = [],
        notes: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientSubmissionRecord:
        """Submit a correction without overwriting historical submissions."""
        prior_submissions = await self.repo.get_submissions_by_action(action.id)
        next_version = len(prior_submissions) + 1
        prior_id = prior_submissions[-1].id if prior_submissions else None

        provenance = SubmissionProvenance(
            actor_id=actor_id,
            actor_role=actor_role,
            submitted_at=datetime.now(timezone.utc),
            client_ip=client_ip,
            user_agent=user_agent,
        )

        correction_sub = PatientSubmissionRecord(
            action_id=action.id,
            patient_id=action.patient_id,
            submission_version=next_version,
            submission_type=SubmissionType.CORRECTION,
            responses=corrected_responses,
            document_ids=document_ids,
            notes=notes,
            is_correction=True,
            correction_reason=reason,
            prior_submission_id=prior_id,
            provenance=provenance,
        )
        saved_correction = await self.repo.save_submission(correction_sub)

        # Action status returns to SUBMITTED / NEEDS_REVIEW
        old_status = action.status
        action.status = ActionStatus.SUBMITTED
        await self.repo.save_action(action)

        await self.repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=action.id,
                from_status=old_status,
                to_status=ActionStatus.SUBMITTED,
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Correction submitted (v{next_version}): {reason}",
                details={"submission_id": saved_correction.id, "prior_submission_id": prior_id},
            )
        )
        return saved_correction

    async def attach_document(
        self,
        action: PatientActionRecord,
        document_id: str,
        submitted_by: str,
        document_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DocumentSubmissionRecord:
        """Link an uploaded Phase 5 document to this action."""
        if not document_id or not document_id.strip():
            raise DocumentSubmissionInvalidException("Document ID cannot be blank.")

        doc_record = DocumentSubmissionRecord(
            action_id=action.id,
            patient_id=action.patient_id,
            document_id=document_id,
            document_type=document_type,
            description=description,
            submitted_by=submitted_by,
        )
        saved_doc = await self.repo.save_document_submission(doc_record)

        await self.repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=action.id,
                from_status=action.status,
                to_status=action.status,
                actor_id=submitted_by,
                actor_role="PATIENT",
                reason="Document attached to action.",
                details={"document_id": document_id, "doc_record_id": saved_doc.id},
            )
        )
        return saved_doc

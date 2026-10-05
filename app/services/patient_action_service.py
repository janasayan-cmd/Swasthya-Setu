"""HealthSetu Phase 42 - Patient Action Master Service.

Orchestrates patient self-service actions, lifecycle transitions,
questionnaires, document attachments, submissions, corrections,
and administrative/clinician reviews.

NON-NEGOTIABLE CLINICAL SAFETY PRINCIPLES:
- PATIENT ACTION != CLINICAL DECISION
- PATIENT RESPONSE != CLINICAL VERIFICATION
- PATIENT ACKNOWLEDGEMENT != CLINICAL UNDERSTANDING OR ADHERENCE
- PATIENT CONFIRMATION != CLINICAL CONSENT UNLESS EXPLICITLY DEFINED
- PATIENT SUBMISSION != VERIFIED MEDICAL DATA
- PATIENT REPORTED SYMPTOM != TRIAGE RESULT
- PATIENT MEDICATION ENTRY != VERIFIED MEDICATION
- PATIENT ALLERGY ENTRY != VERIFIED ALLERGY
- NO DIRECT UNCONTROLLED CLINICAL RECORD MODIFICATION FROM SELF-SERVICE
- NO AUTONOMOUS DIAGNOSIS, TRIAGE, PRESCRIBING, OR EMERGENCY DISPATCH
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    PatientActionAlreadySubmittedException,
    PatientActionExpiredException,
    PatientActionNotFoundException,
    PatientActionsDisabledException,
    PatientActionValidationFailedException,
)
from app.repositories.patient_action_repository import PatientActionRepository
from app.schemas.audit import AuditEventType
from app.schemas.patient_action import (
    ActionPriority,
    ActionStatus,
    ActionType,
    PatientActionAcknowledgeRequest,
    PatientActionCancelRequest,
    PatientActionCompleteRequest,
    PatientActionCorrectionRequest,
    PatientActionCreateRequest,
    PatientActionHistoryRecord,
    PatientActionRecord,
    PatientActionRefuseRequest,
    PatientActionReviewRequest,
    PatientActionStartRequest,
    PatientActionSubmitRequest,
)
from app.schemas.patient_submission import (
    DocumentSubmissionRecord,
    DocumentSubmissionRequest,
    PatientSubmissionRecord,
    SubmissionType,
)
from app.schemas.questionnaire import (
    QuestionnaireDefinition,
    QuestionnaireResponseRecord,
    QuestionnaireSubmissionRequest,
)
from app.services.audit_service import AuditService
from app.services.patient_action_authorization_service import PatientActionAuthorizationService
from app.services.patient_action_validation_service import PatientActionValidationService
from app.services.patient_action_workflow_service import PatientActionWorkflowService
from app.services.patient_submission_service import PatientSubmissionService
from app.services.questionnaire_service import QuestionnaireService

logger = logging.getLogger(__name__)


class PatientActionService:
    """Master orchestrator for patient self-service engagement."""

    def __init__(
        self,
        action_repo: PatientActionRepository,
        auth_service: PatientActionAuthorizationService,
        validation_service: PatientActionValidationService,
        submission_service: PatientSubmissionService,
        questionnaire_service: QuestionnaireService,
        workflow_service: PatientActionWorkflowService,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.action_repo = action_repo
        self.auth_service = auth_service
        self.validation_service = validation_service
        self.submission_service = submission_service
        self.questionnaire_service = questionnaire_service
        self.workflow_service = workflow_service
        self.audit_service = audit_service

    def _check_enabled(self) -> None:
        """Verify feature flag for Phase 42."""
        if not getattr(settings, "PATIENT_ACTIONS_ENABLED", True):
            raise PatientActionsDisabledException()

    async def _record_audit(
        self,
        event_type: AuditEventType,
        actor_id: Optional[str],
        patient_id: Optional[str],
        action: str,
        resource_id: Optional[str] = None,
        outcome: str = "ALLOW",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Helper to safely record an audit event."""
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=event_type,
                    actor_id=actor_id,
                    action=action,
                    resource_type="patient_action",
                    resource_id=resource_id,
                    outcome=outcome,
                    metadata=metadata or {},
                )
            except Exception as e:
                logger.warning(f"Failed to record audit event {event_type}: {e}")

    # =========================================================================
    # Action Lifecycle: Creation & Retrieval
    # =========================================================================

    async def create_action(
        self,
        request: PatientActionCreateRequest,
        created_by: Optional[str] = None,
    ) -> PatientActionRecord:
        """Create a new patient action instance."""
        self._check_enabled()

        # Compute expiration horizon
        exp_hours = request.expires_in_hours or getattr(settings, "PATIENT_ACTION_DEFAULT_EXPIRATION_HOURS", 72)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=exp_hours)

        action = PatientActionRecord(
            definition_id=request.definition_id,
            patient_id=request.patient_id,
            organization_id=request.organization_id,
            facility_id=request.facility_id,
            care_team_id=request.care_team_id,
            encounter_id=request.encounter_id,
            title=request.title,
            description=request.description,
            action_type=request.action_type,
            priority=request.priority,
            target_resource_type=request.target_resource_type,
            target_resource_id=request.target_resource_id,
            expires_at=expires_at,
            created_by=created_by,
            metadata=request.metadata,
        )
        saved = await self.action_repo.save_action(action)

        # Record history entry
        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=saved.id,
                from_status=None,
                to_status=ActionStatus.AVAILABLE,
                actor_id=created_by,
                actor_role="SYSTEM_OR_STAFF",
                reason="Patient action created.",
            )
        )

        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_CREATED,
            actor_id=created_by,
            patient_id=saved.patient_id,
            action="patient_action:create",
            resource_id=saved.id,
            metadata={"action_type": saved.action_type.value},
        )

        # Trigger workflow / notification
        await self.workflow_service.on_action_created(saved)
        return saved

    async def get_action(
        self,
        action_id: str,
        current_user: Any,
    ) -> PatientActionRecord:
        """Retrieve a patient action with authorization checks."""
        self._check_enabled()
        action = await self.action_repo.get_action_by_id(action_id)
        if not action:
            raise PatientActionNotFoundException(
                message=f"Patient action '{action_id}' not found."
            )

        # Enforce authorization
        self.auth_service.authorize_patient_access(current_user, action, requested_operation="read")

        actor_id = getattr(current_user, "id", None)
        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_ACCESSED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:read",
            resource_id=action.id,
        )
        return action

    async def list_patient_actions(
        self,
        patient_id: str,
        current_user: Any,
        status: Optional[ActionStatus] = None,
        action_type: Optional[ActionType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PatientActionRecord], int]:
        """List paginated actions for a specific patient."""
        self._check_enabled()
        self.auth_service.authorize_patient_list(current_user, patient_id)

        bounded_size = min(page_size, getattr(settings, "PATIENT_ACTION_MAX_PAGE_SIZE", 100))
        return await self.action_repo.list_actions_by_patient(
            patient_id=patient_id,
            status=status,
            action_type=action_type,
            page=page,
            page_size=bounded_size,
        )

    async def list_admin_actions(
        self,
        current_user: Any,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        status: Optional[ActionStatus] = None,
        action_type: Optional[ActionType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PatientActionRecord], int]:
        """List paginated actions for admin / clinician operational monitoring."""
        self._check_enabled()
        role = getattr(current_user, "role", None)
        if role not in ("ADMIN", "SUPERADMIN", "SYSTEM", "DOCTOR", "CLINICIAN", "NURSE"):
            self.auth_service.authorize_patient_access(current_user, None, requested_operation="admin_list")

        bounded_size = min(page_size, getattr(settings, "PATIENT_ACTION_MAX_PAGE_SIZE", 100))
        return await self.action_repo.list_actions_admin(
            organization_id=organization_id,
            facility_id=facility_id,
            status=status,
            action_type=action_type,
            page=page,
            page_size=bounded_size,
        )

    # =========================================================================
    # Action Transitions: Start, Submit, Complete, Cancel, Acknowledge, Refuse
    # =========================================================================

    async def start_action(
        self,
        action_id: str,
        current_user: Any,
    ) -> PatientActionRecord:
        """Mark an action as started."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)
        self.validation_service.validate_action_for_start(action)

        old_status = action.status
        action.status = ActionStatus.STARTED
        action.started_at = datetime.now(timezone.utc)
        saved = await self.action_repo.save_action(action)

        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=saved.id,
                from_status=old_status,
                to_status=ActionStatus.STARTED,
                actor_id=actor_id,
                actor_role=getattr(current_user, "role", "PATIENT"),
                reason="Patient initiated action.",
            )
        )

        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_STARTED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:start",
            resource_id=action.id,
        )
        return saved

    async def submit_action(
        self,
        action_id: str,
        current_user: Any,
        request: PatientActionSubmitRequest,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientSubmissionRecord:
        """Submit response for a patient action."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        actor_role = getattr(current_user, "role", "PATIENT")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)

        # Idempotency check before state validation to return existing submission on retries
        if request.idempotency_key:
            existing = await self.action_repo.get_submission_by_idempotency_key(request.idempotency_key)
            if existing:
                return existing

        self.validation_service.validate_action_for_submission(action)
        self.validation_service.validate_clinical_safety_boundaries(request.responses)

        submission = await self.submission_service.submit_action(
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            responses=request.responses,
            document_ids=request.document_ids,
            notes=request.notes,
            idempotency_key=request.idempotency_key,
            submission_type=SubmissionType.ACTION_SUBMISSION,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_SUBMITTED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:submit",
            resource_id=action.id,
            metadata={"submission_id": submission.id},
        )

        await self.workflow_service.on_action_submitted(action, submission.id)
        return submission

    async def complete_action(
        self,
        action_id: str,
        current_user: Any,
        request: Optional[PatientActionCompleteRequest] = None,
    ) -> PatientActionRecord:
        """Mark an action as completed."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)
        self.validation_service.validate_action_for_completion(action)

        old_status = action.status
        action.status = ActionStatus.COMPLETED
        action.completed_at = datetime.now(timezone.utc)
        saved = await self.action_repo.save_action(action)

        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=saved.id,
                from_status=old_status,
                to_status=ActionStatus.COMPLETED,
                actor_id=actor_id,
                actor_role=getattr(current_user, "role", "PATIENT"),
                reason=request.notes if request and request.notes else "Action completed.",
            )
        )

        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_COMPLETED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:complete",
            resource_id=action.id,
        )
        return saved

    async def cancel_action(
        self,
        action_id: str,
        current_user: Any,
        request: PatientActionCancelRequest,
    ) -> PatientActionRecord:
        """Cancel an action with reason."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        action = await self.get_action(action_id, current_user)
        self.validation_service.validate_action_for_cancellation(action)

        old_status = action.status
        action.status = ActionStatus.CANCELLED
        action.cancelled_at = datetime.now(timezone.utc)
        action.cancellation_reason = request.reason
        saved = await self.action_repo.save_action(action)

        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=saved.id,
                from_status=old_status,
                to_status=ActionStatus.CANCELLED,
                actor_id=actor_id,
                actor_role=getattr(current_user, "role", "PATIENT"),
                reason=f"Action cancelled: {request.reason}",
            )
        )

        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_CANCELLED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:cancel",
            resource_id=action.id,
            metadata={"cancellation_reason": request.reason},
        )
        return saved

    async def acknowledge_action(
        self,
        action_id: str,
        current_user: Any,
        request: Optional[PatientActionAcknowledgeRequest] = None,
    ) -> PatientActionRecord:
        """Acknowledge notice receipt or care plan delivery."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)
        self.validation_service.validate_action_for_acknowledgement(action)

        old_status = action.status
        action.status = ActionStatus.COMPLETED
        action.completed_at = datetime.now(timezone.utc)
        saved = await self.action_repo.save_action(action)

        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=saved.id,
                from_status=old_status,
                to_status=ActionStatus.COMPLETED,
                actor_id=actor_id,
                actor_role=getattr(current_user, "role", "PATIENT"),
                reason=request.notes if request and request.notes else "Patient acknowledged receipt.",
            )
        )

        # Audit both general and care-plan specific acknowledgement if applicable
        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_ACKNOWLEDGED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:acknowledge",
            resource_id=action.id,
        )

        if action.action_type == ActionType.CARE_PLAN_ACKNOWLEDGEMENT:
            await self._record_audit(
                event_type=AuditEventType.CARE_PLAN_ACKNOWLEDGED,
                actor_id=actor_id,
                patient_id=action.patient_id,
                action="care_plan:acknowledge",
                resource_id=action.target_resource_id or action.id,
            )

        return saved

    async def refuse_action(
        self,
        action_id: str,
        current_user: Any,
        request: PatientActionRefuseRequest,
    ) -> PatientActionRecord:
        """Record explicit patient refusal to perform action."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)
        self.validation_service.validate_action_for_refusal(action)

        old_status = action.status
        action.is_refusal = True
        action.refusal_reason = request.reason
        action.status = ActionStatus.CANCELLED
        action.cancelled_at = datetime.now(timezone.utc)
        action.cancellation_reason = f"Patient Refused: {request.reason}"
        saved = await self.action_repo.save_action(action)

        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=saved.id,
                from_status=old_status,
                to_status=ActionStatus.CANCELLED,
                actor_id=actor_id,
                actor_role=getattr(current_user, "role", "PATIENT"),
                reason=f"Patient declined/refused action: {request.reason}",
            )
        )

        await self._record_audit(
            event_type=AuditEventType.PATIENT_ACTION_REFUSED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:refuse",
            resource_id=action.id,
            metadata={"refusal_reason": request.reason},
        )
        return saved

    async def submit_correction(
        self,
        action_id: str,
        current_user: Any,
        request: PatientActionCorrectionRequest,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientSubmissionRecord:
        """Submit a correction while preserving historical submission records."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        actor_role = getattr(current_user, "role", "PATIENT")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)
        self.validation_service.validate_action_for_correction(action)
        self.validation_service.validate_clinical_safety_boundaries(request.corrected_responses)

        correction = await self.submission_service.submit_correction(
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=request.reason,
            corrected_responses=request.corrected_responses,
            document_ids=request.document_ids,
            notes=request.notes,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        await self._record_audit(
            event_type=AuditEventType.PATIENT_RESPONSE_CORRECTED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:correct",
            resource_id=action.id,
            metadata={"submission_version": correction.submission_version},
        )
        return correction

    async def get_action_history(
        self,
        action_id: str,
        current_user: Any,
    ) -> List[PatientActionHistoryRecord]:
        """Retrieve state transition history for an action."""
        await self.get_action(action_id, current_user)
        return await self.action_repo.get_history_by_action(action_id)

    # =========================================================================
    # Questionnaires & Documents
    # =========================================================================

    async def get_action_questionnaire(
        self,
        action_id: str,
        current_user: Any,
    ) -> QuestionnaireDefinition:
        """Retrieve the questionnaire template linked to this action."""
        action = await self.get_action(action_id, current_user)
        qid = action.metadata.get("questionnaire_id") or action.target_resource_id
        if not qid:
            # Fallback to definition questionnaire_id
            if action.definition_id:
                defn = await self.action_repo.get_definition_by_id(action.definition_id)
                if defn and defn.questionnaire_id:
                    qid = defn.questionnaire_id

        if not qid:
            raise PatientActionValidationFailedException("No questionnaire is associated with this action.")

        q = await self.questionnaire_service.get_questionnaire(qid)
        await self._record_audit(
            event_type=AuditEventType.QUESTIONNAIRE_VIEWED,
            actor_id=getattr(current_user, "id", None),
            patient_id=action.patient_id,
            action="questionnaire:view",
            resource_id=q.id,
        )
        return q

    async def submit_questionnaire(
        self,
        action_id: str,
        current_user: Any,
        request: QuestionnaireSubmissionRequest,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> QuestionnaireResponseRecord:
        """Submit structured answers to an action's questionnaire."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)
        self.validation_service.validate_action_for_submission(action)

        q = await self.get_action_questionnaire(action_id, current_user)

        response_record = await self.questionnaire_service.validate_and_save_response(
            questionnaire_id=q.id,
            action_id=action.id,
            patient_id=action.patient_id,
            answers=request.answers,
            submitted_by=actor_id,
        )

        # Mark action submitted
        action.status = ActionStatus.SUBMITTED
        action.submitted_at = datetime.now(timezone.utc)
        await self.action_repo.save_action(action)

        # Add history
        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=action.id,
                from_status=ActionStatus.AVAILABLE,
                to_status=ActionStatus.SUBMITTED,
                actor_id=actor_id,
                actor_role=getattr(current_user, "role", "PATIENT"),
                reason="Questionnaire submitted.",
                details={"response_id": response_record.id, "questionnaire_id": q.id},
            )
        )

        await self._record_audit(
            event_type=AuditEventType.QUESTIONNAIRE_SUBMITTED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="questionnaire:submit",
            resource_id=q.id,
            metadata={"response_id": response_record.id},
        )

        await self.workflow_service.on_action_submitted(action, response_record.id)
        return response_record

    async def attach_document(
        self,
        action_id: str,
        current_user: Any,
        request: DocumentSubmissionRequest,
    ) -> DocumentSubmissionRecord:
        """Attach a Phase 5 document to this action."""
        self._check_enabled()
        actor_id = getattr(current_user, "id", "anonymous")
        self.validation_service.check_rate_limit(actor_id)

        action = await self.get_action(action_id, current_user)
        if action.status in (ActionStatus.EXPIRED, ActionStatus.CANCELLED):
            raise PatientActionInvalidStateException(
                f"Cannot attach document to action in '{action.status}' state."
            )

        doc = await self.submission_service.attach_document(
            action=action,
            document_id=request.document_id,
            submitted_by=actor_id,
            document_type=request.document_type,
            description=request.description,
        )

        await self._record_audit(
            event_type=AuditEventType.DOCUMENT_SUBMISSION_CREATED,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action="patient_action:attach_document",
            resource_id=doc.id,
            metadata={"document_id": doc.document_id},
        )
        return doc

    async def get_documents(
        self,
        action_id: str,
        current_user: Any,
    ) -> List[DocumentSubmissionRecord]:
        """Retrieve all documents attached to this action."""
        await self.get_action(action_id, current_user)
        return await self.action_repo.get_documents_by_action(action_id)

    # =========================================================================
    # Clinician / Administrative Operational Review
    # =========================================================================

    async def review_action(
        self,
        action_id: str,
        current_user: Any,
        request: PatientActionReviewRequest,
    ) -> PatientActionRecord:
        """Perform clinician review on submitted patient action (ACCEPT, REJECT, REQUEST_CORRECTION)."""
        self._check_enabled()
        role = getattr(current_user, "role", None)
        if role not in ("DOCTOR", "CLINICIAN", "NURSE", "ADMIN", "SUPERADMIN"):
            raise PatientActionValidationFailedException("Only authorized clinicians can review submissions.")

        action = await self.action_repo.get_action_by_id(action_id)
        if not action:
            raise PatientActionNotFoundException(f"Action '{action_id}' not found.")

        old_status = action.status
        outcome = request.review_outcome.upper()

        if outcome == "ACCEPT":
            action.status = ActionStatus.COMPLETED
            action.completed_at = datetime.now(timezone.utc)
            audit_event = AuditEventType.PATIENT_ACTION_COMPLETED
        elif outcome == "REJECT":
            action.status = ActionStatus.REJECTED
            audit_event = AuditEventType.PATIENT_ACTION_REJECTED
        elif outcome == "REQUEST_CORRECTION":
            action.status = ActionStatus.NEEDS_REVIEW
            audit_event = AuditEventType.PATIENT_ACTION_NEEDS_REVIEW
        else:
            raise PatientActionValidationFailedException(
                f"Invalid review outcome '{request.review_outcome}'. Must be ACCEPT, REJECT, or REQUEST_CORRECTION."
            )

        saved = await self.action_repo.save_action(action)
        actor_id = getattr(current_user, "id", "clinician")

        await self.action_repo.add_history_entry(
            PatientActionHistoryRecord(
                action_id=saved.id,
                from_status=old_status,
                to_status=saved.status,
                actor_id=actor_id,
                actor_role=role,
                reason=f"Clinician review outcome: {outcome}. Notes: {request.reviewer_notes or 'None'}",
            )
        )

        await self._record_audit(
            event_type=audit_event,
            actor_id=actor_id,
            patient_id=action.patient_id,
            action=f"patient_action:review_{outcome.lower()}",
            resource_id=action.id,
        )
        return saved

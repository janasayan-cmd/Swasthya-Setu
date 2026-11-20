"""Phase 74: Adoption Exceptions, Consequences & Escalations Service.

Coordinates:
- Operational adoption exception lifecycle (draft, submit, review, active, expiry, escalation)
- Unintended operational consequence reporting and routing to authoritative workflows
- Adoption escalations to management review and operational leadership
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
    AdoptionEscalationRecord,
    AdoptionExceptionRecord,
    AdoptionExceptionStatus,
    ConsequenceStatus,
    CreateAdoptionEscalationRequest,
    CreateAdoptionExceptionRequest,
    EscalateAdoptionExceptionRequest,
    OperationalConsequenceRecord,
    ReportConsequenceRequest,
    ReviewAdoptionExceptionRequest,
    RouteConsequenceRequest,
    SubmitAdoptionExceptionRequest,
)


class AdoptionExceptionConsequenceService:
    """Service governing exceptions, unintended consequences, and escalations."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    # -------------------------------------------------------------------------
    # Exceptions
    # -------------------------------------------------------------------------
    def create_exception(
        self,
        registration_id: str,
        request: CreateAdoptionExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionExceptionRecord:
        """Creates an operational adoption exception."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        exc_id = f"aex_{uuid.uuid4().hex[:12]}"

        record = AdoptionExceptionRecord(
            exception_id=exc_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            baseline_version=request.baseline_version,
            category=request.category,
            title=request.title,
            description=request.description,
            supporting_evidence_ids=request.supporting_evidence_ids,
            risk_reference=request.risk_reference,
            operational_scope=request.operational_scope,
            responsible_owner_id=request.responsible_owner_id,
            requested_duration_days=request.requested_duration_days,
            review_date=request.review_date,
            expiry_date=None,
            authorization_reference=None,
            status=AdoptionExceptionStatus.DRAFT,
            reviewed_by=None,
            reviewed_at=None,
            resolution_requirements=request.resolution_requirements,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_exception(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.exception_created",
            actor_id=current_user.user_id,
            summary=f"Adoption exception '{saved.title}' drafted (Category: {saved.category.value}).",
            details={"exception_id": saved.exception_id},
        )
        return saved

    def get_exception(
        self, exception_id: str, current_user: AuthenticatedUserContext
    ) -> AdoptionExceptionRecord:
        """Retrieves an adoption exception with tenant isolation."""
        exc = self.repo.get_exception(exception_id)
        if not exc or exc.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.ADOPTION_EXCEPTION_NOT_FOUND,
                message=f"Adoption exception '{exception_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return exc

    def list_exceptions_for_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> List[AdoptionExceptionRecord]:
        """Lists exceptions for an adoption registration."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_exceptions_for_registration(registration_id, current_user.tenant_id)

    def submit_exception(
        self,
        exception_id: str,
        request: SubmitAdoptionExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionExceptionRecord:
        """Submits an exception draft for review."""
        exc = self.get_exception(exception_id, current_user)
        if exc.status != AdoptionExceptionStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_ADOPTION_EXCEPTION_STATE,
                message=f"Exception cannot be submitted from status '{exc.status.value}'. Must be DRAFT.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = exc.model_dump()
        updated_dict["status"] = AdoptionExceptionStatus.SUBMITTED
        updated_dict["updated_at"] = now

        saved = self.repo.save_exception(AdoptionExceptionRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=exc.registration_id,
            event_type="governance_change_adoption.exception_submitted",
            actor_id=current_user.user_id,
            summary=f"Adoption exception '{saved.title}' submitted.",
            details={"submission_notes": request.submission_notes},
        )
        return saved

    def review_exception(
        self,
        exception_id: str,
        request: ReviewAdoptionExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionExceptionRecord:
        """Reviews and approves or rejects an exception."""
        exc = self.get_exception(exception_id, current_user)
        if exc.status not in [AdoptionExceptionStatus.SUBMITTED, AdoptionExceptionStatus.UNDER_REVIEW]:
            raise AppException(
                code=ErrorCode.INVALID_ADOPTION_EXCEPTION_STATE,
                message=f"Exception cannot be reviewed from status '{exc.status.value}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = exc.model_dump()
        if request.approved:
            updated_dict["status"] = AdoptionExceptionStatus.ACTIVE
            updated_dict["authorization_reference"] = request.authorization_reference
            updated_dict["expiry_date"] = request.expiry_date
        else:
            updated_dict["status"] = AdoptionExceptionStatus.REJECTED

        updated_dict["reviewed_by"] = current_user.user_id
        updated_dict["reviewed_at"] = now
        updated_dict["updated_at"] = now

        saved = self.repo.save_exception(AdoptionExceptionRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=exc.registration_id,
            event_type="governance_change_adoption.exception_reviewed",
            actor_id=current_user.user_id,
            summary=f"Adoption exception '{saved.title}' reviewed: {saved.status.value}.",
            details={"approved": request.approved, "notes": request.review_notes},
        )
        return saved

    def escalate_exception(
        self,
        exception_id: str,
        request: EscalateAdoptionExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionExceptionRecord:
        """Escalates an exception to a higher governance authority (e.g. Phase 67)."""
        exc = self.get_exception(exception_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = exc.model_dump()
        updated_dict["status"] = AdoptionExceptionStatus.ESCALATED
        updated_dict["updated_at"] = now

        saved = self.repo.save_exception(AdoptionExceptionRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=exc.registration_id,
            event_type="governance_change_adoption.exception_escalated",
            actor_id=current_user.user_id,
            summary=f"Adoption exception '{saved.title}' escalated to {request.destination_workflow}.",
            details={"reason": request.escalation_reason, "destination": request.destination_workflow},
        )
        return saved

    # -------------------------------------------------------------------------
    # Operational Consequences
    # -------------------------------------------------------------------------
    def report_consequence(
        self,
        registration_id: str,
        request: ReportConsequenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> OperationalConsequenceRecord:
        """Reports an unintended operational consequence."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        cq_id = f"cns_{uuid.uuid4().hex[:12]}"

        record = OperationalConsequenceRecord(
            consequence_id=cq_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            title=request.title,
            description=request.description,
            severity=request.severity,
            operational_scope=request.operational_scope,
            reported_by=current_user.user_id,
            reported_at=now,
            status=ConsequenceStatus.REPORTED,
            routed_destination=None,
            destination_reference=None,
            routing_notes=None,
            routed_by=None,
            routed_at=None,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_consequence(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.consequence_reported",
            actor_id=current_user.user_id,
            summary=f"Unintended consequence '{saved.title}' reported (Severity: {saved.severity.value}).",
            details={"consequence_id": saved.consequence_id},
        )
        return saved

    def get_consequence(
        self, consequence_id: str, current_user: AuthenticatedUserContext
    ) -> OperationalConsequenceRecord:
        """Retrieves an operational consequence with tenant isolation."""
        consequence = self.repo.get_consequence(consequence_id)
        if not consequence or consequence.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.OPERATIONAL_CONSEQUENCE_NOT_FOUND,
                message=f"Operational consequence '{consequence_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return consequence

    def list_consequences_for_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> List[OperationalConsequenceRecord]:
        """Lists unintended consequences for an adoption registration."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_consequences_for_registration(registration_id, current_user.tenant_id)

    def route_consequence(
        self,
        consequence_id: str,
        request: RouteConsequenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> OperationalConsequenceRecord:
        """Routes an unintended operational consequence to its authoritative destination workflow."""
        consequence = self.get_consequence(consequence_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = consequence.model_dump()
        updated_dict["status"] = ConsequenceStatus.ROUTED
        updated_dict["routed_destination"] = request.routed_destination
        updated_dict["destination_reference"] = request.destination_reference
        updated_dict["routing_notes"] = request.routing_notes
        updated_dict["routed_by"] = current_user.user_id
        updated_dict["routed_at"] = now
        updated_dict["updated_at"] = now

        saved = self.repo.save_consequence(OperationalConsequenceRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=consequence.registration_id,
            event_type="governance_change_adoption.consequence_routed",
            actor_id=current_user.user_id,
            summary=f"Consequence '{saved.title}' routed to {saved.routed_destination.value} (Ref: {saved.destination_reference}).",
            details={"destination": saved.routed_destination.value, "ref": saved.destination_reference},
        )
        return saved

    # -------------------------------------------------------------------------
    # Escalations
    # -------------------------------------------------------------------------
    def create_escalation(
        self,
        registration_id: str,
        request: CreateAdoptionEscalationRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionEscalationRecord:
        """Creates an adoption-level escalation."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        esc_id = f"esc_{uuid.uuid4().hex[:12]}"

        record = AdoptionEscalationRecord(
            escalation_id=esc_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            title=request.title,
            reason=request.reason,
            urgency=request.urgency,
            escalated_to_destination=request.escalated_to_destination,
            escalated_by=current_user.user_id,
            escalated_at=now,
            acknowledged_by=None,
            acknowledged_at=None,
            resolution_notes=None,
            resolved=False,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_escalation(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.escalated",
            actor_id=current_user.user_id,
            summary=f"Adoption escalation '{saved.title}' raised (Urgency: {saved.urgency.value}).",
            details={"escalation_id": saved.escalation_id, "destination": saved.escalated_to_destination},
        )
        return saved

    def list_escalations_for_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> List[AdoptionEscalationRecord]:
        """Lists escalations for an adoption registration."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_escalations_for_registration(registration_id, current_user.tenant_id)

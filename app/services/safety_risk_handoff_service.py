"""Phase 64: Clinical Safety Risk Handoff Service Orchestrator.

Orchestrates downstream handoffs, acknowledgements, outcome reconciliation,
retries, escalations, and follow-up status for Phase 63 governed risk dispositions.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_risk_handoff_repository import (
    SafetyRiskHandoffRepository,
    get_safety_risk_handoff_repository,
)
from app.repositories.safety_risk_review_repository import (
    SafetyRiskReviewRepository,
    get_safety_risk_review_repository,
)
from app.schemas.safety_risk_handoff import (
    CreateSafetyRiskHandoffRequest,
    DestinationAcknowledgement,
    HandoffDestinationPhase,
    HandoffHistoryEntry,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.schemas.safety_risk_handoff_action import (
    CancelHandoffRequest,
    EscalateHandoffRequest,
    ReconcileHandoffRequest,
    RetryHandoffRequest,
    SubmitHandoffRequest,
)
from app.schemas.safety_risk_handoff_outcome import (
    HandoffOutcomeRecord,
    IngestOutcomeRequest,
)
from app.schemas.safety_risk_handoff_reconciliation import (
    HandoffReconciliationRecord,
)
from app.schemas.safety_risk_handoff_status import HandoffStatusResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_risk_handoff_authorization_service import (
    SafetyRiskHandoffAuthorizationService,
)
from app.services.safety_risk_handoff_concurrency_service import (
    SafetyRiskHandoffConcurrencyService,
)
from app.services.safety_risk_handoff_eligibility_service import (
    SafetyRiskHandoffEligibilityService,
)
from app.services.safety_risk_handoff_escalation_service import (
    SafetyRiskHandoffEscalationService,
)
from app.services.safety_risk_handoff_idempotency_service import (
    SafetyRiskHandoffIdempotencyService,
    get_safety_risk_handoff_idempotency_service,
)
from app.services.safety_risk_handoff_outcome_service import (
    SafetyRiskHandoffOutcomeService,
)
from app.services.safety_risk_handoff_privacy_service import (
    SafetyRiskHandoffPrivacyService,
)
from app.services.safety_risk_handoff_reconciliation_service import (
    SafetyRiskHandoffReconciliationService,
)
from app.services.safety_risk_handoff_retry_service import (
    SafetyRiskHandoffRetryService,
)
from app.services.safety_risk_handoff_submission_service import (
    SafetyRiskHandoffSubmissionService,
)

logger = logging.getLogger(__name__)


class SafetyRiskHandoffService:
    """Primary service coordinator for Phase 64 clinical safety risk handoffs."""

    def __init__(
        self,
        repository: Optional[SafetyRiskHandoffRepository] = None,
        review_repository: Optional[SafetyRiskReviewRepository] = None,
        idempotency_service: Optional[SafetyRiskHandoffIdempotencyService] = None,
    ) -> None:
        self.repository = repository or get_safety_risk_handoff_repository()
        self.review_repo = review_repository or get_safety_risk_review_repository()
        self.idempotency_svc = idempotency_service or get_safety_risk_handoff_idempotency_service()

    def create_handoff(
        self,
        request: CreateSafetyRiskHandoffRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskHandoffRecord:
        """Create a new governed action handoff from an authorized Phase 63 disposition."""
        # 1. Authority and Privacy checks
        SafetyRiskHandoffAuthorizationService.validate_actor_authority(user)
        SafetyRiskHandoffPrivacyService.validate_purpose(request.purpose)

        # 2. Idempotency check
        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "create_handoff", request.model_dump()
        )
        if cached:
            existing = self.repository.get(cached)
            if existing:
                return existing

        # 3. Validate disposition eligibility & determine target destination
        review, disposition, final_dest = (
            SafetyRiskHandoffEligibilityService.validate_disposition_eligibility(
                review_id=request.review_id,
                disposition_id=request.disposition_id,
                destination_phase=request.destination_phase,
                review_repo=self.review_repo,
            )
        )

        # Tenant boundary check
        SafetyRiskHandoffPrivacyService.validate_tenant_access(
            user, review.organization_id, review.facility_id
        )

        # 4. Construct sanitized handoff record
        sanitized_scope = SafetyRiskHandoffPrivacyService.sanitize_payload(
            request.authorized_scope or review.scope or {}
        )

        handoff = SafetyRiskHandoffRecord(
            source_review_id=review.review_id,
            source_disposition_id=disposition.disposition_id,
            source_risk_context_id=review.assessment_id,
            source_revision=str(getattr(review, "version_tag", getattr(review, "risk_context_version", "1"))),
            organization_id=review.organization_id,
            facility_id=review.facility_id,
            destination_phase=final_dest,
            destination_operation=request.destination_operation or "GOVERNED_REVIEW_HANDOFF",
            state=HandoffLifecycleState.READY,
            authorized_scope=sanitized_scope,
            contract_version=request.contract_version or "v1.0.0",
            correlation_id=request.correlation_id or review.assessment_id,
            idempotency_key=request.idempotency_key,
            created_by=user.user_id,
            follow_up_status="READY_FOR_DESTINATION_SUBMISSION",
        )

        entry = HandoffHistoryEntry(
            from_state=HandoffLifecycleState.CREATED,
            to_state=HandoffLifecycleState.READY,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="CREATE_HANDOFF",
            details={
                "review_id": review.review_id,
                "disposition_id": disposition.disposition_id,
                "destination": final_dest.value,
            },
        )
        handoff.history.append(entry)

        saved = self.repository.save(handoff)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "create_handoff", request.model_dump(), saved.handoff_id
            )
        return saved

    def get_handoff(
        self,
        handoff_id: str,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskHandoffRecord:
        """Fetch handoff record enforcing tenant boundaries."""
        handoff = self.repository.get(handoff_id)
        if not handoff:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_HANDOFF_NOT_FOUND,
                message=f"Safety risk handoff '{handoff_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyRiskHandoffPrivacyService.validate_tenant_access(
            user, handoff.organization_id, handoff.facility_id
        )
        return handoff

    def get_status(
        self,
        handoff_id: str,
        user: AuthenticatedUserContext,
    ) -> HandoffStatusResponse:
        """Get operational summary status for a handoff."""
        handoff = self.get_handoff(handoff_id, user)
        return HandoffStatusResponse(
            handoff_id=handoff.handoff_id,
            state=handoff.state,
            destination_phase=handoff.destination_phase,
            is_acknowledged=handoff.acknowledgement is not None,
            is_reconciled=handoff.reconciliation is not None,
            outcomes_count=len(handoff.outcomes),
            retry_count=handoff.retry_count,
            max_retries=handoff.max_retries,
            follow_up_status=handoff.follow_up_status,
            blocking_reason=handoff.blocking_reason,
            escalation_reason=handoff.escalation_reason,
            updated_at=handoff.updated_at,
        )

    def get_history(
        self,
        handoff_id: str,
        user: AuthenticatedUserContext,
    ) -> List[HandoffHistoryEntry]:
        """Fetch immutable state transition audit history."""
        handoff = self.get_handoff(handoff_id, user)
        return handoff.history

    def get_outcomes(
        self,
        handoff_id: str,
        user: AuthenticatedUserContext,
    ) -> List[Dict[str, Any]]:
        """Fetch authorized received outcome records."""
        handoff = self.get_handoff(handoff_id, user)
        return handoff.outcomes

    def submit_handoff(
        self,
        handoff_id: str,
        request: SubmitHandoffRequest,
        user: AuthenticatedUserContext,
    ) -> DestinationAcknowledgement:
        """Submit a pending handoff to its destination adapter."""
        handoff = self.get_handoff(handoff_id, user)
        SafetyRiskHandoffAuthorizationService.validate_actor_authority(user)

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "submit_handoff", request.model_dump()
        )
        if cached and handoff.acknowledgement:
            return handoff.acknowledgement

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        ack = SafetyRiskHandoffSubmissionService.submit_handoff(
            handoff=handoff,
            actor_id=user.user_id,
            actor_role=role_str,
        )
        self.repository.save(handoff)

        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "submit_handoff", request.model_dump(), ack.acknowledgement_id
            )
        return ack

    def ingest_outcome(
        self,
        handoff_id: str,
        request: IngestOutcomeRequest,
        user: AuthenticatedUserContext,
    ) -> HandoffOutcomeRecord:
        """Ingest an outcome reported by a destination phase."""
        handoff = self.get_handoff(handoff_id, user)
        SafetyRiskHandoffAuthorizationService.validate_actor_authority(user)

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "ingest_outcome", request.model_dump()
        )
        if cached:
            for o in handoff.outcomes:
                if o.get("outcome_id") == cached:
                    return HandoffOutcomeRecord(**o)

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        outcome = SafetyRiskHandoffOutcomeService.ingest_outcome(
            handoff=handoff,
            request=request,
            actor_id=user.user_id,
            actor_role=role_str,
        )
        self.repository.save(handoff)

        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "ingest_outcome", request.model_dump(), outcome.outcome_id
            )
        return outcome

    def reconcile_handoff(
        self,
        handoff_id: str,
        request: ReconcileHandoffRequest,
        user: AuthenticatedUserContext,
    ) -> HandoffReconciliationRecord:
        """Perform outcome reconciliation on a handoff."""
        handoff = self.get_handoff(handoff_id, user)
        SafetyRiskHandoffAuthorizationService.validate_actor_authority(user)

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        rec = SafetyRiskHandoffReconciliationService.reconcile(
            handoff=handoff,
            actor_id=user.user_id,
            actor_role=role_str,
            reason=request.reason,
        )
        self.repository.save(handoff)
        return rec

    def retry_handoff(
        self,
        handoff_id: str,
        request: RetryHandoffRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskHandoffRecord:
        """Schedule a bounded retry for an interrupted or failed handoff."""
        handoff = self.get_handoff(handoff_id, user)
        SafetyRiskHandoffAuthorizationService.validate_actor_authority(user)

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        SafetyRiskHandoffRetryService.schedule_retry(
            handoff=handoff,
            reason=request.reason,
            actor_id=user.user_id,
            actor_role=role_str,
        )
        return self.repository.save(handoff)

    def cancel_handoff(
        self,
        handoff_id: str,
        request: CancelHandoffRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskHandoffRecord:
        """Request cancellation when permitted by the destination contract."""
        handoff = self.get_handoff(handoff_id, user)
        SafetyRiskHandoffAuthorizationService.validate_actor_authority(user)

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        SafetyRiskHandoffEscalationService.cancel(
            handoff=handoff,
            reason=request.reason,
            actor_id=user.user_id,
            actor_role=role_str,
        )
        return self.repository.save(handoff)

    def escalate_handoff(
        self,
        handoff_id: str,
        request: EscalateHandoffRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskHandoffRecord:
        """Escalate an unresolved handoff to human governance review."""
        handoff = self.get_handoff(handoff_id, user)
        SafetyRiskHandoffAuthorizationService.validate_actor_authority(user)

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        SafetyRiskHandoffEscalationService.escalate(
            handoff=handoff,
            reason=request.reason,
            actor_id=user.user_id,
            actor_role=role_str,
            severity=request.severity or "HIGH",
        )
        return self.repository.save(handoff)

    # -----------------------------------------------------------------------
    # Filtered List Methods
    # -----------------------------------------------------------------------

    def list_handoffs(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        state: Optional[HandoffLifecycleState] = None,
        destination_phase: Optional[HandoffDestinationPhase] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        return self.repository.list_handoffs(
            organization_id=user.organization_id,
            facility_id=facility_id,
            state=state,
            destination_phase=destination_phase,
            limit=limit,
            offset=offset,
        )

    def list_pending(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        return self.repository.list_pending(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_reconciliation_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        return self.repository.list_reconciliation_required(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_retry_exhausted(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        return self.repository.list_retry_exhausted(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_escalation_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        return self.repository.list_escalation_required(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )


_handoff_service_instance: Optional[SafetyRiskHandoffService] = None


def get_safety_risk_handoff_service() -> SafetyRiskHandoffService:
    global _handoff_service_instance
    if _handoff_service_instance is None:
        _handoff_service_instance = SafetyRiskHandoffService()
    return _handoff_service_instance

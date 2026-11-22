"""Phase 80: Governance Continuity Activation Coordination Service.

Coordinates human-authorized activation decisions, coordinator acknowledgements,
and verified deactivations.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_activation import (
    AcknowledgeActivationRequest,
    AssessActivationRequest,
    AuthorizeActivationDecisionRequest,
    ContinuityActivationStatus,
    CreateActivationRequest,
    DeactivateActivationRequest,
    GovernanceContinuityActivationRecord,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityActivationService:
    """Manages continuity activation requests, human authorization, and deactivation."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_activation_request(
        self,
        tenant_id: str,
        requestor_id: str,
        request: CreateActivationRequest,
    ) -> GovernanceContinuityActivationRecord:
        dis = self.repository.get_disruption(request.triggering_disruption_id)
        if not dis or dis.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DISRUPTION_NOT_FOUND,
                message=f"Disruption '{request.triggering_disruption_id}' was not found.",
                status_code=404,
            )

        act_id = f"GCA-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = GovernanceContinuityActivationRecord(
            activation_id=act_id,
            tenant_id=tenant_id,
            triggering_disruption_id=request.triggering_disruption_id,
            affected_capability_ids=request.affected_capability_ids,
            applicable_plan_id=request.applicable_plan_id,
            plan_version=request.plan_version,
            activation_requestor_id=requestor_id,
            authorized_decision_maker_id=None,
            decision_timestamp=None,
            status=ContinuityActivationStatus.PROPOSED,
            decision_rationale=request.activation_rationale,
            alternative_operating_arrangements=[],
            responsible_coordinator_id=request.responsible_coordinator_id,
            acknowledgement_timestamp=None,
            communication_references=[],
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_activation(record)

    def assess_activation(
        self,
        tenant_id: str,
        assessor_id: str,
        activation_id: str,
        request: AssessActivationRequest,
    ) -> GovernanceContinuityActivationRecord:
        act = self.repository.get_activation(activation_id)
        if not act or act.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ACTIVATION_NOT_FOUND,
                message=f"Continuity activation '{activation_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = act.model_copy(
            update={
                "status": ContinuityActivationStatus.UNDER_ASSESSMENT,
                "updated_at": now_str,
            }
        )
        return self.repository.save_activation(updated)

    def authorize_activation_decision(
        self,
        tenant_id: str,
        authorizer_id: str,
        activation_id: str,
        request: AuthorizeActivationDecisionRequest,
    ) -> GovernanceContinuityActivationRecord:
        act = self.repository.get_activation(activation_id)
        if not act or act.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ACTIVATION_NOT_FOUND,
                message=f"Continuity activation '{activation_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: requestor cannot authorize their own continuity activation
        if authorizer_id == act.activation_requestor_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Requestors cannot authorize their own continuity activations.",
                status_code=403,
            )

        now_str = _get_utc_now_str()
        arrangements = request.alternative_arrangements_approved or act.alternative_operating_arrangements

        updated = act.model_copy(
            update={
                "status": request.status,
                "authorized_decision_maker_id": authorizer_id,
                "decision_timestamp": now_str,
                "decision_rationale": request.decision_rationale,
                "alternative_operating_arrangements": arrangements,
                "updated_at": now_str,
            }
        )
        return self.repository.save_activation(updated)

    def acknowledge_activation(
        self,
        tenant_id: str,
        coordinator_id: str,
        activation_id: str,
        request: AcknowledgeActivationRequest,
    ) -> GovernanceContinuityActivationRecord:
        act = self.repository.get_activation(activation_id)
        if not act or act.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ACTIVATION_NOT_FOUND,
                message=f"Continuity activation '{activation_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        comm_refs = list(act.communication_references)
        if request.acknowledgement_notes:
            comm_refs.append(f"ACK by {coordinator_id}: {request.acknowledgement_notes}")

        updated = act.model_copy(
            update={
                "acknowledgement_timestamp": now_str,
                "communication_references": comm_refs,
                "updated_at": now_str,
            }
        )
        return self.repository.save_activation(updated)

    def deactivate_activation(
        self,
        tenant_id: str,
        deactivator_id: str,
        activation_id: str,
        request: DeactivateActivationRequest,
    ) -> GovernanceContinuityActivationRecord:
        act = self.repository.get_activation(activation_id)
        if not act or act.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ACTIVATION_NOT_FOUND,
                message=f"Continuity activation '{activation_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        comm_refs = list(act.communication_references)
        comm_refs.append(f"Deactivated by {deactivator_id}: {request.deactivation_rationale} (Ref: {request.recovery_verification_reference})")

        updated = act.model_copy(
            update={
                "status": ContinuityActivationStatus.DEACTIVATED,
                "communication_references": comm_refs,
                "updated_at": now_str,
            }
        )
        return self.repository.save_activation(updated)

    def get_activation(
        self,
        tenant_id: str,
        activation_id: str,
    ) -> GovernanceContinuityActivationRecord:
        act = self.repository.get_activation(activation_id)
        if not act or act.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ACTIVATION_NOT_FOUND,
                message=f"Continuity activation '{activation_id}' was not found.",
                status_code=404,
            )
        return act

    def list_activations(
        self,
        tenant_id: str,
        disruption_id: Optional[str] = None,
        status: Optional[ContinuityActivationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityActivationRecord]:
        return self.repository.list_activations(
            tenant_id=tenant_id,
            disruption_id=disruption_id,
            status=status,
            skip=skip,
            limit=limit,
        )

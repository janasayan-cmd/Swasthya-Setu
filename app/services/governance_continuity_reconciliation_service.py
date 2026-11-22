"""Phase 80: Decision and Evidence Continuity & Reconciliation Service.

Captures temporary decisions made during disruptions and manages controlled,
audited reconciliation into authoritative workflows (Phase 72, 63, 54, 49).
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_reconciliation import (
    ReconciliationStatus,
    RecordTemporaryDecisionRequest,
    ReviewReconciliationConflictRequest,
    SubmitReconciliationRequest,
    TemporaryGovernanceDecisionRecord,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityReconciliationService:
    """Manages temporary governance decision logging, provenance preservation, and authoritative reconciliation."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def record_temporary_decision(
        self,
        tenant_id: str,
        author_id: str,
        request: RecordTemporaryDecisionRequest,
    ) -> TemporaryGovernanceDecisionRecord:
        act = self.repository.get_activation(request.activation_id)
        if not act or act.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ACTIVATION_NOT_FOUND,
                message=f"Continuity activation '{request.activation_id}' was not found.",
                status_code=404,
            )

        dec_id = f"TGD-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = TemporaryGovernanceDecisionRecord(
            temporary_decision_id=dec_id,
            tenant_id=tenant_id,
            activation_id=request.activation_id,
            decision_title=request.decision_title,
            decision_summary=request.decision_summary,
            decision_authority_role=request.decision_authority_role,
            authorized_decision_maker_id=request.authorized_decision_maker_id,
            delegation_reference=request.delegation_reference,
            decision_timestamp=request.decision_timestamp,
            supporting_evidence_references=request.supporting_evidence_references or [],
            temporary_documentation_reference=request.temporary_documentation_reference,
            reconciliation_status=ReconciliationStatus.PENDING,
            reconciliation_timestamp=None,
            receiving_authoritative_record_id=None,
            reconciled_by=None,
            conflict_description=None,
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_temporary_decision(record)

    def submit_reconciliation(
        self,
        tenant_id: str,
        reconciler_id: str,
        temporary_decision_id: str,
        request: SubmitReconciliationRequest,
    ) -> TemporaryGovernanceDecisionRecord:
        decision = self.repository.get_temporary_decision(temporary_decision_id)
        if not decision or decision.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.TEMPORARY_DECISION_NOT_FOUND,
                message=f"Temporary governance decision '{temporary_decision_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()

        # Check for potential conflict if target is marked CONFLICT
        if "conflict" in request.receiving_authoritative_record_id.lower():
            updated = decision.model_copy(
                update={
                    "reconciliation_status": ReconciliationStatus.CONFLICT_DETECTED,
                    "conflict_description": f"Conflicting record detected with target: {request.receiving_authoritative_record_id}",
                    "reconciled_by": reconciler_id,
                    "reconciliation_timestamp": now_str,
                    "updated_at": now_str,
                }
            )
            return self.repository.save_temporary_decision(updated)

        updated = decision.model_copy(
            update={
                "reconciliation_status": ReconciliationStatus.RECONCILED,
                "receiving_authoritative_record_id": request.receiving_authoritative_record_id,
                "reconciled_by": reconciler_id,
                "reconciliation_timestamp": now_str,
                "conflict_description": None,
                "updated_at": now_str,
            }
        )
        return self.repository.save_temporary_decision(updated)

    def review_reconciliation_conflict(
        self,
        tenant_id: str,
        reviewer_id: str,
        temporary_decision_id: str,
        request: ReviewReconciliationConflictRequest,
    ) -> TemporaryGovernanceDecisionRecord:
        decision = self.repository.get_temporary_decision(temporary_decision_id)
        if not decision or decision.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.TEMPORARY_DECISION_NOT_FOUND,
                message=f"Temporary governance decision '{temporary_decision_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        target = request.receiving_authoritative_record_id or decision.receiving_authoritative_record_id

        updated = decision.model_copy(
            update={
                "reconciliation_status": request.resolution_disposition,
                "receiving_authoritative_record_id": target,
                "conflict_description": f"Conflict resolved by {reviewer_id}: {request.conflict_resolution_notes}",
                "reconciled_by": reviewer_id,
                "reconciliation_timestamp": now_str,
                "updated_at": now_str,
            }
        )
        return self.repository.save_temporary_decision(updated)

    def get_temporary_decision(
        self,
        tenant_id: str,
        temporary_decision_id: str,
    ) -> TemporaryGovernanceDecisionRecord:
        decision = self.repository.get_temporary_decision(temporary_decision_id)
        if not decision or decision.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.TEMPORARY_DECISION_NOT_FOUND,
                message=f"Temporary governance decision '{temporary_decision_id}' was not found.",
                status_code=404,
            )
        return decision

    def list_temporary_decisions(
        self,
        tenant_id: str,
        activation_id: Optional[str] = None,
        reconciliation_status: Optional[ReconciliationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[TemporaryGovernanceDecisionRecord]:
        return self.repository.list_temporary_decisions(
            tenant_id=tenant_id,
            activation_id=activation_id,
            reconciliation_status=reconciliation_status,
            skip=skip,
            limit=limit,
        )

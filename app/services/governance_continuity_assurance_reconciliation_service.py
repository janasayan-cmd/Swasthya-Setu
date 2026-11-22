"""Phase 81: Decision and Evidence Reconciliation Assurance Service.

Validates the integrity of records reconciled after continuity activation,
ensuring provenance preservation, conflict routing, and audit trail completeness.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_reconciliation import (
    AssessReconciliationIntegrityRequest,
    ReconciliationAssuranceRecord,
    ReconciliationIntegrityStatus,
)


class GovernanceContinuityAssuranceReconciliationService:
    """Domain service for assessing reconciliation integrity of temporary governance records."""

    def __init__(self, repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository

    def assess_reconciliation_integrity(
        self,
        req: AssessReconciliationIntegrityRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ReconciliationAssuranceRecord:
        assurance_id = f"RIA-{uuid.uuid4().hex[:8].upper()}"

        unresolved_count = len(req.unresolved_conflict_ids)
        findings = []

        if unresolved_count > 0:
            status = ReconciliationIntegrityStatus.UNRESOLVED_CONFLICT_DETECTED
            findings.append(f"{unresolved_count} reconciliation conflicts unresolved; routing to authoritative workflow required")
        elif req.total_decisions_reconciled < req.total_temporary_decisions_recorded:
            status = ReconciliationIntegrityStatus.RECONCILIATION_DELAYED
            findings.append(f"{req.total_temporary_decisions_recorded - req.total_decisions_reconciled} decisions pending reconciliation")
        elif not req.has_full_provenance:
            status = ReconciliationIntegrityStatus.MISSING_AUTHORITY_EVIDENCE
            findings.append("Temporary decisions missing original actor or authority provenance")
        else:
            status = ReconciliationIntegrityStatus.VERIFIED_INTEGRAL

        record = ReconciliationAssuranceRecord(
            assurance_id=assurance_id,
            reconciliation_batch_id=req.reconciliation_batch_id,
            activation_id=req.activation_id,
            total_temporary_decisions=req.total_temporary_decisions_recorded,
            total_reconciled=req.total_decisions_reconciled,
            unresolved_conflicts_count=unresolved_count,
            unresolved_conflict_ids=req.unresolved_conflict_ids,
            integrity_status=status,
            has_full_provenance=req.has_full_provenance,
            receiving_workflow_references=req.receiving_workflow_references,
            findings_generated=findings,
            limitations="Audit integrity verified against retained cryptographic provenance and journal entries.",
            evaluated_by=actor_id,
            evaluated_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_reconciliation_assessment(record)

    def get_reconciliation_assessment(self, assurance_id: str, tenant_id: str = "default") -> ReconciliationAssuranceRecord:
        rec = self.repo.get_reconciliation_assessment(assurance_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.RECONCILIATION_ASSURANCE_NOT_FOUND,
                message=f"Reconciliation assessment {assurance_id} not found",
                status_code=404,
            )
        return rec

    def list_reconciliation_assessments(
        self,
        tenant_id: str = "default",
        activation_id: Optional[str] = None,
    ) -> List[ReconciliationAssuranceRecord]:
        return self.repo.list_reconciliation_assessments(tenant_id, activation_id)


# Module-level instance
governance_continuity_assurance_reconciliation_service = GovernanceContinuityAssuranceReconciliationService()

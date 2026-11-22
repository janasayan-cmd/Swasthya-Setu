"""Phase 81: Independent Continuity Validation Programme Service.

Supports formal independent validation reviews with evaluator assignment,
independence declarations, conflict-of-interest checks, and management responses.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_programme import (
    AssignEvaluatorRequest,
    CreateValidationProgrammeRequest,
    IndependenceCheckResult,
    IndependentValidationProgrammeRecord,
    ProgrammeStatus,
    RecordIndependenceDeclarationRequest,
    SubmitEvidenceRequest,
)


class GovernanceContinuityAssuranceProgrammeService:
    """Domain service for managing independent continuity validation programmes."""

    def __init__(self, repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository

    def create_programme(
        self,
        req: CreateValidationProgrammeRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> IndependentValidationProgrammeRecord:
        programme_id = f"IVP-{uuid.uuid4().hex[:8].upper()}"

        record = IndependentValidationProgrammeRecord(
            programme_id=programme_id,
            programme_name=req.programme_name,
            scope_description=req.scope_description,
            objectives=req.objectives,
            framework_version=req.framework_version,
            target_plan_ids=req.target_plan_ids,
            status=ProgrammeStatus.PLANNED,
            assigned_evaluators=[],
            independence_status=IndependenceCheckResult.PENDING_DECLARATION,
            evidence_requests=[],
            associated_finding_ids=[],
            created_by=actor_id,
            created_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_validation_programme(record)

    def assign_evaluator(
        self,
        programme_id: str,
        req: AssignEvaluatorRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> IndependentValidationProgrammeRecord:
        rec = self.repo.get_validation_programme(programme_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.VALIDATION_PROGRAMME_NOT_FOUND,
                message=f"Validation programme {programme_id} not found",
                status_code=404,
            )
        if rec.status in (ProgrammeStatus.APPROVED, ProgrammeStatus.CLOSED):
            raise AppException(
                code=ErrorCode.INVALID_VALIDATION_PROGRAMME_STATE,
                message=f"Programme {programme_id} is in status {rec.status} and cannot accept new evaluators",
                status_code=400,
            )

        existing_ids = [e["evaluator_id"] for e in rec.assigned_evaluators]
        if req.evaluator_id not in existing_ids:
            rec.assigned_evaluators.append({
                "evaluator_id": req.evaluator_id,
                "evaluator_name": req.evaluator_name,
                "evaluator_organization": req.evaluator_organization,
                "is_external_or_independent": req.is_external_or_independent,
                "assigned_at": datetime.utcnow().isoformat(),
                "assigned_by": actor_id,
            })
            rec.status = ProgrammeStatus.IN_PROGRESS
        return self.repo.save_validation_programme(rec)

    def record_independence_declaration(
        self,
        programme_id: str,
        req: RecordIndependenceDeclarationRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> IndependentValidationProgrammeRecord:
        rec = self.repo.get_validation_programme(programme_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.VALIDATION_PROGRAMME_NOT_FOUND,
                message=f"Validation programme {programme_id} not found",
                status_code=404,
            )

        assigned = next((e for e in rec.assigned_evaluators if e["evaluator_id"] == req.evaluator_id), None)
        if not assigned:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_ACCESS_DENIED,
                message=f"Evaluator {req.evaluator_id} is not assigned to programme {programme_id}",
                status_code=403,
            )

        if req.has_conflict_of_interest:
            rec.independence_status = IndependenceCheckResult.CONFLICT_OF_INTEREST_IDENTIFIED
            assigned["conflict_of_interest"] = True
            assigned["conflict_details"] = req.conflict_details
        else:
            rec.independence_status = IndependenceCheckResult.INDEPENDENT_CONFIRMED
            assigned["conflict_of_interest"] = False
            assigned["declaration_statement"] = req.declaration_statement

        return self.repo.save_validation_programme(rec)

    def submit_evidence_request(
        self,
        programme_id: str,
        req: SubmitEvidenceRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> IndependentValidationProgrammeRecord:
        rec = self.repo.get_validation_programme(programme_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.VALIDATION_PROGRAMME_NOT_FOUND,
                message=f"Validation programme {programme_id} not found",
                status_code=404,
            )

        # Conflict check
        if rec.independence_status == IndependenceCheckResult.CONFLICT_OF_INTEREST_IDENTIFIED:
            raise AppException(
                code=ErrorCode.CONFLICT_OF_INTEREST_DETECTED,
                message="Cannot submit evidence request under a programme with unmitigated conflict of interest",
                status_code=400,
            )

        rec.evidence_requests.append({
            "request_id": f"EVR-{uuid.uuid4().hex[:6].upper()}",
            "target_id": req.target_capability_or_plan_id,
            "description": req.evidence_description,
            "document_ref": req.evidence_document_ref,
            "submitted_by": actor_id,
            "submitted_at": datetime.utcnow().isoformat(),
        })
        return self.repo.save_validation_programme(rec)

    def approve_programme_report(
        self,
        programme_id: str,
        management_response: str,
        actor_id: str,
        tenant_id: str = "default",
    ) -> IndependentValidationProgrammeRecord:
        rec = self.repo.get_validation_programme(programme_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.VALIDATION_PROGRAMME_NOT_FOUND,
                message=f"Validation programme {programme_id} not found",
                status_code=404,
            )

        # Separation of duties: creator or assigned evaluators cannot approve the final report
        assigned_ids = [e["evaluator_id"] for e in rec.assigned_evaluators]
        if actor_id in assigned_ids or rec.created_by == actor_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Assigned evaluator or programme creator cannot approve their own independent validation report",
                status_code=400,
            )

        rec.status = ProgrammeStatus.APPROVED
        rec.management_response = management_response
        rec.approved_by = actor_id
        rec.approved_at = datetime.utcnow()
        return self.repo.save_validation_programme(rec)

    def get_programme(self, programme_id: str, tenant_id: str = "default") -> IndependentValidationProgrammeRecord:
        rec = self.repo.get_validation_programme(programme_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.VALIDATION_PROGRAMME_NOT_FOUND,
                message=f"Validation programme {programme_id} not found",
                status_code=404,
            )
        return rec

    def list_programmes(
        self,
        tenant_id: str = "default",
        status: Optional[ProgrammeStatus] = None,
    ) -> List[IndependentValidationProgrammeRecord]:
        return self.repo.list_validation_programmes(tenant_id, status)


# Module-level instance
governance_continuity_assurance_programme_service = GovernanceContinuityAssuranceProgrammeService()

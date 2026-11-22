"""Phase 81: Personnel and Delegated Authority Readiness Service.

Evaluates critical role coverage, approved substitutes, and verifies delegated
authority against the authoritative authorization framework without duplicating HR data.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_personnel import (
    AssessPersonnelReadinessRequest,
    PersonnelReadinessAssuranceRecord,
    ReadinessStatus,
    VerifyDelegatedAuthorityRequest,
)


class GovernanceContinuityAssurancePersonnelService:
    """Domain service for personnel continuity and delegated authority assurance."""

    def __init__(self, repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository

    def assess_readiness(
        self,
        req: AssessPersonnelReadinessRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> PersonnelReadinessAssuranceRecord:
        readiness_id = f"PAR-{uuid.uuid4().hex[:8].upper()}"

        has_substitute = bool(req.approved_substitute_id)
        has_doc = bool(req.authority_source_doc_ref)
        has_evidence = bool(req.competency_evidence_ref)

        gaps = []
        if not has_substitute:
            gaps.append("Missing approved substitute")
        if not has_doc:
            gaps.append("Missing formal delegation documentation")
        if not has_evidence:
            gaps.append("Missing competency evidence")

        status = ReadinessStatus.UNVERIFIED_AUTHORITY if not gaps else ReadinessStatus.SUBSTITUTE_MISSING

        record = PersonnelReadinessAssuranceRecord(
            readiness_id=readiness_id,
            role_key=req.role_key,
            role_name=req.role_name,
            primary_owner_id=req.primary_owner_id,
            approved_substitute_id=req.approved_substitute_id,
            organizational_scope=req.organizational_scope,
            authority_source_doc_ref=req.authority_source_doc_ref,
            competency_evidence_ref=req.competency_evidence_ref,
            readiness_status=status,
            authority_verified_valid=False,
            separation_of_duties_verified=False,
            last_exercise_participated_ref=req.last_exercise_participated_ref,
            outstanding_readiness_gaps=gaps,
            evaluated_by=actor_id,
            evaluated_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_personnel_readiness(record)

    def verify_delegated_authority(
        self,
        readiness_id: str,
        req: VerifyDelegatedAuthorityRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> PersonnelReadinessAssuranceRecord:
        rec = self.repo.get_personnel_readiness(readiness_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.PERSONNEL_READINESS_NOT_FOUND,
                message=f"Personnel readiness record {readiness_id} not found",
                status_code=404,
            )

        # Separation of duties: primary owner or substitute cannot verify their own readiness
        if rec.primary_owner_id == actor_id or rec.approved_substitute_id == actor_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Primary owner or substitute cannot verify their own delegated authority readiness",
                status_code=400,
            )

        rec.authority_verified_valid = req.verified_valid
        rec.delegation_expiration_date = req.delegation_expiration_date
        rec.separation_of_duties_verified = req.separation_of_duties_verified
        rec.verified_by = actor_id
        rec.verified_at = datetime.utcnow()

        if req.verified_valid and req.separation_of_duties_verified:
            rec.readiness_status = ReadinessStatus.VERIFIED_READY
            rec.outstanding_readiness_gaps = []
        elif not req.separation_of_duties_verified:
            rec.readiness_status = ReadinessStatus.SEPARATION_OF_DUTIES_CONFLICT
            rec.outstanding_readiness_gaps.append("Separation of duties conflict detected")
        else:
            rec.readiness_status = ReadinessStatus.CONDITIONALLY_READY
            rec.outstanding_readiness_gaps.append("Authority verification conditional: " + (req.verification_notes or ""))

        return self.repo.save_personnel_readiness(rec)

    def get_personnel_readiness(self, readiness_id: str, tenant_id: str = "default") -> PersonnelReadinessAssuranceRecord:
        rec = self.repo.get_personnel_readiness(readiness_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.PERSONNEL_READINESS_NOT_FOUND,
                message=f"Personnel readiness record {readiness_id} not found",
                status_code=404,
            )
        return rec

    def list_personnel_readiness(
        self,
        tenant_id: str = "default",
        role_key: Optional[str] = None,
    ) -> List[PersonnelReadinessAssuranceRecord]:
        return self.repo.list_personnel_readiness(tenant_id, role_key)


# Module-level instance
governance_continuity_assurance_personnel_service = GovernanceContinuityAssurancePersonnelService()

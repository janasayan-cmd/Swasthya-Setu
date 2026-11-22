"""Phase 81: Continuity Finding Management Service.

Structured management of continuity assurance findings across 12 categories,
routing to Phase 54 CAPA, Phase 63 Risk, Phase 67 Exception, and Phase 70 Audit.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_finding import (
    CloseFindingRequest,
    ContinuityAssuranceFindingRecord,
    CreateContinuityFindingRequest,
    FindingStatus,
    ReferFindingRequest,
)


class GovernanceContinuityAssuranceFindingService:
    """Domain service for managing continuity assurance findings and authoritative referrals."""

    def __init__(self, repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository

    def create_finding(
        self,
        req: CreateContinuityFindingRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityAssuranceFindingRecord:
        finding_id = f"CAF-{uuid.uuid4().hex[:8].upper()}"

        record = ContinuityAssuranceFindingRecord(
            finding_id=finding_id,
            category=req.category,
            severity=req.severity,
            title=req.title,
            description=req.description,
            affected_capability_id=req.affected_capability_id,
            related_plan_id=req.related_plan_id,
            related_plan_version=req.related_plan_version,
            source_evidence_ref=req.source_evidence_ref,
            validation_criteria_ref=req.validation_criteria_ref,
            detection_method=req.detection_method,
            impact_description=req.impact_description,
            assigned_owner=req.assigned_owner,
            recommended_action=req.recommended_action,
            status=FindingStatus.IDENTIFIED,
            limitations=req.limitations or "Finding identifies continuity gap; does not determine clinical risk acceptance.",
            identified_by=actor_id,
            identified_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_finding(record)

    def refer_finding(
        self,
        finding_id: str,
        req: ReferFindingRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityAssuranceFindingRecord:
        rec = self.repo.get_finding(finding_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CONTINUITY_FINDING_NOT_FOUND,
                message=f"Continuity finding {finding_id} not found",
                status_code=404,
            )

        destination = req.destination_workflow.upper()
        if "CAPA" in destination:
            rec.status = FindingStatus.REFERRED_TO_CAPA
        elif "RISK" in destination:
            rec.status = FindingStatus.REFERRED_TO_RISK
        elif "AUDIT" in destination:
            rec.status = FindingStatus.REFERRED_TO_AUDIT
        elif "REVIEW" in destination or "MANAGEMENT" in destination:
            rec.status = FindingStatus.REFERRED_TO_MANAGEMENT_REVIEW
        else:
            rec.status = FindingStatus.UNDER_REVIEW

        rec.destination_workflow = destination
        rec.referral_reference_id = req.referral_reference_id
        rec.referral_notes = req.referral_notes
        rec.updated_at = datetime.utcnow()
        return self.repo.save_finding(rec)

    def close_finding(
        self,
        finding_id: str,
        req: CloseFindingRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityAssuranceFindingRecord:
        rec = self.repo.get_finding(finding_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CONTINUITY_FINDING_NOT_FOUND,
                message=f"Continuity finding {finding_id} not found",
                status_code=404,
            )

        # Separation of duties: assigned owner cannot close finding without independent confirmation
        if rec.assigned_owner == actor_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Assigned action owner cannot self-close their own continuity finding",
                status_code=400,
            )

        # Where required, verified effectiveness must come from Phase 55
        if req.phase55_effectiveness_ref:
            rec.status = FindingStatus.VERIFIED_EFFECTIVE_BY_PHASE55
            rec.phase55_effectiveness_ref = req.phase55_effectiveness_ref
        else:
            rec.status = FindingStatus.CLOSED

        rec.closure_rationale = req.closure_rationale
        rec.closed_at = datetime.utcnow()
        rec.updated_at = datetime.utcnow()
        return self.repo.save_finding(rec)

    def get_finding(self, finding_id: str, tenant_id: str = "default") -> ContinuityAssuranceFindingRecord:
        rec = self.repo.get_finding(finding_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CONTINUITY_FINDING_NOT_FOUND,
                message=f"Continuity finding {finding_id} not found",
                status_code=404,
            )
        return rec

    def list_findings(
        self,
        tenant_id: str = "default",
        status: Optional[FindingStatus] = None,
    ) -> List[ContinuityAssuranceFindingRecord]:
        return self.repo.list_findings(tenant_id, status)


# Module-level instance
governance_continuity_assurance_finding_service = GovernanceContinuityAssuranceFindingService()

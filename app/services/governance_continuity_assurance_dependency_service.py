"""Phase 81: Critical Dependency Resilience Assurance Service.

Evaluates dependencies from Phase 80 (personnel, system, information, external),
identifies single points of failure (SPOFs), and verifies tested alternative availability.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_dependency import (
    AssessDependencyResilienceRequest,
    DependencyResilienceAssuranceRecord,
    DependencyResilienceEvaluation,
)


class GovernanceContinuityAssuranceDependencyService:
    """Domain service for assessing critical dependency resilience."""

    def __init__(self, repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository

    def assess_dependency(
        self,
        req: AssessDependencyResilienceRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> DependencyResilienceAssuranceRecord:
        assessment_id = f"DRA-{uuid.uuid4().hex[:8].upper()}"

        is_spof = not req.has_alternative
        follow_up = []

        if is_spof:
            evaluation = DependencyResilienceEvaluation.SINGLE_POINT_OF_FAILURE
            follow_up.append("Establish and document validated alternative operating arrangement")
        elif not req.testing_evidence_ref:
            evaluation = DependencyResilienceEvaluation.DOCUMENTED_UNTESTED
            follow_up.append("Execute formal continuity exercise or simulation to validate alternative")
        else:
            # Check evidence age (if older than 365 days, considered stale)
            now = datetime.now(timezone.utc)
            evidence_time = req.evidence_timestamp
            if evidence_time and evidence_time.tzinfo is None:
                evidence_time = evidence_time.replace(tzinfo=timezone.utc)

            if evidence_time and (now - evidence_time).days > 365:
                evaluation = DependencyResilienceEvaluation.EVIDENCE_STALE
                follow_up.append("Testing evidence exceeds 1-year currency threshold; re-validation required")
            else:
                evaluation = DependencyResilienceEvaluation.RESILIENT_TESTED

        record = DependencyResilienceAssuranceRecord(
            assessment_id=assessment_id,
            dependency_id=req.dependency_id,
            source_capability_id=req.source_capability_id,
            dependency_type=req.dependency_type,
            criticality=req.criticality,
            has_alternative=req.has_alternative,
            alternative_arrangement_ref=req.alternative_arrangement_ref,
            testing_evidence_ref=req.testing_evidence_ref,
            evidence_timestamp=req.evidence_timestamp,
            is_spof=is_spof,
            resilience_evaluation=evaluation,
            unresolved_limitations="Dependency resilience evaluation depends on provider SLAs and exercise scope.",
            recommended_follow_up=follow_up,
            evaluated_by=actor_id,
            evaluated_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_dependency_assessment(record)

    def get_dependency_assessment(self, assessment_id: str, tenant_id: str = "default") -> DependencyResilienceAssuranceRecord:
        rec = self.repo.get_dependency_assessment(assessment_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.DEPENDENCY_ASSURANCE_NOT_FOUND,
                message=f"Dependency assessment {assessment_id} not found",
                status_code=404,
            )
        return rec

    def list_dependency_assessments(
        self,
        tenant_id: str = "default",
        dependency_id: Optional[str] = None,
    ) -> List[DependencyResilienceAssuranceRecord]:
        return self.repo.list_dependency_assessments(tenant_id, dependency_id)


# Module-level instance
governance_continuity_assurance_dependency_service = GovernanceContinuityAssuranceDependencyService()

"""Phase 80: Governance Dependency Mapping Service.

Maps dependencies across personnel, systems, information, and external partners,
identifying single points of failure (SPOFs) and unvalidated alternatives.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_dependency import (
    ContinuityDependencyType,
    CreateDependencyRequest,
    DependencyStatus,
    DependencyValidationResult,
    GovernanceContinuityDependencyRecord,
    ValidateDependencyRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityDependencyService:
    """Manages governance dependency mapping, validation, and SPOF analysis."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_dependency(
        self,
        tenant_id: str,
        request: CreateDependencyRequest,
    ) -> GovernanceContinuityDependencyRecord:
        cap = self.repository.get_capability(request.source_capability_id)
        if not cap or cap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_CAPABILITY_NOT_FOUND,
                message=f"Governance capability '{request.source_capability_id}' was not found.",
                status_code=404,
            )

        dep_id = f"GCD-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        # If has_validated_alternative is False, flag as potential single point of failure
        is_spof = request.is_single_point_of_failure or (not request.has_validated_alternative)
        status = DependencyStatus.IDENTIFIED if not request.has_validated_alternative else DependencyStatus.VALIDATED

        record = GovernanceContinuityDependencyRecord(
            dependency_id=dep_id,
            tenant_id=tenant_id,
            source_capability_id=request.source_capability_id,
            dependency_type=request.dependency_type,
            target_reference=request.target_reference,
            criticality=request.criticality,
            responsible_owner_id=request.responsible_owner_id,
            availability_requirements=request.availability_requirements,
            has_validated_alternative=request.has_validated_alternative,
            alternative_arrangement_description=request.alternative_arrangement_description or "",
            is_single_point_of_failure=is_spof,
            last_validation_date=now_str if request.has_validated_alternative else None,
            status=status,
            evidence_references=request.evidence_references or [],
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_dependency(record)

    def validate_dependency(
        self,
        tenant_id: str,
        dependency_id: str,
        request: ValidateDependencyRequest,
    ) -> GovernanceContinuityDependencyRecord:
        dep = self.repository.get_dependency(dependency_id)
        if not dep or dep.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DEPENDENCY_NOT_FOUND,
                message=f"Governance dependency '{dependency_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated_evidence = list(dep.evidence_references)
        if request.evidence_reference and request.evidence_reference not in updated_evidence:
            updated_evidence.append(request.evidence_reference)

        updated = dep.model_copy(
            update={
                "status": request.status,
                "has_validated_alternative": request.has_validated_alternative,
                "alternative_arrangement_description": request.alternative_arrangement_description if request.alternative_arrangement_description is not None else dep.alternative_arrangement_description,
                "is_single_point_of_failure": request.is_single_point_of_failure,
                "last_validation_date": now_str,
                "evidence_references": updated_evidence,
                "updated_at": now_str,
            }
        )
        return self.repository.save_dependency(updated)

    def get_dependency(
        self,
        tenant_id: str,
        dependency_id: str,
    ) -> GovernanceContinuityDependencyRecord:
        dep = self.repository.get_dependency(dependency_id)
        if not dep or dep.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DEPENDENCY_NOT_FOUND,
                message=f"Governance dependency '{dependency_id}' was not found.",
                status_code=404,
            )
        return dep

    def list_dependencies(
        self,
        tenant_id: str,
        capability_id: Optional[str] = None,
        dependency_type: Optional[ContinuityDependencyType] = None,
        status: Optional[DependencyStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityDependencyRecord]:
        return self.repository.list_dependencies(
            tenant_id=tenant_id,
            capability_id=capability_id,
            dependency_type=dependency_type,
            status=status,
            skip=skip,
            limit=limit,
        )

    def evaluate_dependencies_and_spofs(
        self,
        tenant_id: str,
    ) -> DependencyValidationResult:
        all_deps = self.repository.list_all_dependencies(tenant_id)
        spofs = [d for d in all_deps if d.is_single_point_of_failure]
        unvalidated = [d for d in all_deps if not d.has_validated_alternative or d.status == DependencyStatus.UNVALIDATED]

        return DependencyValidationResult(
            tenant_id=tenant_id,
            total_dependencies=len(all_deps),
            single_points_of_failure=spofs,
            unvalidated_dependencies=unvalidated,
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
        )

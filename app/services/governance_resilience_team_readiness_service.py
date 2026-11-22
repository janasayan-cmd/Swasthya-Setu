"""Phase 84: Team Readiness Assessment Service.

Evaluates collective team readiness without averaging scores, ensuring that
critical role vacancies and backup coverage deficits remain explicitly visible.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_team_readiness import (
    AssessTeamReadinessRequest,
    TeamReadinessOutcome,
    TeamReadinessRecord,
)


class GovernanceResilienceTeamReadinessService:
    """Service managing team readiness evaluations and role coverage analysis."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def assess_team_readiness(
        self,
        tenant_id: str,
        user_id: str,
        request: AssessTeamReadinessRequest,
    ) -> TeamReadinessRecord:
        # Evaluate role coverage: identify critical vacancies and backup deficits
        critical_vacancies: List[str] = []
        backup_deficits: List[str] = []
        all_verified = True

        for item in request.role_coverage:
            if item.is_vacant or not item.primary_user_id:
                critical_vacancies.append(item.role_name)
                all_verified = False
            elif not item.backup_user_id:
                backup_deficits.append(item.role_name)
                all_verified = False
            elif not item.has_verified_evidence:
                all_verified = False

        # Determine outcome strictly (NOT a simple average!)
        if critical_vacancies:
            outcome = TeamReadinessOutcome.CRITICAL_ROLES_VACANT
        elif backup_deficits:
            outcome = TeamReadinessOutcome.BACKUP_COVERAGE_DEFICIT
        elif not all_verified:
            outcome = TeamReadinessOutcome.DEMONSTRATION_DEFICIT
        elif request.conditions_imposed:
            outcome = TeamReadinessOutcome.READY_SUBJECT_TO_CONDITIONS
        else:
            outcome = TeamReadinessOutcome.VERIFIED_READY

        assessment_id = f"tmr-{uuid.uuid4().hex[:10]}"
        record = TeamReadinessRecord(
            team_assessment_id=assessment_id,
            tenant_id=tenant_id,
            team_name=request.team_name,
            department_id=request.department_id,
            facility_id=request.facility_id,
            framework_id=request.framework_id,
            framework_version=request.framework_version,
            role_coverage=request.role_coverage,
            critical_vacancies=critical_vacancies,
            backup_deficits=backup_deficits,
            readiness_outcome=outcome,
            conditions_imposed=request.conditions_imposed,
            limitations=request.limitations,
            assessed_by=user_id,
        )
        return self.repository.save_team_readiness(record)

    def get_team_readiness(
        self, tenant_id: str, team_assessment_id: str
    ) -> TeamReadinessRecord:
        record = self.repository.get_team_readiness(team_assessment_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.TEAM_READINESS_NOT_FOUND,
                message=f"Team readiness record '{team_assessment_id}' not found.",
                status_code=404,
            )
        return record

    def list_team_readiness(
        self,
        tenant_id: str,
        department_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        outcome: Optional[TeamReadinessOutcome] = None,
    ) -> List[TeamReadinessRecord]:
        return self.repository.list_team_readiness(
            tenant_id=tenant_id,
            department_id=department_id,
            facility_id=facility_id,
            outcome=outcome,
        )


_team_readiness_service = GovernanceResilienceTeamReadinessService()


def get_governance_resilience_team_readiness_service() -> GovernanceResilienceTeamReadinessService:
    return _team_readiness_service

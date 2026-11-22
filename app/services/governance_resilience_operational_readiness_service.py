"""Phase 84: Operational Readiness Verification Service.

Verifies operational readiness across organization, facility, department, and team scopes
with explicit verification criteria and independent separation of duties.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_operational_readiness import (
    AssessOperationalReadinessRequest,
    OperationalReadinessOutcome,
    OperationalReadinessRecord,
    OperationalReadinessScope,
    VerifyOperationalReadinessRequest,
)


class GovernanceResilienceOperationalReadinessService:
    """Service assessing and independently verifying multi-scope operational readiness."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def assess_readiness(
        self,
        tenant_id: str,
        assessor_id: str,
        request: AssessOperationalReadinessRequest,
    ) -> OperationalReadinessRecord:
        readiness_id = f"op-rdy-{uuid.uuid4().hex[:10]}"
        record = OperationalReadinessRecord(
            readiness_id=readiness_id,
            tenant_id=tenant_id,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            framework_version=request.framework_version,
            critical_unmet_requirements=request.critical_unmet_requirements,
            unresolved_exceptions=request.unresolved_exceptions,
            outcome=request.outcome,
            conditions=request.conditions,
            valid_until=request.valid_until,
            assessor_id=assessor_id,
        )
        return self.repository.save_operational_readiness(record)

    def get_readiness(self, tenant_id: str, readiness_id: str) -> OperationalReadinessRecord:
        record = self.repository.get_operational_readiness(readiness_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.OPERATIONAL_READINESS_NOT_FOUND,
                message=f"Operational readiness record '{readiness_id}' not found.",
                status_code=404,
            )
        return record

    def verify_readiness(
        self,
        tenant_id: str,
        readiness_id: str,
        verifier_id: str,
        request: VerifyOperationalReadinessRequest,
    ) -> OperationalReadinessRecord:
        record = self.get_readiness(tenant_id, readiness_id)

        # Separation of duties: Verifier cannot be assessor
        if verifier_id == record.assessor_id:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Operational readiness assessor cannot independently verify their own assessment.",
                status_code=400,
            )

        if request.verified:
            record.outcome = OperationalReadinessOutcome.VERIFIED_READY
            record.verifier_id = verifier_id
            record.verified_at = datetime.utcnow()
            if request.conditions:
                record.conditions = request.conditions
        else:
            record.outcome = OperationalReadinessOutcome.REASSESSMENT_REQUIRED

        return self.repository.save_operational_readiness(record)

    def list_readiness(
        self,
        tenant_id: str,
        scope_type: Optional[OperationalReadinessScope] = None,
        outcome: Optional[OperationalReadinessOutcome] = None,
    ) -> List[OperationalReadinessRecord]:
        return self.repository.list_operational_readiness(
            tenant_id=tenant_id,
            scope_type=scope_type,
            outcome=outcome,
        )

    def get_readiness_history(
        self, tenant_id: str, readiness_id: str
    ) -> List[OperationalReadinessRecord]:
        self.get_readiness(tenant_id, readiness_id)
        return self.repository.get_operational_readiness_history(readiness_id, tenant_id)


_readiness_service = GovernanceResilienceOperationalReadinessService()


def get_governance_resilience_operational_readiness_service() -> GovernanceResilienceOperationalReadinessService:
    return _readiness_service

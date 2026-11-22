"""Phase 84: Delegated-Authority Readiness Service.

Assesses capability and scenario readiness of emergency delegates without
modifying legal delegations, creating new authority, or granting clinical practice.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_delegated_authority_readiness import (
    AssessDelegatedAuthorityReadinessRequest,
    DelegatedAuthorityReadinessRecord,
    DelegatedAuthorityStatus,
)


class GovernanceResilienceDelegatedAuthorityReadinessService:
    """Service assessing delegated governance authority operational readiness."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def assess_delegated_readiness(
        self,
        tenant_id: str,
        assessor_id: str,
        request: AssessDelegatedAuthorityReadinessRequest,
    ) -> DelegatedAuthorityReadinessRecord:
        # Delegate cannot assess their own readiness
        if assessor_id == request.delegate_user_id:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Delegate cannot assess their own delegated-authority readiness.",
                status_code=400,
            )

        now = datetime.utcnow()
        if request.delegation_valid_until and request.delegation_valid_until < now:
            status = DelegatedAuthorityStatus.EXPIRED_DELEGATION_EVIDENCE
        elif not request.practical_scenario_demonstrated:
            status = DelegatedAuthorityStatus.DEMONSTRATION_REQUIRED
        elif not (request.awareness_demonstrated and request.documentation_capability_verified and request.escalation_pathway_verified):
            status = DelegatedAuthorityStatus.AWARENESS_DEMONSTRATED_UNVERIFIED_AUTHORITY
        else:
            status = DelegatedAuthorityStatus.VERIFIED_READY

        readiness_id = f"dar-{uuid.uuid4().hex[:10]}"
        record = DelegatedAuthorityReadinessRecord(
            delegation_readiness_id=readiness_id,
            tenant_id=tenant_id,
            delegated_authority_reference=request.delegated_authority_reference,
            delegate_user_id=request.delegate_user_id,
            delegator_role=request.delegator_role,
            authorized_scope=request.authorized_scope,
            delegation_valid_until=request.delegation_valid_until,
            awareness_demonstrated=request.awareness_demonstrated,
            documentation_capability_verified=request.documentation_capability_verified,
            escalation_pathway_verified=request.escalation_pathway_verified,
            practical_scenario_demonstrated=request.practical_scenario_demonstrated,
            status=status,
            limitations=request.limitations,
            assessed_by=assessor_id,
        )
        return self.repository.save_delegated_readiness(record)

    def get_delegated_readiness(
        self, tenant_id: str, delegation_readiness_id: str
    ) -> DelegatedAuthorityReadinessRecord:
        record = self.repository.get_delegated_readiness(delegation_readiness_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.DELEGATED_AUTHORITY_READINESS_NOT_FOUND,
                message=f"Delegated authority readiness record '{delegation_readiness_id}' not found.",
                status_code=404,
            )
        return record

    def list_delegated_readiness(
        self,
        tenant_id: str,
        delegate_user_id: Optional[str] = None,
        status: Optional[DelegatedAuthorityStatus] = None,
    ) -> List[DelegatedAuthorityReadinessRecord]:
        return self.repository.list_delegated_readiness(
            tenant_id=tenant_id,
            delegate_user_id=delegate_user_id,
            status=status,
        )


_delegated_readiness_service = GovernanceResilienceDelegatedAuthorityReadinessService()


def get_governance_resilience_delegated_authority_readiness_service() -> GovernanceResilienceDelegatedAuthorityReadinessService:
    return _delegated_readiness_service

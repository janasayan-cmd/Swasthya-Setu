"""Phase 76: Governance Benefit Register Service.

Coordinates:
- Registration of expected benefits associated with approved governance changes
- Validation against Phase 72 decisions, Phase 73 implementations, Phase 74 adoptions, and Phase 75 portfolios
- Lineage reconstruction and benefit lifecycle management
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_benefit_assurance_repository import (
    GovernanceBenefitAssuranceRepository,
    get_governance_benefit_assurance_repository,
)
from app.repositories.governance_decision_implementation_repository import (
    get_governance_decision_implementation_repository,
)
from app.repositories.governance_change_adoption_repository import (
    get_governance_change_adoption_repository,
)
from app.repositories.governance_change_portfolio_repository import (
    get_governance_change_portfolio_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_benefit_register import (
    BenefitLineageResponse,
    BenefitStatus,
    GovernanceBenefitRecord,
    RegisterBenefitRequest,
)


class GovernanceBenefitRegisterService:
    """Service governing benefit registration, source validation, and lineage."""

    def __init__(
        self,
        repository: Optional[GovernanceBenefitAssuranceRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_benefit_assurance_repository()
        self.phase73_repo = get_governance_decision_implementation_repository()
        self.phase74_repo = get_governance_change_adoption_repository()
        self.phase75_repo = get_governance_change_portfolio_repository()

    def register_benefit(
        self,
        request: RegisterBenefitRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceBenefitRecord:
        """Registers an expected operational benefit linked to an approved governance change."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        # Validate Phase 73 implementation record if present in repo
        phase73_rec = self.phase73_repo.get_implementation(request.implementation_id)
        if phase73_rec is not None:
            rec_tenant = getattr(phase73_rec, "organization_id", None) or getattr(phase73_rec, "tenant_id", None)
            if rec_tenant != user_tenant:
                raise AppException(
                    code=ErrorCode.BENEFIT_SOURCE_RECORD_INVALID,
                    message="Referenced Phase 73 implementation record belongs to a different tenant.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if phase73_rec.status.value in ["CANCELLED_WITH_AUTHORIZATION"]:
                raise AppException(
                    code=ErrorCode.BENEFIT_SOURCE_RECORD_INVALID,
                    message=f"Referenced Phase 73 implementation is cancelled ({phase73_rec.status.value}).",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if len(request.implementation_id.strip()) < 2:
                raise AppException(
                    code=ErrorCode.BENEFIT_SOURCE_RECORD_INVALID,
                    message="A valid Phase 73 implementation reference is required.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Validate Phase 74 adoption registration if provided
        if request.adoption_registration_id:
            phase74_rec = self.phase74_repo.get_registration(request.adoption_registration_id)
            if phase74_rec is not None and phase74_rec.tenant_id != user_tenant:
                raise AppException(
                    code=ErrorCode.BENEFIT_SOURCE_RECORD_INVALID,
                    message="Referenced Phase 74 adoption record belongs to a different tenant.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Validate Phase 75 portfolio if provided
        if request.portfolio_id:
            port = self.phase75_repo.get_portfolio(request.portfolio_id)
            if port is not None and port.tenant_id != user_tenant:
                raise AppException(
                    code=ErrorCode.BENEFIT_SOURCE_RECORD_INVALID,
                    message="Referenced Phase 75 portfolio belongs to a different tenant.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Check for duplicate benefit with identical title and implementation
        existing = self.repo.list_benefits(user_tenant, implementation_id=request.implementation_id)
        for b in existing:
            if b.title.strip().lower() == request.title.strip().lower() and b.status != BenefitStatus.RETIRED:
                raise AppException(
                    code=ErrorCode.INVALID_BENEFIT_STATE,
                    message=f"A benefit with title '{request.title}' is already registered for this implementation.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        now = datetime.now(timezone.utc).isoformat()
        benefit_id = f"ben_{uuid.uuid4().hex[:12]}"

        record = GovernanceBenefitRecord(
            benefit_id=benefit_id,
            tenant_id=user_tenant,
            title=request.title,
            description=request.description,
            category=request.category,
            expected_outcome=request.expected_outcome,
            decision_id=request.decision_id,
            implementation_id=request.implementation_id,
            portfolio_id=request.portfolio_id,
            adoption_registration_id=request.adoption_registration_id,
            responsible_benefit_owner_id=request.responsible_benefit_owner_id,
            organizational_scope=request.organizational_scope,
            expected_realization_date=request.expected_realization_date,
            measurement_period=request.measurement_period,
            active_baseline_id=None,
            active_target_id=None,
            measurement_methodology=request.measurement_methodology,
            evidence_requirements=request.evidence_requirements,
            verification_requirements=request.verification_requirements,
            status=BenefitStatus.REGISTERED,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
            version=1,
        )
        return self.repo.save_benefit(record)

    def get_benefit(self, benefit_id: str, current_user: AuthenticatedUserContext) -> GovernanceBenefitRecord:
        """Retrieves single benefit record with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Governance benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return benefit

    def list_benefits(
        self,
        current_user: AuthenticatedUserContext,
        portfolio_id: Optional[str] = None,
        implementation_id: Optional[str] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceBenefitRecord]:
        """Lists benefits matching filters for the tenant."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        return self.repo.list_benefits(
            tenant_id=user_tenant,
            portfolio_id=portfolio_id,
            implementation_id=implementation_id,
            category=category,
            skip=skip,
            limit=limit,
        )

    def get_benefit_lineage(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> BenefitLineageResponse:
        """Reconstructs complete governance lineage from original decision to benefit."""
        benefit = self.get_benefit(benefit_id, current_user)

        nodes = [
            {"node_type": "GOVERNANCE_DECISION", "id": benefit.decision_id, "label": f"Phase 72 Decision ({benefit.decision_id})"},
            {"node_type": "IMPLEMENTATION", "id": benefit.implementation_id, "label": f"Phase 73 Implementation ({benefit.implementation_id})"},
        ]
        if benefit.adoption_registration_id:
            nodes.append({
                "node_type": "ADOPTION_MONITORING",
                "id": benefit.adoption_registration_id,
                "label": f"Phase 74 Adoption ({benefit.adoption_registration_id})",
            })
        if benefit.portfolio_id:
            nodes.append({
                "node_type": "PORTFOLIO",
                "id": benefit.portfolio_id,
                "label": f"Phase 75 Portfolio ({benefit.portfolio_id})",
            })
        nodes.append({
            "node_type": "BENEFIT_REALIZATION",
            "id": benefit.benefit_id,
            "label": f"Phase 76 Benefit ({benefit.title})",
            "status": benefit.status.value,
        })

        return BenefitLineageResponse(
            benefit_id=benefit.benefit_id,
            decision_id=benefit.decision_id,
            implementation_id=benefit.implementation_id,
            portfolio_id=benefit.portfolio_id,
            adoption_registration_id=benefit.adoption_registration_id,
            title=benefit.title,
            status=benefit.status,
            category=benefit.category,
            active_baseline_id=benefit.active_baseline_id,
            active_target_id=benefit.active_target_id,
            lineage_nodes=nodes,
        )

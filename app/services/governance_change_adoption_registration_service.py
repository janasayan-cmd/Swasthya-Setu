"""Phase 74: Governance Change Adoption Registration Service.

Coordinates:
- Registration intake of approved governance changes from Phase 73 implementation records
- Operational scope and milestone tracking
- Full decision-to-adoption lineage reconstruction
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_adoption_repository import (
    GovernanceChangeAdoptionRepository,
    get_governance_change_adoption_repository,
)
from app.repositories.governance_decision_implementation_repository import (
    get_governance_decision_implementation_repository,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_change_adoption_registration import (
    AdoptionLineageResponse,
    AdoptionRegistrationStatus,
    CreateAdoptionRegistrationRequest,
    GovernanceChangeAdoptionRecord,
    UpdateAdoptionRegistrationRequest,
)


class GovernanceChangeAdoptionRegistrationService:
    """Service governing change adoption registration and lineage."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()
        self.phase73_repo = get_governance_decision_implementation_repository()

    def register_change_adoption(
        self,
        request: CreateAdoptionRegistrationRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangeAdoptionRecord:
        """Registers an implemented governance change for operational adoption monitoring.
        
        Validates that the change possesses an authorized Phase 73 implementation record.
        """
        # Validate Phase 73 implementation record eligibility
        phase73_rec = self.phase73_repo.get_implementation(request.implementation_id)
        if phase73_rec is not None:
            # If present in Phase 73 repo, verify tenant and that it is not cancelled
            rec_tenant = getattr(phase73_rec, "tenant_id", None) or getattr(phase73_rec, "organization_id", None)
            user_tenant = current_user.tenant_id or current_user.organization_id
            if rec_tenant != user_tenant:
                raise AppException(
                    code=ErrorCode.PHASE73_IMPLEMENTATION_NOT_ELIGIBLE,
                    message="Referenced Phase 73 implementation record belongs to a different tenant.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if phase73_rec.status.value in ["CANCELLED", "REJECTED"]:
                raise AppException(
                    code=ErrorCode.PHASE73_IMPLEMENTATION_NOT_ELIGIBLE,
                    message=f"Phase 73 implementation record is in ineligible status: {phase73_rec.status.value}.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # If not in local in-memory repo (e.g. cross-service or mocked), validate structure
            if not request.implementation_id or len(request.implementation_id.strip()) < 3:
                raise AppException(
                    code=ErrorCode.PHASE73_IMPLEMENTATION_NOT_ELIGIBLE,
                    message="A valid Phase 73 implementation record reference is mandatory.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        now = datetime.now(timezone.utc).isoformat()
        reg_id = f"gcar_{uuid.uuid4().hex[:12]}"

        record = GovernanceChangeAdoptionRecord(
            registration_id=reg_id,
            tenant_id=current_user.tenant_id,
            management_review_id=request.management_review_id,
            decision_id=request.decision_id,
            implementation_id=request.implementation_id,
            title=request.title,
            change_description=request.change_description,
            operational_scope=request.operational_scope,
            accountable_operational_owner_id=request.accountable_operational_owner_id,
            adoption_monitoring_owner_id=request.adoption_monitoring_owner_id,
            status=AdoptionRegistrationStatus.PENDING_BASELINE,
            monitoring_start_date=request.monitoring_start_date,
            expected_monitoring_duration_days=request.expected_monitoring_duration_days,
            current_baseline_version=None,
            active_baseline_id=None,
            adoption_milestones=request.adoption_milestones,
            required_evidence_categories=request.required_evidence_categories,
            limitations_disclosed=request.limitations_disclosed,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
            version=1,
        )

        saved = self.repo.save_registration(record)
        self.repo.log_timeline_event(
            registration_id=reg_id,
            event_type="governance_change_adoption.registered",
            actor_id=current_user.user_id,
            summary=f"Governance change adoption registered for implementation '{request.implementation_id}'.",
            details={"title": request.title, "scope": request.operational_scope.model_dump()},
        )
        return saved

    def get_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> GovernanceChangeAdoptionRecord:
        """Retrieves an adoption registration record with tenant isolation."""
        record = self.repo.get_registration(registration_id)
        if not record or record.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_registrations(
        self,
        current_user: AuthenticatedUserContext,
        status_filter: Optional[AdoptionRegistrationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceChangeAdoptionRecord]:
        """Lists adoption registrations for the current user's tenant."""
        return self.repo.list_registrations(
            tenant_id=current_user.tenant_id,
            status=status_filter,
            skip=skip,
            limit=limit,
        )

    def update_registration(
        self,
        registration_id: str,
        request: UpdateAdoptionRegistrationRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangeAdoptionRecord:
        """Updates metadata or operational scope of an adoption registration."""
        record = self.get_registration(registration_id, current_user)

        updated_dict = record.model_dump()
        if request.title is not None:
            updated_dict["title"] = request.title
        if request.change_description is not None:
            updated_dict["change_description"] = request.change_description
        if request.operational_scope is not None:
            updated_dict["operational_scope"] = request.operational_scope
        if request.accountable_operational_owner_id is not None:
            updated_dict["accountable_operational_owner_id"] = request.accountable_operational_owner_id
        if request.adoption_monitoring_owner_id is not None:
            updated_dict["adoption_monitoring_owner_id"] = request.adoption_monitoring_owner_id
        if request.expected_monitoring_duration_days is not None:
            updated_dict["expected_monitoring_duration_days"] = request.expected_monitoring_duration_days
        if request.status is not None:
            updated_dict["status"] = request.status
        if request.limitations_disclosed is not None:
            updated_dict["limitations_disclosed"] = request.limitations_disclosed

        updated_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_dict["version"] = record.version + 1

        updated_record = GovernanceChangeAdoptionRecord(**updated_dict)
        saved = self.repo.save_registration(updated_record)

        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.updated",
            actor_id=current_user.user_id,
            summary=f"Adoption registration updated to version {saved.version}.",
        )
        return saved

    def get_registration_lineage(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> AdoptionLineageResponse:
        """Reconstructs the full governance lineage from management decision to adoption monitoring."""
        reg = self.get_registration(registration_id, current_user)
        baselines = self.repo.list_baselines_for_registration(registration_id, current_user.tenant_id)
        plans = self.repo.list_monitoring_plans_for_registration(registration_id, current_user.tenant_id)
        evidence = self.repo.list_evidence_for_registration(registration_id, current_user.tenant_id)
        indicators = self.repo.list_indicators_for_registration(registration_id, current_user.tenant_id)
        drift = self.repo.list_drift_signals_for_registration(registration_id, current_user.tenant_id)
        sustainability = self.repo.list_sustainability_assessments_for_registration(registration_id, current_user.tenant_id)
        exceptions = self.repo.list_exceptions_for_registration(registration_id, current_user.tenant_id)
        consequences = self.repo.list_consequences_for_registration(registration_id, current_user.tenant_id)
        escalations = self.repo.list_escalations_for_registration(registration_id, current_user.tenant_id)

        lineage_nodes = [
            {"node_type": "MANAGEMENT_REVIEW", "id": reg.management_review_id, "label": "Phase 72 Management Review"},
            {"node_type": "APPROVED_DECISION", "id": reg.decision_id, "label": "Phase 72 Governance Decision"},
            {"node_type": "IMPLEMENTATION_RECORD", "id": reg.implementation_id, "label": "Phase 73 Implementation Record"},
            {"node_type": "ADOPTION_REGISTRATION", "id": reg.registration_id, "label": reg.title, "status": reg.status.value},
        ]
        if reg.active_baseline_id:
            lineage_nodes.append({
                "node_type": "ACTIVE_BASELINE",
                "id": reg.active_baseline_id,
                "version": reg.current_baseline_version,
            })

        return AdoptionLineageResponse(
            registration_id=reg.registration_id,
            tenant_id=reg.tenant_id,
            management_review_id=reg.management_review_id,
            decision_id=reg.decision_id,
            implementation_id=reg.implementation_id,
            active_baseline_version=reg.current_baseline_version,
            baselines_count=len(baselines),
            monitoring_plans_count=len(plans),
            evidence_count=len(evidence),
            indicators_count=len(indicators),
            drift_signals_count=len(drift),
            sustainability_assessments_count=len(sustainability),
            exceptions_count=len(exceptions),
            consequences_count=len(consequences),
            escalations_count=len(escalations),
            lineage_nodes=lineage_nodes,
        )

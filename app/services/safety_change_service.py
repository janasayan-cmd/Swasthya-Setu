"""Phase 51: Controlled Safety Change Request & Lifecycle Service.

Manages initiation of governed safety changes, multi-dimensional impact assessments,
emergency change pathways, version preservation, and lifecycle state management.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import (
    RiskAlreadyClosedException,
    RiskNotFoundException,
    RiskVersionConflictException,
    SafetyChangeAccessDeniedException,
    SafetyChangeInvalidStateException,
    SafetyChangeNotFoundException,
    SafetyChangeVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.risk import RiskHistoryEntry
from app.schemas.safety_change import (
    ImpactAssessment,
    SafetyChangeCreateRequest,
    SafetyChangeRecord,
)
from app.schemas.safety_governance import (
    AIGovernanceStatus,
    ChangeRequestState,
    RolloutScopeType,
    SafetyChangeTargetType,
)
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.safety_change_service")


class SafetyChangeService:
    """Service governing controlled safety change requests and impact evaluations."""

    def __init__(
        self,
        repository: Optional[SafetyGovernanceRepository] = None,
        policy_service: Optional[SafetyGovernancePolicyService] = None,
        audit_svc: Optional[AuditService] = None,
        metrics_svc: Optional[SafetyGovernanceMetricsService] = None,
    ) -> None:
        self.repository = repository or safety_governance_repository
        self.policy_service = policy_service or safety_governance_policy_service
        self.audit_service = audit_svc or audit_service
        self.metrics_service = metrics_svc or safety_governance_metrics_service

    async def create_change_request(
        self,
        request: SafetyChangeCreateRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SafetyChangeRecord:
        """Create a controlled safety change request bound to an identified risk."""
        # 1. Authority validation (AI cannot initiate authorized changes directly)
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "create_change_request")

        # 2. Retrieve risk & validate
        risk = self.repository.get_risk(request.risk_id)
        if not risk:
            raise RiskNotFoundException(f"Parent clinical safety risk '{request.risk_id}' not found.")
        self.policy_service.validate_org_boundary(risk.organization_id, organization_id, "risk")

        if risk.is_closed:
            raise RiskAlreadyClosedException(
                f"Cannot create change request against closed risk '{risk.id}'. Reopening required."
            )

        if request.expected_risk_version is not None and risk.version != request.expected_risk_version:
            raise RiskVersionConflictException(
                f"Risk version mismatch: expected {request.expected_risk_version}, current {risk.version}."
            )

        # 3. Idempotency check
        if request.idempotency_key:
            existing_id = self.repository.get_idempotent_result(request.idempotency_key)
            if existing_id:
                existing_change = self.repository.get_change(existing_id)
                if existing_change:
                    return existing_change

        # 4. Construct record
        now = datetime.now(timezone.utc)
        initial_state = ChangeRequestState.REVIEW_REQUIRED if request.impact_assessment else ChangeRequestState.DRAFT
        change = SafetyChangeRecord(
            risk_id=risk.id,
            risk_version_at_creation=risk.version,
            version=1,
            title=request.title,
            description=request.description,
            target_type=request.target_type,
            affected_subsystem=request.affected_subsystem,
            state=initial_state,
            current_version=request.current_version,
            proposed_version=request.proposed_version,
            proposed_change_details=request.proposed_change_details,
            reason=request.reason,
            expected_benefit=request.expected_benefit,
            possible_adverse_effects=request.possible_adverse_effects,
            dependencies=request.dependencies,
            implementation_scope=request.implementation_scope,
            scope_details=request.scope_details,
            rollback_plan=request.rollback_plan,
            validation_plan=request.validation_plan,
            monitoring_plan=request.monitoring_plan,
            impact_assessment=request.impact_assessment,
            created_by_id=actor_id,
            created_by_role=actor_role,
            organization_id=organization_id or risk.organization_id,
            facility_id=facility_id or risk.facility_id,
            is_emergency=request.is_emergency,
            emergency_justification=request.emergency_justification,
            created_at=now,
            updated_at=now,
            ai_metadata=request.ai_metadata,
        )

        persisted = self.repository.save_change(change)
        if request.idempotency_key:
            self.repository.save_idempotent_result(request.idempotency_key, persisted.id)

        # Link to risk
        if persisted.id not in risk.linked_change_request_ids:
            risk.linked_change_request_ids.append(persisted.id)
            risk.version += 1
            risk.updated_at = now
            self.repository.save_risk(risk)

            self.repository.add_risk_history(
                RiskHistoryEntry(
                    risk_id=risk.id,
                    version=risk.version,
                    previous_state=risk.state,
                    new_state=risk.state,
                    action="CHANGE_REQUEST_LINKED",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    reason=f"Safety change request '{persisted.id}' created",
                    details={"change_id": persisted.id, "target_type": persisted.target_type.value},
                )
            )

        self.metrics_service.increment("change_requested_count")
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.SAFETY_CHANGE_REQUESTED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:change:request",
                    resource_type="safety_change",
                    resource_id=persisted.id,
                    metadata={"risk_id": risk.id, "target_type": persisted.target_type.value},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for change request: %s", ex)

        return persisted

    def get_change(self, change_id: str, actor_org_id: Optional[str] = None) -> SafetyChangeRecord:
        """Retrieve safety change request by ID."""
        change = self.repository.get_change(change_id)
        if not change:
            raise SafetyChangeNotFoundException(f"Safety change request '{change_id}' not found.")
        self.policy_service.validate_org_boundary(change.organization_id, actor_org_id, "safety_change")
        return change

    def list_changes(
        self,
        risk_id: Optional[str] = None,
        state: Optional[ChangeRequestState] = None,
        organization_id: Optional[str] = None,
    ) -> List[SafetyChangeRecord]:
        """List and filter safety change requests."""
        return self.repository.list_changes(
            risk_id=risk_id,
            state=state,
            organization_id=organization_id,
        )

    async def record_impact_assessment(
        self,
        change_id: str,
        assessment: ImpactAssessment,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
    ) -> SafetyChangeRecord:
        """Record multi-dimensional impact assessment and advance change to REVIEW_REQUIRED."""
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "record_impact_assessment")

        change = self.get_change(change_id, organization_id)
        if change.state not in (ChangeRequestState.DRAFT, ChangeRequestState.REVIEW_REQUIRED):
            raise SafetyChangeInvalidStateException(
                f"Cannot update impact assessment when change is in state '{change.state.value}'."
            )

        change.impact_assessment = assessment
        change.state = ChangeRequestState.REVIEW_REQUIRED
        change.version += 1
        change.updated_at = datetime.now(timezone.utc)
        return self.repository.save_change(change)

    async def close_change(
        self,
        change_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
    ) -> SafetyChangeRecord:
        """Formally complete and close a validated safety change request."""
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "close_change")

        change = self.get_change(change_id, organization_id)
        # Must be in VALIDATED or MONITORING state to close
        if change.state not in (ChangeRequestState.VALIDATED, ChangeRequestState.MONITORING):
            raise SafetyChangeInvalidStateException(
                f"Cannot complete safety change '{change_id}' from state '{change.state.value}'. "
                "Must be VALIDATED or MONITORING."
            )

        change.state = ChangeRequestState.COMPLETED
        change.version += 1
        change.updated_at = datetime.now(timezone.utc)
        self.repository.save_change(change)
        return change


# Global singleton safety change service
safety_change_service = SafetyChangeService()

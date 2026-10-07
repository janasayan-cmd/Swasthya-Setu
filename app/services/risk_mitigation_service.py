"""Phase 51: Risk Mitigation Planning & Tracking Service.

Manages mitigation creation, status progression, linkage to risks,
and enforces the distinction between MITIGATION and CONTROL.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    RiskAlreadyClosedException,
    RiskNotFoundException,
    RiskVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.risk import RiskHistoryEntry
from app.schemas.risk_mitigation import (
    MitigationCreateRequest,
    MitigationRecord,
    MitigationStatus,
)
from app.schemas.safety_governance import RiskState
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.risk_mitigation_service")


class RiskMitigationService:
    """Service governing risk mitigation planning, owners, and validation criteria."""

    def __init__(
        self,
        repository: Optional[SafetyGovernanceRepository] = None,
        policy_service: Optional[SafetyGovernancePolicyService] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_governance_repository
        self.policy_service = policy_service or safety_governance_policy_service
        self.audit_service = audit_svc or audit_service

    async def create_mitigation(
        self,
        risk_id: str,
        request: MitigationCreateRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> MitigationRecord:
        """Create a planned mitigation for an identified or assessed clinical risk."""
        # 1. Authority validation
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "create_mitigation")

        # 2. Retrieve risk & validate
        risk = self.repository.get_risk(risk_id)
        if not risk:
            raise RiskNotFoundException(f"Clinical safety risk '{risk_id}' not found.")
        self.policy_service.validate_org_boundary(risk.organization_id, organization_id, "risk")

        if risk.is_closed:
            raise RiskAlreadyClosedException(f"Cannot create mitigation for closed risk '{risk_id}'.")

        if request.expected_version is not None and risk.version != request.expected_version:
            raise RiskVersionConflictException(
                f"Version conflict on risk: expected {request.expected_version}, current {risk.version}."
            )

        now = datetime.now(timezone.utc)
        mitigation = MitigationRecord(
            risk_id=risk_id,
            title=request.title,
            description=request.description,
            mitigation_type=request.mitigation_type,
            owner_id=request.owner_id,
            expected_outcome=request.expected_outcome,
            dependencies=request.dependencies,
            evidence=request.evidence,
            validation_criteria=request.validation_criteria,
            status=MitigationStatus.PLANNED,
            created_at=now,
            updated_at=now,
        )

        persisted = self.repository.save_mitigation(mitigation)

        # Link to risk & update state if applicable
        previous_state = risk.state
        if mitigation.id not in risk.linked_mitigation_ids:
            risk.linked_mitigation_ids.append(mitigation.id)

        if risk.state in (RiskState.IDENTIFIED, RiskState.MITIGATION_REQUIRED):
            risk.state = RiskState.MITIGATION_PLANNED

        risk.version += 1
        risk.updated_at = now
        self.repository.save_risk(risk)

        # Append history entry
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=risk.state,
                action="MITIGATION_CREATED",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Mitigation plan '{persisted.title}' created",
                details={"mitigation_id": persisted.id, "owner_id": persisted.owner_id},
            )
        )

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.RISK_MITIGATION_CREATED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:mitigation:create",
                    resource_type="risk_mitigation",
                    resource_id=persisted.id,
                    metadata={"risk_id": risk.id, "mitigation_type": persisted.mitigation_type},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for mitigation creation: %s", ex)

        return persisted

    def update_mitigation_status(
        self,
        mitigation_id: str,
        new_status: MitigationStatus,
        actor_id: str,
        actor_role: str,
        notes: Optional[str] = None,
    ) -> MitigationRecord:
        """Update mitigation execution status."""
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "update_mitigation")

        mitigation = self.repository.get_mitigation(mitigation_id)
        if not mitigation:
            raise RiskNotFoundException(f"Mitigation '{mitigation_id}' not found.")

        mitigation.status = new_status
        mitigation.updated_at = datetime.now(timezone.utc)
        self.repository.save_mitigation(mitigation)

        # If mitigation is now IN_PROGRESS, update parent risk if applicable
        risk = self.repository.get_risk(mitigation.risk_id)
        if risk and risk.state == RiskState.MITIGATION_PLANNED and new_status == MitigationStatus.IN_PROGRESS:
            risk.state = RiskState.MITIGATION_IN_PROGRESS
            risk.version += 1
            risk.updated_at = datetime.now(timezone.utc)
            self.repository.save_risk(risk)

        return mitigation

    def get_mitigation(self, mitigation_id: str) -> Optional[MitigationRecord]:
        """Retrieve mitigation by ID."""
        return self.repository.get_mitigation(mitigation_id)

    def list_mitigations(self, risk_id: str) -> List[MitigationRecord]:
        """List all mitigations linked to a risk."""
        return self.repository.list_mitigations(risk_id)


# Global singleton risk mitigation service
risk_mitigation_service = RiskMitigationService()

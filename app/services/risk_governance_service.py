"""Phase 51: Clinical Safety Risk Governance Service.

Manages risk registration from safety sources (incidents, near misses, learning recommendations),
lifecycle state progression, evidence linkage, audit history preservation,
prerequisite-verified closure, and historical-preserving reopening.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import settings
from app.core.exceptions import (
    RiskAlreadyClosedException,
    RiskAssessmentRequiredException,
    RiskInvalidStateException,
    RiskInvalidTransitionException,
    RiskNotFoundException,
    RiskVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.risk import (
    RiskCloseRequest,
    RiskCreateRequest,
    RiskHistoryEntry,
    RiskRecord,
    RiskReopenRequest,
)
from app.schemas.safety_governance import (
    AIGovernanceStatus,
    ChangeRequestState,
    RiskCategory,
    RiskState,
)
from app.schemas.risk_mitigation import MitigationStatus
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.risk_governance_service")


class RiskGovernanceService:
    """Master service governing clinical safety risks and lifecycle integrity."""

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

    async def create_risk(
        self,
        request: RiskCreateRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RiskRecord:
        """Register a potential clinical safety risk with full source provenance."""
        # 1. Authority / AI Check: AI can only suggest drafts, human authority required for registration
        if request.ai_metadata and request.ai_metadata.ai_status == AIGovernanceStatus.AI_SUGGESTED:
            request.ai_metadata.ai_status = AIGovernanceStatus.HUMAN_REVIEW_REQUIRED

        # 2. Idempotency Check
        if request.idempotency_key:
            existing_id = self.repository.get_idempotent_result(request.idempotency_key)
            if existing_id:
                existing_risk = self.repository.get_risk(existing_id)
                if existing_risk:
                    logger.info("Returning existing risk %s for idempotency key %s", existing_id, request.idempotency_key)
                    return existing_risk

        # 3. Instantiate Risk Record
        now = datetime.now(timezone.utc)
        risk = RiskRecord(
            title=request.title,
            description=request.description,
            category=request.category,
            state=RiskState.IDENTIFIED,
            initial_severity=request.initial_severity,
            initial_likelihood=request.initial_likelihood,
            initial_impact=request.initial_impact,
            sources=request.sources,
            affected_subsystem=request.affected_subsystem,
            affected_workflow=request.affected_workflow,
            affected_provider=request.affected_provider,
            organization_id=organization_id or request.organization_id,
            facility_id=facility_id or request.facility_id,
            created_by_id=actor_id,
            created_by_role=actor_role,
            created_at=now,
            updated_at=now,
            ai_metadata=request.ai_metadata,
        )

        persisted = self.repository.save_risk(risk)
        if request.idempotency_key:
            self.repository.save_idempotent_result(request.idempotency_key, persisted.id)

        # 4. Record Initial History Entry
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=persisted.id,
                version=persisted.version,
                previous_state=None,
                new_state=RiskState.IDENTIFIED,
                action="RISK_CREATED",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Initial registration from safety finding source",
                details={"category": persisted.category.value, "initial_severity": persisted.initial_severity.value},
            )
        )

        # 5. Audit & Telemetry
        self.metrics_service.increment("risk_created_count")
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.RISK_CREATED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:risk:create",
                    resource_type="clinical_risk",
                    resource_id=persisted.id,
                    metadata={"category": persisted.category.value, "sources_count": len(persisted.sources)},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for risk creation: %s", ex)

        return persisted

    def get_risk(self, risk_id: str, actor_org_id: Optional[str] = None) -> RiskRecord:
        """Retrieve a clinical safety risk, validating multi-tenancy boundaries."""
        risk = self.repository.get_risk(risk_id)
        if not risk:
            raise RiskNotFoundException(f"Clinical safety risk '{risk_id}' not found.")
        self.policy_service.validate_org_boundary(risk.organization_id, actor_org_id, "risk")
        return risk

    def list_risks(
        self,
        actor_org_id: Optional[str] = None,
        category: Optional[RiskCategory] = None,
        state: Optional[RiskState] = None,
    ) -> List[RiskRecord]:
        """List and filter clinical safety risks."""
        return self.repository.list_risks(
            organization_id=actor_org_id,
            category=category,
            state=state,
        )

    def get_risk_history(self, risk_id: str, actor_org_id: Optional[str] = None) -> List[RiskHistoryEntry]:
        """Retrieve full chronological history entries for a risk."""
        self.get_risk(risk_id, actor_org_id)
        return self.repository.list_risk_history(risk_id)

    async def attach_evidence(
        self,
        risk_id: str,
        evidence: Dict[str, Any],
        actor_id: str,
        actor_role: str,
        actor_org_id: Optional[str] = None,
    ) -> RiskRecord:
        """Attach supporting evidence pointer to an existing risk."""
        risk = self.get_risk(risk_id, actor_org_id)
        now = datetime.now(timezone.utc)
        evidence_with_ts = {**evidence, "attached_by": actor_id, "attached_at": now.isoformat()}
        risk.evidence_references.append(evidence_with_ts)
        risk.updated_at = now
        self.repository.save_risk(risk)
        return risk

    def transition_state(
        self,
        risk_id: str,
        new_state: RiskState,
        actor_id: str,
        actor_role: str,
        reason: str,
        expected_version: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> RiskRecord:
        """Safely transition risk lifecycle state with version concurrency protection."""
        risk = self.get_risk(risk_id)

        if expected_version is not None and risk.version != expected_version:
            raise RiskVersionConflictException(
                f"Risk version conflict: expected version {expected_version}, but current version is {risk.version}."
            )

        if risk.is_closed and new_state != RiskState.REOPENED:
            raise RiskAlreadyClosedException(
                f"Risk '{risk_id}' is CLOSED. Cannot transition to '{new_state.value}' without formal reopening."
            )

        previous_state = risk.state
        risk.state = new_state
        risk.version += 1
        risk.updated_at = datetime.now(timezone.utc)
        self.repository.save_risk(risk)

        # Record history
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=new_state,
                action="STATE_TRANSITION",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                details=details or {},
            )
        )

        return risk

    async def close_risk(
        self,
        risk_id: str,
        request: RiskCloseRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RiskRecord:
        """Formal risk closure following rigorous governance prerequisite validation.

        Closed does NOT mean risk is permanently eliminated or patient harm is impossible.
        """
        # 1. Authority validation (AI cannot close risks)
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "close_risk")

        risk = self.get_risk(risk_id, organization_id)
        if risk.is_closed:
            raise RiskAlreadyClosedException(f"Risk '{risk_id}' is already CLOSED.")

        if request.expected_version is not None and risk.version != request.expected_version:
            raise RiskVersionConflictException(
                f"Version conflict on risk closure: expected {request.expected_version}, current {risk.version}."
            )

        # 2. Validate prerequisites for closure (Section 40)
        # Must have completed a structured assessment
        if not risk.latest_assessment_id:
            raise RiskAssessmentRequiredException(
                f"Risk '{risk_id}' cannot be closed without a completed, authorized risk assessment."
            )

        # Linked mitigations cannot be failed or unaddressed
        mitigations = self.repository.list_mitigations(risk_id)
        for m in mitigations:
            if m.status in (MitigationStatus.FAILED, MitigationStatus.IN_PROGRESS):
                raise RiskInvalidStateException(
                    f"Risk cannot be closed while linked mitigation '{m.id}' is in status '{m.status.value}'."
                )

        # Linked change requests must be resolved (not currently implementing or validation pending or failed)
        changes = self.repository.list_changes(risk_id=risk_id)
        for c in changes:
            if c.state in (
                ChangeRequestState.IMPLEMENTING,
                ChangeRequestState.VALIDATION_REQUIRED,
                ChangeRequestState.FAILED,
            ):
                raise RiskInvalidStateException(
                    f"Risk cannot be closed while linked safety change '{c.id}' is in status '{c.state.value}'."
                )

        now = datetime.now(timezone.utc)
        previous_state = risk.state
        risk.state = RiskState.CLOSED
        risk.is_closed = True
        risk.closed_at = now
        risk.closed_by_id = actor_id
        risk.closed_reason = request.reason
        risk.version += 1
        risk.updated_at = now

        self.repository.save_risk(risk)

        # Record history
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=RiskState.CLOSED,
                action="RISK_CLOSED",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                details={"verification_notes": request.verification_notes},
            )
        )

        self.metrics_service.increment("risk_closed_count")
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.RISK_CLOSED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:risk:close",
                    resource_type="clinical_risk",
                    resource_id=risk.id,
                    metadata={"closed_reason": request.reason},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for risk closure: %s", ex)

        return risk

    async def reopen_risk(
        self,
        risk_id: str,
        request: RiskReopenRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RiskRecord:
        """Reopen a previously closed risk upon recurrence or new findings while preserving history."""
        # 1. Authority validation
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "reopen_risk")

        risk = self.get_risk(risk_id, organization_id)
        if not risk.is_closed:
            raise RiskInvalidStateException(
                f"Risk '{risk_id}' is not closed (current state: {risk.state.value}) and cannot be reopened."
            )

        if request.expected_version is not None and risk.version != request.expected_version:
            raise RiskVersionConflictException(
                f"Version conflict on risk reopening: expected {request.expected_version}, current {risk.version}."
            )

        now = datetime.now(timezone.utc)
        previous_state = risk.state
        risk.state = RiskState.REOPENED
        risk.is_closed = False
        risk.reopened_at = now
        risk.reopened_by_id = actor_id
        risk.reopened_reason = request.reason
        if request.new_evidence:
            for ev in request.new_evidence:
                risk.evidence_references.append({**ev, "attached_during": "reopen", "attached_at": now.isoformat()})
        risk.version += 1
        risk.updated_at = now

        self.repository.save_risk(risk)

        # Record history entry (history is preserved, never overwritten)
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=RiskState.REOPENED,
                action="RISK_REOPENED",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                details={"new_evidence_count": len(request.new_evidence)},
            )
        )

        self.metrics_service.increment("risk_reopened_count")
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.RISK_REOPENED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:risk:reopen",
                    resource_type="clinical_risk",
                    resource_id=risk.id,
                    metadata={"reopen_reason": request.reason},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for risk reopening: %s", ex)

        return risk


# Global singleton risk governance service
risk_governance_service = RiskGovernanceService()

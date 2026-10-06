"""Phase 49: Incident Investigation & Root-Cause Hypotheses Service.

Manages safety investigator assignments, hypothesis tracking, and findings documentation.
Guards against AI autonomously confirming root causes or declaring clinical conclusions.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    AIIncidentAuthorityProhibitedException,
    IncidentInvalidStateException,
    IncidentNotFoundException,
    IncidentRootCauseUnconfirmedException,
    IncidentUnauthorizedAssignmentException,
)
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.incident_investigation import (
    HypothesisCreateRequest,
    HypothesisStatus,
    HypothesisStatusUpdateRequest,
    InvestigationRecord,
    RootCauseCategory,
    RootCauseHypothesis,
)
from app.schemas.incidents import IncidentRecord, IncidentStatus
from app.services.audit_service import AuditService, audit_service

logger = logging.getLogger("app.incident_investigation_service")


class IncidentInvestigationService:
    """Service governing incident investigations, root-cause hypotheses, and findings."""

    def __init__(
        self,
        repository: Optional[SafetyIncidentRepository] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_incident_repository
        self.audit_service = audit_svc or audit_service

    async def assign_investigator(
        self,
        incident_id: str,
        investigator_id: str,
        investigator_role: str,
        assigned_by_id: str,
        notes: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Assign an authorized investigator to the incident."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")

        # Prohibit AI from becoming authoritative lead investigator
        if "AI" in investigator_role.upper() or "BOT" in investigator_role.upper() or "MODEL" in investigator_role.upper():
            raise AIIncidentAuthorityProhibitedException("AI agents cannot serve as authoritative lead safety investigators.")

        incident.assigned_investigator_id = investigator_id
        incident.assigned_investigator_role = investigator_role
        if incident.status in [IncidentStatus.DETECTED, IncidentStatus.TRIAGED, IncidentStatus.OPEN, IncidentStatus.CONTAINMENT_REQUIRED, IncidentStatus.CONTAINED]:
            incident.status = IncidentStatus.INVESTIGATING
        incident.updated_at = datetime.now(timezone.utc)

        self.repository.save_incident(incident)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_INVESTIGATED,
                    outcome="ALLOW",
                    actor_id=assigned_by_id,
                    action="incident:assign_investigator",
                    resource_type="safety_incident",
                    resource_id=incident.id,
                    metadata={
                        "investigator_id": investigator_id,
                        "investigator_role": investigator_role,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for assignment on %s: %s", incident.id, ex)

        return incident

    async def propose_hypothesis(
        self,
        incident_id: str,
        request: HypothesisCreateRequest,
        proposer_id: str,
        proposer_role: str,
        request_id: Optional[str] = None,
    ) -> RootCauseHypothesis:
        """Propose a candidate root-cause hypothesis (initially in PROPOSED status)."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")

        hypothesis = RootCauseHypothesis(
            incident_id=incident_id,
            category=request.category,
            title=request.title,
            statement=request.statement,
            status=HypothesisStatus.PROPOSED,
            proposed_by_id=proposer_id,
            proposed_by_role=proposer_role,
            supporting_evidence_ids=request.supporting_evidence_ids,
        )
        self.repository.save_hypothesis(hypothesis)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_HYPOTHESIS_RECORDED,
                    outcome="ALLOW",
                    actor_id=proposer_id,
                    action="incident:propose_hypothesis",
                    resource_type="root_cause_hypothesis",
                    resource_id=hypothesis.id,
                    metadata={
                        "incident_id": incident_id,
                        "category": request.category.value,
                        "status": HypothesisStatus.PROPOSED.value,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for hypothesis %s: %s", hypothesis.id, ex)

        return hypothesis

    async def update_hypothesis_status(
        self,
        hypothesis_id: str,
        request: HypothesisStatusUpdateRequest,
        updater_id: str,
        updater_role: str,
        request_id: Optional[str] = None,
    ) -> RootCauseHypothesis:
        """Update status of a hypothesis (e.g. SUPPORTED, REJECTED, CONFIRMED)."""
        hypothesis = self.repository.get_hypothesis(hypothesis_id)
        if not hypothesis:
            raise IncidentNotFoundException(f"Hypothesis '{hypothesis_id}' not found.")

        # Guard: AI cannot confirm root causes autonomously
        if request.status == HypothesisStatus.CONFIRMED:
            if "AI" in updater_role.upper() or "BOT" in updater_role.upper() or "SYSTEM" in updater_role.upper():
                raise AIIncidentAuthorityProhibitedException(
                    "AI or automated systems cannot autonomously confirm root causes. Authorized human review required."
                )

        hypothesis.status = request.status
        if request.notes:
            hypothesis.investigator_notes = request.notes
        if request.evidence_id and request.evidence_id not in hypothesis.supporting_evidence_ids:
            hypothesis.supporting_evidence_ids.append(request.evidence_id)
        hypothesis.updated_at = datetime.now(timezone.utc)

        self.repository.save_hypothesis(hypothesis)

        # If hypothesis is confirmed, update parent incident
        if request.status == HypothesisStatus.CONFIRMED:
            incident = self.repository.get_incident(hypothesis.incident_id)
            if incident:
                incident.root_cause_category = hypothesis.category.value
                incident.root_cause_confirmed = True
                incident.updated_at = datetime.now(timezone.utc)
                self.repository.save_incident(incident)

        return hypothesis

    def get_investigation_record(self, incident_id: str) -> InvestigationRecord:
        """Compile consolidated investigation state for an incident."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")

        hypotheses = self.repository.list_hypotheses(incident_id)
        confirmed_rc = incident.root_cause_category if incident.root_cause_confirmed else None

        return InvestigationRecord(
            incident_id=incident_id,
            investigator_id=incident.assigned_investigator_id,
            investigator_role=incident.assigned_investigator_role,
            started_at=incident.detected_at,
            hypotheses=hypotheses,
            confirmed_root_cause=confirmed_rc,
            findings_summary=incident.resolution_summary,
            completed_at=incident.resolved_at,
        )


# Global singleton
incident_investigation_service = IncidentInvestigationService()

"""Phase 49: Clinical Safety Incident Management Service.

Governs clinical safety incident lifecycle transitions, triage, severity
and impact classification, status validations, and reopening workflows.
Distinct from Phase 27 operational incidents.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    IncidentAlreadyClosedException,
    IncidentAlreadyReopenedException,
    IncidentAlreadyResolvedException,
    IncidentInvalidStateException,
    IncidentInvalidTransitionException,
    IncidentNotFoundException,
)
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.incidents import (
    IncidentClosureRequest,
    IncidentCreateRequest,
    IncidentImpactStatus,
    IncidentRecord,
    IncidentReopenRequest,
    IncidentResolutionRequest,
    IncidentSeverity,
    IncidentStatus,
    IncidentTriageRequest,
    IncidentType,
)
from app.services.audit_service import AuditService, audit_service

logger = logging.getLogger("app.clinical_incident_service")


class ClinicalIncidentService:
    """Service governing clinical safety incident lifecycle, triage, status updates, and audit trails."""

    def __init__(
        self,
        repository: Optional[SafetyIncidentRepository] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_incident_repository
        self.audit_service = audit_svc or audit_service

    async def create_incident(
        self,
        request: IncidentCreateRequest,
        actor_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Create a new safety incident record."""
        now = datetime.now(timezone.utc)
        occurred = request.occurred_at or now

        incident = IncidentRecord(
            title=request.title,
            description=request.description,
            incident_type=request.incident_type,
            status=IncidentStatus.DETECTED,
            severity=request.severity,
            impact_status=request.impact_status,
            source=request.source,
            patient_id=request.patient_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            resource_version=request.resource_version,
            decision_id=request.decision_id,
            safety_check_id=request.safety_check_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            alert_id=request.alert_id,
            signal_ids=request.signal_ids,
            occurred_at=occurred,
            detected_at=now,
            recorded_at=now,
        )
        self.repository.save_incident(incident)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_CREATED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action=f"incident:create:{request.incident_type.value}",
                    resource_type="safety_incident",
                    resource_id=incident.id,
                    metadata={
                        "incident_id": incident.id,
                        "severity": incident.severity.value,
                        "incident_type": incident.incident_type.value,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for incident %s: %s", incident.id, ex)

        return incident

    def get_incident(self, incident_id: str) -> IncidentRecord:
        """Retrieve an incident record or raise IncidentNotFoundException."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Safety incident '{incident_id}' not found.")
        return incident

    def list_incidents(
        self,
        patient_id: Optional[str] = None,
        incident_type: Optional[IncidentType] = None,
        status: Optional[IncidentStatus] = None,
    ) -> List[IncidentRecord]:
        """List and filter incidents."""
        return self.repository.list_incidents(
            patient_id=patient_id,
            incident_type=incident_type,
            status=status,
        )

    async def triage_incident(
        self,
        incident_id: str,
        request: IncidentTriageRequest,
        triaged_by_id: str,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Triage an incident, updating assessed severity and containment requirements."""
        incident = self.get_incident(incident_id)
        if incident.status in [IncidentStatus.CLOSED, IncidentStatus.REJECTED]:
            raise IncidentInvalidStateException(
                f"Cannot triage incident '{incident_id}' in terminal state '{incident.status.value}'."
            )

        now = datetime.now(timezone.utc)
        incident.severity = request.severity
        incident.impact_status = request.impact_status
        incident.updated_at = now

        if request.requires_containment:
            incident.status = IncidentStatus.CONTAINMENT_REQUIRED
        else:
            incident.status = IncidentStatus.TRIAGED

        self.repository.save_incident(incident)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_TRIAGED,
                    outcome="ALLOW",
                    actor_id=triaged_by_id,
                    action="incident:triage",
                    resource_type="safety_incident",
                    resource_id=incident.id,
                    metadata={
                        "incident_id": incident.id,
                        "severity": request.severity.value,
                        "impact_status": request.impact_status.value,
                        "requires_containment": request.requires_containment,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for triage %s: %s", incident.id, ex)

        return incident

    async def resolve_incident(
        self,
        incident_id: str,
        request: IncidentResolutionRequest,
        resolved_by_id: str,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Mark incident resolved with documented findings."""
        incident = self.get_incident(incident_id)
        if incident.status == IncidentStatus.CLOSED:
            raise IncidentAlreadyClosedException(f"Incident '{incident_id}' is already closed.")
        if incident.status == IncidentStatus.RESOLVED:
            raise IncidentAlreadyResolvedException(f"Incident '{incident_id}' is already resolved.")

        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        incident.resolution_summary = request.resolution_summary
        if request.root_cause_category:
            incident.root_cause_category = request.root_cause_category
        incident.root_cause_confirmed = request.root_cause_confirmed
        incident.updated_at = now

        self.repository.save_incident(incident)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_RESOLVED,
                    outcome="ALLOW",
                    actor_id=resolved_by_id,
                    action="incident:resolve",
                    resource_type="safety_incident",
                    resource_id=incident.id,
                    metadata={
                        "incident_id": incident.id,
                        "root_cause_category": incident.root_cause_category,
                        "root_cause_confirmed": incident.root_cause_confirmed,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for resolution %s: %s", incident.id, ex)

        return incident

    async def reopen_incident(
        self,
        incident_id: str,
        request: IncidentReopenRequest,
        reopened_by_id: str,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Reopen a previously resolved or closed incident."""
        incident = self.get_incident(incident_id)
        if incident.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]:
            raise IncidentAlreadyReopenedException(
                f"Incident '{incident_id}' is currently '{incident.status.value}' and cannot be reopened."
            )

        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.REOPENED
        incident.reopened_at = now
        incident.closed_at = None
        incident.closure_reason = None
        incident.updated_at = now

        self.repository.save_incident(incident)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_REOPENED,
                    outcome="ALLOW",
                    actor_id=reopened_by_id,
                    action="incident:reopen",
                    resource_type="safety_incident",
                    resource_id=incident.id,
                    metadata={
                        "incident_id": incident.id,
                        "reopen_reason": request.reopen_reason,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for reopening %s: %s", incident.id, ex)

        return incident

    def mark_duplicate(self, incident_id: str, canonical_incident_id: str) -> IncidentRecord:
        """Mark an incident as a duplicate of a canonical parent incident."""
        incident = self.get_incident(incident_id)
        canonical = self.get_incident(canonical_incident_id)

        incident.status = IncidentStatus.DUPLICATE
        incident.duplicate_of_id = canonical.id
        incident.updated_at = datetime.now(timezone.utc)
        return self.repository.save_incident(incident)


# Global singleton
clinical_incident_service = ClinicalIncidentService()

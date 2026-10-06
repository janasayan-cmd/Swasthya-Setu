"""Phase 49: Safety Incident Ingestion & Signal Promotion Service.

Ingests safety signals from safety gates, external providers, decision traces,
and async workflows. Deduplicates signals within configurable time windows
and promotes distinct signals to incident candidates without losing safety events.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import IncidentDuplicateException
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.incidents import (
    IncidentImpactStatus,
    IncidentRecord,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    IncidentType,
    SafetySignal,
    SafetySignalCreateRequest,
)
from app.services.audit_service import AuditService, audit_service

logger = logging.getLogger("app.safety_incident_service")


class SafetyIncidentService:
    """Service governing safety signal intake, correlation, and candidate incident promotion."""

    def __init__(
        self,
        repository: Optional[SafetyIncidentRepository] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_incident_repository
        self.audit_service = audit_svc or audit_service

    async def ingest_safety_signal(
        self,
        request: SafetySignalCreateRequest,
        actor_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[SafetySignal, Optional[IncidentRecord]]:
        """Ingest a safety signal, check for duplicate within window, and correlate/create incident.

        Returns (signal, incident_candidate).
        """
        now = datetime.now(timezone.utc)
        correlation_key = (
            request.correlation_id
            or f"{request.incident_type.value}:{request.resource_type or 'gen'}:{request.resource_id or 'gen'}:{request.decision_id or 'none'}"
        )

        # 1. Deduplication check
        window_seconds = settings.INCIDENT_DEDUPLICATION_WINDOW_MINUTES * 60
        existing_signal = self.repository.find_duplicate_signal(correlation_key, window_seconds=window_seconds)

        signal = SafetySignal(
            source=request.source,
            incident_type=request.incident_type,
            summary=request.summary,
            description=request.description,
            severity_candidate=request.severity_candidate,
            impact_candidate=request.impact_candidate,
            decision_id=request.decision_id,
            safety_check_id=request.safety_check_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            alert_id=request.alert_id,
            patient_id=request.patient_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            resource_version=request.resource_version,
            correlation_id=correlation_key,
            metadata=request.metadata,
            detected_at=now,
        )
        self.repository.save_signal(signal)

        # 2. Audit emission
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_SIGNAL_CREATED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action=f"safety_signal:{request.incident_type.value}",
                    resource_type=request.resource_type or "safety_signal",
                    resource_id=signal.id,
                    metadata={
                        "signal_id": signal.id,
                        "incident_type": request.incident_type.value,
                        "severity_candidate": request.severity_candidate.value,
                        "is_duplicate": existing_signal is not None,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for signal %s: %s", signal.id, ex)

        # 3. Correlation with existing incident or promotion to candidate
        incident: Optional[IncidentRecord] = None
        if existing_signal:
            # Correlate to existing incident if one exists for the earlier signal
            matching_incidents = self.repository.list_incidents(
                patient_id=request.patient_id,
                incident_type=request.incident_type,
            )
            for cand in matching_incidents:
                if existing_signal.id in cand.signal_ids and cand.status not in [IncidentStatus.CLOSED, IncidentStatus.REJECTED]:
                    cand.signal_ids.append(signal.id)
                    self.repository.save_incident(cand)
                    incident = cand
                    break
        else:
            # Promote to new incident candidate
            incident = IncidentRecord(
                title=f"Safety Incident: {request.incident_type.value} - {request.summary[:80]}",
                description=request.description or request.summary,
                incident_type=request.incident_type,
                status=IncidentStatus.DETECTED,
                severity=request.severity_candidate,
                impact_status=request.impact_candidate,
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
                signal_ids=[signal.id],
                occurred_at=now,
                detected_at=now,
                recorded_at=now,
            )
            self.repository.save_incident(incident)

        return signal, incident


# Global singleton
safety_incident_service = SafetyIncidentService()

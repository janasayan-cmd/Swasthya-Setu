"""Phase 49: Incident Evidence & Timeline Reconstruction Service.

Preserves evidence relationships without duplicating raw PHI and reconstructs
chronological incident timelines respecting Phase 46 temporal integrity.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import IncidentNotFoundException
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.schemas.incident_evidence import (
    EvidenceAttachRequest,
    EvidenceReference,
    EvidenceType,
    IncidentTimelineEntry,
)
from app.schemas.incidents import IncidentRecord


class IncidentEvidenceService:
    """Service governing evidence reference linking and timeline reconstruction."""

    def __init__(self, repository: Optional[SafetyIncidentRepository] = None) -> None:
        self.repository = repository or safety_incident_repository

    def attach_evidence(
        self,
        incident_id: str,
        request: EvidenceAttachRequest,
        recorded_by_id: Optional[str] = None,
    ) -> EvidenceReference:
        """Attach a foreign evidence reference to the incident."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")

        # Sanitize metadata to exclude forbidden clinical payload / raw PHI
        sanitized_meta = {
            k: v for k, v in request.metadata.items()
            if k.lower() not in {"patient_data", "prescription", "raw_document", "password", "token"}
        }

        evidence = EvidenceReference(
            incident_id=incident_id,
            evidence_type=request.evidence_type,
            reference_id=request.reference_id,
            summary=request.summary,
            source_system=request.source_system,
            snapshot_hash=request.snapshot_hash,
            metadata=sanitized_meta,
            recorded_by_id=recorded_by_id,
        )
        return self.repository.save_evidence(evidence)

    def list_evidence(self, incident_id: str) -> List[EvidenceReference]:
        """List all attached evidence references for an incident."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")
        return self.repository.list_evidence(incident_id)

    def reconstruct_timeline(self, incident_id: str) -> List[IncidentTimelineEntry]:
        """Reconstruct the factual chronological timeline of the incident."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")

        timeline: List[IncidentTimelineEntry] = []

        # 1. Base milestone events
        timeline.append(
            IncidentTimelineEntry(
                timestamp=incident.occurred_at,
                event_time_type="OCCURRED",
                title="Event Occurred",
                description=f"Underlying safety event occurred in {incident.source.value}.",
                source=incident.source.value,
            )
        )

        if incident.detected_at != incident.occurred_at:
            timeline.append(
                IncidentTimelineEntry(
                    timestamp=incident.detected_at,
                    event_time_type="DETECTED",
                    title="Event Detected",
                    description="Safety signal detected by runtime monitoring or safety gate.",
                    source="SAFETY_MONITORING",
                )
            )

        timeline.append(
            IncidentTimelineEntry(
                timestamp=incident.recorded_at,
                event_time_type="RECORDED",
                title="Incident Candidate Recorded",
                description=f"Incident candidate '{incident.title}' created in status '{incident.status.value}'.",
                source="INCIDENT_SERVICE",
            )
        )

        if incident.contained_at:
            timeline.append(
                IncidentTimelineEntry(
                    timestamp=incident.contained_at,
                    event_time_type="CONTAINED",
                    title="Risk Contained",
                    description=f"Containment action applied: {incident.containment_action}",
                    source="SAFETY_OFFICER",
                )
            )

        if incident.resolved_at:
            timeline.append(
                IncidentTimelineEntry(
                    timestamp=incident.resolved_at,
                    event_time_type="RESOLVED",
                    title="Incident Resolved",
                    description=f"Remediation confirmed: {incident.resolution_summary}",
                    source="INVESTIGATION_TEAM",
                )
            )

        if incident.closed_at:
            timeline.append(
                IncidentTimelineEntry(
                    timestamp=incident.closed_at,
                    event_time_type="CLOSED",
                    title="Incident Formally Closed",
                    description=f"Closure validated: {incident.closure_reason}",
                    source="SAFETY_OFFICER",
                )
            )

        if incident.reopened_at:
            timeline.append(
                IncidentTimelineEntry(
                    timestamp=incident.reopened_at,
                    event_time_type="REOPENED",
                    title="Incident Reopened",
                    description="Incident reopened due to recurrence or new findings.",
                    source="SAFETY_OFFICER",
                )
            )

        # 2. Add attached evidence references
        evidences = self.repository.list_evidence(incident_id)
        for ev in evidences:
            timeline.append(
                IncidentTimelineEntry(
                    timestamp=ev.recorded_at,
                    event_time_type="EVIDENCE_ATTACHED",
                    title=f"Evidence Linked: {ev.evidence_type.value}",
                    description=ev.summary,
                    source=ev.source_system,
                    evidence_id=ev.id,
                )
            )

        # Sort timeline chronologically
        timeline.sort(key=lambda t: t.timestamp)
        return timeline


# Global singleton
incident_evidence_service = IncidentEvidenceService()

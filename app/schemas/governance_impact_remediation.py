"""Phase 87: Impact Remediation and Escalation Coordination Schemas.

Defines schemas for routing significant dependency concerns to authoritative workflows:
Phase 63 (Risk), Phase 67 (Exception), Phase 49 (Incident), Phase 54 (Corrective Action),
Phase 72 (Management Review), Phase 80 (Continuity Planning).
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.governance_disruption_common import (
    MANDATORY_DISRUPTION_IMPACT_DISCLAIMER,
    FollowUpDestinationWorkflow,
    FollowUpStatus,
    ImpactSeverity,
)


class ImpactFollowUpRecord(BaseModel):
    follow_up_id: str
    tenant_id: str
    assessment_id: str
    finding_reference_id: Optional[str] = None
    affected_capability_ref: str
    responsible_owner_ref: str
    destination_workflow: FollowUpDestinationWorkflow
    priority_severity: ImpactSeverity = ImpactSeverity.HIGH
    status: FollowUpStatus = FollowUpStatus.PROPOSED
    proposal_description: str
    external_workflow_reference_id: Optional[str] = None
    handoff_timestamp: Optional[datetime] = None
    acknowledgement_timestamp: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    outcome_notes: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class CreateImpactFollowUpRequest(BaseModel):
    finding_reference_id: Optional[str] = None
    affected_capability_ref: str
    responsible_owner_ref: str
    destination_workflow: FollowUpDestinationWorkflow
    priority_severity: ImpactSeverity = ImpactSeverity.HIGH
    proposal_description: str


class SubmitImpactFollowUpRequest(BaseModel):
    submission_notes: Optional[str] = None


class AcknowledgeImpactFollowUpRequest(BaseModel):
    external_workflow_reference_id: str
    acknowledgement_notes: Optional[str] = None

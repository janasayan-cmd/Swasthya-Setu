"""Phase 83: Knowledge Acknowledgement and Application Evidence Schemas.

Supports tracking user acknowledgement of distributed guidance and
verifying evidence of practical application in exercises or real events.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_knowledge import (
    MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER,
)


class AcknowledgementStatus(str, Enum):
    DELIVERED = "DELIVERED"
    VIEWED = "VIEWED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class KnowledgeApplicationContext(str, Enum):
    CONTINUITY_EXERCISE = "CONTINUITY_EXERCISE"
    REAL_DISRUPTION_RESPONSE = "REAL_DISRUPTION_RESPONSE"
    RECOVERY_COORDINATION = "RECOVERY_COORDINATION"
    DELEGATION_HANDOFF = "DELEGATION_HANDOFF"
    INCIDENT_POSTMORTEM = "INCIDENT_POSTMORTEM"
    ROUTINE_PREPAREDNESS_DRILL = "ROUTINE_PREPAREDNESS_DRILL"
    OTHER = "OTHER"


class ApplicationEvidenceStatus(str, Enum):
    RECORDED = "RECORDED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class KnowledgeAcknowledgementRecord(BaseModel):
    acknowledgement_id: str
    tenant_id: str
    campaign_id: str
    knowledge_id: str
    user_id: str
    user_role: Optional[str] = None
    facility_id: Optional[str] = None
    department_id: Optional[str] = None
    status: AcknowledgementStatus = AcknowledgementStatus.DELIVERED
    delivered_at: datetime = Field(default_factory=datetime.utcnow)
    viewed_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledgement_notes: Optional[str] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class RecordAcknowledgementRequest(BaseModel):
    status: AcknowledgementStatus = AcknowledgementStatus.ACKNOWLEDGED
    acknowledgement_notes: Optional[str] = None


class KnowledgeApplicationEvidenceRecord(BaseModel):
    evidence_id: str
    tenant_id: str
    knowledge_id: str
    operational_context: KnowledgeApplicationContext
    operational_reference_id: Optional[str] = None
    description: str
    observed_effectiveness_rating: int = Field(..., ge=1, le=5, description="1 (ineffective) to 5 (highly effective)")
    phase55_assessment_id: Optional[str] = None
    submitted_by: str
    verified_by: Optional[str] = None
    status: ApplicationEvidenceStatus = ApplicationEvidenceStatus.RECORDED
    rejection_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class SubmitApplicationEvidenceRequest(BaseModel):
    knowledge_id: str
    operational_context: KnowledgeApplicationContext
    operational_reference_id: Optional[str] = None
    description: str
    observed_effectiveness_rating: int = Field(..., ge=1, le=5)
    phase55_assessment_id: Optional[str] = None


class VerifyApplicationEvidenceRequest(BaseModel):
    verified: bool
    notes: Optional[str] = None

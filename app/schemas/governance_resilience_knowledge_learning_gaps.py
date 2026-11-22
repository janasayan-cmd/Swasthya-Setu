"""Phase 83: Organizational Learning Gap Schemas.

Supports tracking systemic resilience learning gaps, unaddressed exercise findings,
and coordinating referral to Phase 54 CAPA when systemic risks are validated.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_knowledge import (
    MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER,
)


class LearningGapType(str, Enum):
    UNADDRESSED_EXERCISE_FINDING = "UNADDRESSED_EXERCISE_FINDING"
    REPEATED_DISRUPTION_FAILURE = "REPEATED_DISRUPTION_FAILURE"
    KNOWLEDGE_ADOPTION_DEFICIT = "KNOWLEDGE_ADOPTION_DEFICIT"
    OUTDATED_OPERATING_GUIDANCE = "OUTDATED_OPERATING_GUIDANCE"
    UNVERIFIED_COMPETENCY = "UNVERIFIED_COMPETENCY"
    ROLE_SUCCESSION_EXPOSURE = "ROLE_SUCCESSION_EXPOSURE"
    CROSS_ORGANIZATIONAL_SILO = "CROSS_ORGANIZATIONAL_SILO"


class LearningGapSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LearningGapStatus(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    VALIDATED = "VALIDATED"
    CAPA_REFERRED = "CAPA_REFERRED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class OrganizationalLearningGapRecord(BaseModel):
    gap_id: str
    tenant_id: str
    gap_type: LearningGapType
    severity: LearningGapSeverity
    title: str
    description: str
    affected_capabilities: List[str] = Field(default_factory=list)
    affected_roles: List[str] = Field(default_factory=list)
    affected_facilities: List[str] = Field(default_factory=list)
    source_exercise_id: Optional[str] = None
    source_disruption_id: Optional[str] = None
    identified_by: str
    validated_by: Optional[str] = None
    status: LearningGapStatus = LearningGapStatus.IDENTIFIED
    capa_referral_id: Optional[str] = None
    resolution_notes: Optional[str] = None
    identified_at: datetime = Field(default_factory=datetime.utcnow)
    validated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class IdentifyLearningGapRequest(BaseModel):
    gap_type: LearningGapType
    severity: LearningGapSeverity
    title: str
    description: str
    affected_capabilities: List[str] = Field(default_factory=list)
    affected_roles: List[str] = Field(default_factory=list)
    affected_facilities: List[str] = Field(default_factory=list)
    source_exercise_id: Optional[str] = None
    source_disruption_id: Optional[str] = None


class ValidateLearningGapRequest(BaseModel):
    is_valid: bool
    validation_notes: Optional[str] = None


class ReferGapToCAPARequest(BaseModel):
    capa_title: str
    capa_description: str
    priority: str = "HIGH"


class ResolveLearningGapRequest(BaseModel):
    resolution_notes: str

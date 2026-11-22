"""Phase 84: Resilience Capability Framework Schemas.

Supports configurable, version-controlled organizational resilience capability frameworks
with explicit domains, required proficiencies, assessment frequencies, and lifecycle states.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER = (
    "Organizational resilience capability assessments and operational readiness verification "
    "records are administrative governance instruments and do NOT constitute professional "
    "licensing, clinical credentialing, medical competence certification, or authorization for "
    "clinical practice. Phase 84 does not replace authoritative workflows of Phases 49, 54, 55, "
    "63, 67, 69, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, or 83."
)


class CapabilityDomain(str, Enum):
    GOVERNANCE_CONTINUITY = "GOVERNANCE_CONTINUITY"
    RECOVERY_COORDINATION = "RECOVERY_COORDINATION"
    DECISION_CONTINUITY = "DECISION_CONTINUITY"
    EVIDENCE_CONTINUITY = "EVIDENCE_CONTINUITY"
    PERSONNEL_READINESS = "PERSONNEL_READINESS"
    DEPENDENCY_MANAGEMENT = "DEPENDENCY_MANAGEMENT"
    EXERCISE_PARTICIPATION = "EXERCISE_PARTICIPATION"


class ProficiencyLevel(str, Enum):
    AWARENESS = "AWARENESS"
    WORKING_KNOWLEDGE = "WORKING_KNOWLEDGE"
    PROFICIENT = "PROFICIENT"
    EXPERT = "EXPERT"


class FrameworkLifecycleState(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class CapabilityItemDefinition(BaseModel):
    capability_id: str
    name: str
    description: str
    domain: CapabilityDomain
    organizational_scope: str = "GLOBAL"
    applicable_roles: List[str] = Field(default_factory=list)
    required_proficiency: ProficiencyLevel = ProficiencyLevel.WORKING_KNOWLEDGE
    assessment_method: str = "PRACTICAL_DEMONSTRATION"
    required_evidence_types: List[str] = Field(default_factory=list)
    assessment_frequency_days: int = 365


class ResilienceCapabilityFrameworkRecord(BaseModel):
    framework_id: str
    tenant_id: str
    framework_name: str
    description: str
    version: int = 1
    lifecycle_state: FrameworkLifecycleState = FrameworkLifecycleState.DRAFT
    capabilities: List[CapabilityItemDefinition] = Field(default_factory=list)
    created_by: str
    submitted_by: Optional[str] = None
    approved_by: Optional[str] = None
    published_at: Optional[datetime] = None
    review_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class CreateFrameworkRequest(BaseModel):
    framework_name: str
    description: str
    capabilities: List[CapabilityItemDefinition] = Field(default_factory=list)
    review_date: Optional[datetime] = None


class UpdateFrameworkRequest(BaseModel):
    framework_name: Optional[str] = None
    description: Optional[str] = None
    capabilities: Optional[List[CapabilityItemDefinition]] = None
    review_date: Optional[datetime] = None


class SubmitFrameworkRequest(BaseModel):
    notes: Optional[str] = None


class ApproveFrameworkRequest(BaseModel):
    notes: Optional[str] = None


class PublishFrameworkRequest(BaseModel):
    effective_date: Optional[datetime] = None
    notes: Optional[str] = None

"""Phase 83: Resilience Knowledge Management Schemas.

Supports controlled authoring, validation, versioning, publication, withdrawal,
and lifecycle tracking of resilience knowledge assets.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER = (
    "Resilience knowledge management and organizational learning records are "
    "administrative capability development instruments and do NOT constitute proof of "
    "clinical safety, regulatory compliance, operational competency, or effective recovery. "
    "Phase 83 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, "
    "70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, or 82."
)


class KnowledgeCategory(str, Enum):
    VALIDATED_LESSONS_LEARNED = "VALIDATED_LESSONS_LEARNED"
    CONTINUITY_OPERATING_GUIDANCE = "CONTINUITY_OPERATING_GUIDANCE"
    RECOVERY_COORDINATION_GUIDANCE = "RECOVERY_COORDINATION_GUIDANCE"
    EXERCISE_LEARNING = "EXERCISE_LEARNING"
    DEPENDENCY_MANAGEMENT_GUIDANCE = "DEPENDENCY_MANAGEMENT_GUIDANCE"
    GOVERNANCE_DECISION_CONTINUITY = "GOVERNANCE_DECISION_CONTINUITY"
    EVIDENCE_RECONCILIATION_GUIDANCE = "EVIDENCE_RECONCILIATION_GUIDANCE"
    DELEGATED_AUTHORITY_GUIDANCE = "DELEGATED_AUTHORITY_GUIDANCE"
    PERSONNEL_READINESS_GUIDANCE = "PERSONNEL_READINESS_GUIDANCE"
    OPERATIONAL_HANDOFF_GUIDANCE = "OPERATIONAL_HANDOFF_GUIDANCE"
    PREPAREDNESS_IMPROVEMENT_GUIDANCE = "PREPAREDNESS_IMPROVEMENT_GUIDANCE"
    ORGANIZATIONAL_RESILIENCE_PRACTICES = "ORGANIZATIONAL_RESILIENCE_PRACTICES"


class KnowledgeConfidentiality(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"


class KnowledgeLifecycleState(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED_FOR_REVIEW = "SUBMITTED_FOR_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    VALIDATED = "VALIDATED"
    APPROVED_FOR_PUBLICATION = "APPROVED_FOR_PUBLICATION"
    PUBLISHED = "PUBLISHED"
    UNDER_SCHEDULED_REVIEW = "UNDER_SCHEDULED_REVIEW"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"
    ARCHIVED = "ARCHIVED"


class ResilienceKnowledgeRecord(BaseModel):
    knowledge_id: str
    tenant_id: str
    title: str
    category: KnowledgeCategory
    summary: str
    content: str
    source_phase: Optional[str] = None
    source_reference_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    confidentiality_level: KnowledgeConfidentiality = KnowledgeConfidentiality.INTERNAL
    owner_id: str
    author_id: str
    current_state: KnowledgeLifecycleState = KnowledgeLifecycleState.DRAFT
    version: int = 1
    previous_version_id: Optional[str] = None
    review_due_date: Optional[datetime] = None
    published_at: Optional[datetime] = None
    validated_by: Optional[str] = None
    approved_by: Optional[str] = None
    withdrawn_reason: Optional[str] = None
    superseded_by_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class CreateResilienceKnowledgeRequest(BaseModel):
    title: str
    category: KnowledgeCategory
    summary: str
    content: str
    source_phase: Optional[str] = None
    source_reference_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    confidentiality_level: KnowledgeConfidentiality = KnowledgeConfidentiality.INTERNAL
    review_due_date: Optional[datetime] = None


class UpdateResilienceKnowledgeRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[KnowledgeCategory] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    confidentiality_level: Optional[KnowledgeConfidentiality] = None
    review_due_date: Optional[datetime] = None
    material_change: bool = False


class SubmitForReviewRequest(BaseModel):
    submission_notes: Optional[str] = None


class ReviewResilienceKnowledgeRequest(BaseModel):
    outcome: str = Field(..., description="VALIDATE, REQUEST_CHANGES, or REJECT")
    review_notes: Optional[str] = None


class ApproveForPublicationRequest(BaseModel):
    approval_notes: Optional[str] = None


class PublishResilienceKnowledgeRequest(BaseModel):
    publication_notes: Optional[str] = None


class WithdrawResilienceKnowledgeRequest(BaseModel):
    reason: str


class SupersedeResilienceKnowledgeRequest(BaseModel):
    new_knowledge_id: str
    rationale: str

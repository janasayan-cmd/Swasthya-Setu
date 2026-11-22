"""Phase 83: Capability Development Recommendation Schemas.

Supports advisory capability development recommendations targeted at closing
organizational learning gaps and building sustained continuous preparedness.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_knowledge import (
    MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER,
)


class CapabilityActivityType(str, Enum):
    TARGETED_TRAINING = "TARGETED_TRAINING"
    SIMULATION_DRILL = "SIMULATION_DRILL"
    DESKTOP_WALKTHROUGH = "DESKTOP_WALKTHROUGH"
    PEER_KNOWLEDGE_EXCHANGE = "PEER_KNOWLEDGE_EXCHANGE"
    TOOL_ENHANCEMENT = "TOOL_ENHANCEMENT"
    PROCESS_STANDARDIZATION = "PROCESS_STANDARDIZATION"
    SUCCESSION_PREPARATION = "SUCCESSION_PREPARATION"
    CHECKLIST_REFINEMENT = "CHECKLIST_REFINEMENT"
    CROSS_TRAINING = "CROSS_TRAINING"
    DOCUMENTATION_OVERHAUL = "DOCUMENTATION_OVERHAUL"


class RecommendationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"


class ResilienceCapabilityRecommendationRecord(BaseModel):
    recommendation_id: str
    tenant_id: str
    activity_type: CapabilityActivityType
    priority: RecommendationPriority
    title: str
    rationalization: str
    target_capabilities: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    target_facilities: List[str] = Field(default_factory=list)
    linked_learning_gap_ids: List[str] = Field(default_factory=list)
    linked_knowledge_ids: List[str] = Field(default_factory=list)
    status: RecommendationStatus = RecommendationStatus.PROPOSED
    proposed_by: str
    approved_by: Optional[str] = None
    completion_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class ProposeCapabilityRecommendationRequest(BaseModel):
    activity_type: CapabilityActivityType
    priority: RecommendationPriority
    title: str
    rationalization: str
    target_capabilities: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    target_facilities: List[str] = Field(default_factory=list)
    linked_learning_gap_ids: List[str] = Field(default_factory=list)
    linked_knowledge_ids: List[str] = Field(default_factory=list)


class UpdateRecommendationStatusRequest(BaseModel):
    status: RecommendationStatus
    notes: Optional[str] = None
    scheduled_date: Optional[datetime] = None

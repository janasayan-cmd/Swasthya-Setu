"""Phase 83: Knowledge Conflict Detection and Resolution Schemas.

Supports identifying and systematically resolving contradictory, overlapping,
or obsolete resilience guidance across operational silos.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_knowledge import (
    MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER,
)


class KnowledgeConflictType(str, Enum):
    DIRECT_CONTRADICTION = "DIRECT_CONTRADICTION"
    VERSION_AMBIGUITY = "VERSION_AMBIGUITY"
    SCOPE_OVERLAP = "SCOPE_OVERLAP"
    JURISDICTIONAL_MISALIGNMENT = "JURISDICTIONAL_MISALIGNMENT"
    POLICY_DIVERGENCE = "POLICY_DIVERGENCE"
    OBSOLETE_PRACTICE_PERSISTENCE = "OBSOLETE_PRACTICE_PERSISTENCE"


class ConflictStatus(str, Enum):
    DETECTED = "DETECTED"
    UNDER_EVALUATION = "UNDER_EVALUATION"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class KnowledgeConflictRecord(BaseModel):
    conflict_id: str
    tenant_id: str
    conflict_type: KnowledgeConflictType
    description: str
    primary_knowledge_id: str
    conflicting_knowledge_id: str
    detected_by: str
    status: ConflictStatus = ConflictStatus.DETECTED
    resolution_strategy: Optional[str] = None
    resolution_rationale: Optional[str] = None
    resolved_by: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class DetectKnowledgeConflictRequest(BaseModel):
    conflict_type: KnowledgeConflictType
    description: str
    primary_knowledge_id: str
    conflicting_knowledge_id: str


class ResolveKnowledgeConflictRequest(BaseModel):
    resolution_strategy: str
    resolution_rationale: str
    supersede_conflicting: bool = False

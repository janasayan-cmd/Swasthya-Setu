"""Phase 63: Clinical Safety Unresolved-Question Schemas.

Defines schemas for explicitly capturing, assigning, and resolving questions
relevant to governed risk review without silent backend assumptions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class QuestionCategory(str, Enum):
    """Categorization of unresolved questions in governed risk review."""

    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNCERTAIN_SCOPE = "UNCERTAIN_SCOPE"
    UNCERTAIN_VERSION = "UNCERTAIN_VERSION"
    UNRESOLVED_RECURRENCE = "UNRESOLVED_RECURRENCE"
    UNCLEAR_CONTROL_STATUS = "UNCLEAR_CONTROL_STATUS"
    UNRESOLVED_INCIDENT_RELATIONSHIP = "UNRESOLVED_INCIDENT_RELATIONSHIP"
    UNRESOLVED_ASSURANCE_STATUS = "UNRESOLVED_ASSURANCE_STATUS"
    UNRESOLVED_EFFECTIVENESS_STATUS = "UNRESOLVED_EFFECTIVENESS_STATUS"
    UNRESOLVED_GOVERNANCE_REQUIREMENT = "UNRESOLVED_GOVERNANCE_REQUIREMENT"


class QuestionStatus(str, Enum):
    """Lifecycle status of an unresolved question."""

    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    EVIDENCE_REQUESTED = "EVIDENCE_REQUESTED"
    EVIDENCE_RECEIVED = "EVIDENCE_RECEIVED"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"


class UnresolvedQuestionRecord(BaseModel):
    """Structured record for an explicit unresolved issue."""

    model_config = ConfigDict(extra="ignore")

    question_id: str = Field(default_factory=lambda: f"q-{uuid.uuid4().hex[:12]}")
    review_id: str
    category: QuestionCategory
    question_text: str
    status: QuestionStatus = QuestionStatus.OPEN
    created_by: str
    assigned_to: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list)
    resolution_summary: Optional[str] = None
    resolved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateQuestionRequest(BaseModel):
    """Request payload to create a new unresolved question."""

    model_config = ConfigDict(extra="ignore")

    category: QuestionCategory
    question_text: str
    assigned_to: Optional[str] = None
    evidence_references: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ResolveQuestionRequest(BaseModel):
    """Request payload to resolve an existing question."""

    model_config = ConfigDict(extra="ignore")

    resolution_summary: str
    evidence_references: Optional[List[str]] = None

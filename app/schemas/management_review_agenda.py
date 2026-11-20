"""Phase 72: Management Review Agenda, Input Consolidation & Review Package Schemas.

Defines schemas for:
- Review agenda management and topic prioritization
- Cross-phase input consolidation (Phases 49-71)
- Review package generation, compilation, and reproducibility
- Review readiness evaluation and quorum / prerequisite validation
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AgendaCategory(str, Enum):
    """Categories of agenda topics in a clinical safety management review."""

    STATUS_OF_PREVIOUS_ACTIONS = "STATUS_OF_PREVIOUS_ACTIONS"
    CHANGES_IN_INTERNAL_EXTERNAL_ISSUES = "CHANGES_IN_INTERNAL_EXTERNAL_ISSUES"
    CLINICAL_SAFETY_PERFORMANCE = "CLINICAL_SAFETY_PERFORMANCE"
    AUDIT_FINDINGS_AND_INTELLIGENCE = "AUDIT_FINDINGS_AND_INTELLIGENCE"
    COMPLIANCE_AND_POLICY_CONFORMANCE = "COMPLIANCE_AND_POLICY_CONFORMANCE"
    RISK_AND_EXCEPTION_REVIEWS = "RISK_AND_EXCEPTION_REVIEWS"
    CAPA_AND_CORRECTIVE_ACTION_STATUS = "CAPA_AND_CORRECTIVE_ACTION_STATUS"
    RESOURCE_ADEQUACY = "RESOURCE_ADEQUACY"
    SAFETY_SYSTEM_EFFECTIVENESS = "SAFETY_SYSTEM_EFFECTIVENESS"
    OPPORTUNITIES_FOR_IMPROVEMENT = "OPPORTUNITIES_FOR_IMPROVEMENT"
    OTHER_GOVERNANCE_TOPICS = "OTHER_GOVERNANCE_TOPICS"


class AgendaItemPriority(str, Enum):
    """Urgency / priority of an agenda item."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AgendaDiscussionStatus(str, Enum):
    """Status of discussion for an agenda item during the review."""

    PENDING = "PENDING"
    IN_DISCUSSION = "IN_DISCUSSION"
    CONCLUDED = "CONCLUDED"
    DEFERRED = "DEFERRED"


class ReviewAgendaItemRecord(BaseModel):
    """Domain record representing an individual agenda topic."""

    model_config = ConfigDict(extra="ignore")

    agenda_item_id: str = Field(default_factory=lambda: f"gmai-{uuid.uuid4().hex[:12]}")
    review_id: str
    title: str
    description: str
    category: AgendaCategory = AgendaCategory.CLINICAL_SAFETY_PERFORMANCE
    priority: AgendaItemPriority = AgendaItemPriority.MEDIUM
    discussion_status: AgendaDiscussionStatus = AgendaDiscussionStatus.PENDING

    presenter_id: Optional[str] = None
    presenter_name: Optional[str] = None
    allocated_minutes: int = 15
    order: int = 1

    linked_sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsolidatedInputRecord(BaseModel):
    """Domain record representing evidence/data gathered from Phases 49-71."""

    model_config = ConfigDict(extra="ignore")

    input_id: str = Field(default_factory=lambda: f"gmin-{uuid.uuid4().hex[:12]}")
    review_id: str
    source_phase: str
    source_id: str
    source_type: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    collected_by: str


class ReviewPackageRecord(BaseModel):
    """Domain record representing the compiled, reproducible review package."""

    model_config = ConfigDict(extra="ignore")

    package_id: str = Field(default_factory=lambda: f"gmpk-{uuid.uuid4().hex[:12]}")
    review_id: str
    version: int = 1
    package_title: str
    executive_summary: str
    agenda_item_ids: List[str] = Field(default_factory=list)
    input_ids: List[str] = Field(default_factory=list)
    status: str = "COMPILED"  # COMPILED, LOCKED
    compiled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    compiled_by: str
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReadinessOutcome(str, Enum):
    """Outcome of meeting readiness check."""

    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    NOT_READY = "NOT_READY"


class ReadinessCheckResponse(BaseModel):
    """Response containing detailed readiness evaluation results."""

    model_config = ConfigDict(extra="ignore")

    review_id: str
    outcome: ReadinessOutcome
    is_ready: bool
    checks: Dict[str, bool] = Field(default_factory=dict)
    deficiencies: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request Models
class CreateAgendaItemRequest(BaseModel):
    """Request payload to add an agenda item to a review."""

    model_config = ConfigDict(extra="ignore")

    title: str
    description: str
    category: Optional[AgendaCategory] = AgendaCategory.CLINICAL_SAFETY_PERFORMANCE
    priority: Optional[AgendaItemPriority] = AgendaItemPriority.MEDIUM
    presenter_id: Optional[str] = None
    presenter_name: Optional[str] = None
    allocated_minutes: Optional[int] = 15
    order: Optional[int] = 1
    linked_sources: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateAgendaItemRequest(BaseModel):
    """Request payload to update an existing agenda item."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[AgendaCategory] = None
    priority: Optional[AgendaItemPriority] = None
    discussion_status: Optional[AgendaDiscussionStatus] = None
    presenter_id: Optional[str] = None
    presenter_name: Optional[str] = None
    allocated_minutes: Optional[int] = None
    order: Optional[int] = None
    linked_sources: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class CollectInputsRequest(BaseModel):
    """Request payload to gather and index inputs from upstream governance phases."""

    model_config = ConfigDict(extra="ignore")

    source_phase: str
    source_id: str
    source_type: str
    summary: str
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GenerateReviewPackageRequest(BaseModel):
    """Request payload to compile a review package from agenda items and inputs."""

    model_config = ConfigDict(extra="ignore")

    package_title: str
    executive_summary: str
    lock_package: Optional[bool] = False
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

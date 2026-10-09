"""Phase 63: Clinical Safety Routing Schemas.

Defines schemas for controlled routing of governed risk decisions to authoritative
downstream phases (Phase 49 Incident, Phase 50 Learning, Phase 51 Governance,
Phase 52 Assurance, Phase 54 Action, Phase 55 Effectiveness, Phase 56 Improvement,
Phase 59 Surveillance, Phase 62 Reassessment).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RoutingDestination(str, Enum):
    """Authoritative downstream destination phases."""

    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"
    PHASE_50_LEARNING = "PHASE_50_LEARNING"
    PHASE_51_GOVERNANCE = "PHASE_51_GOVERNANCE"
    PHASE_52_ASSURANCE = "PHASE_52_ASSURANCE"
    PHASE_54_SAFETY_ACTION = "PHASE_54_SAFETY_ACTION"
    PHASE_55_EFFECTIVENESS = "PHASE_55_EFFECTIVENESS"
    PHASE_56_IMPROVEMENT = "PHASE_56_IMPROVEMENT"
    PHASE_59_SURVEILLANCE = "PHASE_59_SURVEILLANCE"
    PHASE_62_REASSESSMENT = "PHASE_62_REASSESSMENT"


class RiskRoutingRecord(BaseModel):
    """Immutable record of routing to an authoritative downstream phase."""

    model_config = ConfigDict(extra="ignore")

    routing_id: str = Field(default_factory=lambda: f"route-{uuid.uuid4().hex[:12]}")
    review_id: str
    destination: RoutingDestination
    reason: str
    target_reference: Optional[str] = None
    routed_by: str
    routed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "COMPLETED"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiRoutingRecord(BaseModel):
    """Composite routing record when a disposition produces multiple routing destinations."""

    model_config = ConfigDict(extra="ignore")

    multi_routing_id: str = Field(default_factory=lambda: f"mroute-{uuid.uuid4().hex[:12]}")
    review_id: str
    routes: List[RiskRoutingRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RouteReviewRequest(BaseModel):
    """Request payload to route a reviewed risk decision to downstream phases."""

    model_config = ConfigDict(extra="ignore")

    destinations: List[RoutingDestination]
    reason: str
    target_reference: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RoutingResponse(BaseModel):
    """Response payload for executed routings."""

    model_config = ConfigDict(extra="ignore")

    review_id: str
    destinations: List[RoutingDestination]
    routes: List[RiskRoutingRecord]
    message: str

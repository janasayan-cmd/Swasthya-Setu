"""Phase 65: Safety Completion Readiness Schemas.

Defines readiness evaluation states, evaluation records, and response envelopes.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CompletionReadinessState(str, Enum):
    """Authoritative readiness states for completion eligibility."""

    NOT_EVALUATED = "NOT_EVALUATED"
    EVALUATING = "EVALUATING"
    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    HANDOFFS_PENDING = "HANDOFFS_PENDING"
    OUTCOMES_PENDING = "OUTCOMES_PENDING"
    FOLLOW_UP_PENDING = "FOLLOW_UP_PENDING"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


class ReadinessEvaluationRecord(BaseModel):
    """Detailed record of a completion readiness evaluation."""

    model_config = ConfigDict(extra="ignore")

    evaluation_id: str = Field(default_factory=lambda: f"eval-{uuid.uuid4().hex[:12]}")
    completion_id: str
    readiness_state: CompletionReadinessState
    source_revision: str = "v1.0.0"
    applicable_policy_version: str = "v1.0.0"

    # Aggregated metrics
    total_requirements: int = 0
    satisfied_requirements: int = 0
    pending_requirements: int = 0
    blocked_requirements: int = 0

    total_handoffs: int = 0
    completed_handoffs: int = 0
    pending_handoffs: int = 0

    total_outcomes: int = 0
    reconciled_outcomes: int = 0
    pending_outcomes: int = 0

    total_follow_ups: int = 0
    satisfied_follow_ups: int = 0
    pending_follow_ups: int = 0

    # Specific lists
    blockers: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    missing_evidence_refs: List[str] = Field(default_factory=list)

    is_eligible_for_review: bool = False
    is_eligible_for_closure: bool = False
    requires_human_review: bool = True

    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluated_by: str = "system"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluateReadinessRequest(BaseModel):
    """Request payload to trigger an on-demand readiness evaluation."""

    model_config = ConfigDict(extra="ignore")

    reason: Optional[str] = "ON_DEMAND_READINESS_EVALUATION"
    force_recalculation: bool = False
    policy_version: Optional[str] = None
    correlation_id: Optional[str] = None

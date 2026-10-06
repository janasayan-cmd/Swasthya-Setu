"""Decision Traceability & Replay Contracts (Phase 47).

Defines:
- Detailed decision trace inspection models
- Historical investigation and decision comparison responses
- Downstream action references
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decision_review import DecisionReviewRecord
from app.schemas.decisions import DecisionRecord, DecisionStatus


class DownstreamActionReference(BaseModel):
    """Linkage between decision and downstream clinical action entity."""

    action_type: str = Field(description="Downstream entity type e.g. ALERT, TASK, WORKFLOW")
    action_id: str = Field(description="Unique identifier of triggered action")
    triggered_at: datetime = Field(description="Timestamp of trigger")
    status: str = Field(description="Status of action")


class DecisionTraceResponse(BaseModel):
    """Enveloped response providing end-to-end traceability for a clinical decision."""

    model_config = ConfigDict(extra="ignore")

    decision: DecisionRecord
    reviews: List[DecisionReviewRecord] = Field(default_factory=list, description="Audit history of human reviews")
    downstream_actions: List[DownstreamActionReference] = Field(default_factory=list, description="Downstream actions spawned")
    is_stale: bool = Field(default=False, description="True if underlying clinical record version has changed")
    is_expired: bool = Field(default=False, description="True if decision has exceeded its TTL")
    superseded_by_id: Optional[str] = Field(default=None)
    trace_summary: str = Field(description="Human-readable traceability summary")


class DecisionComparisonResponse(BaseModel):
    """Differential analysis between two decision instances."""

    model_config = ConfigDict(extra="ignore")

    base_decision_id: str
    compared_decision_id: str
    changed_inputs: List[str] = Field(default_factory=list)
    changed_rules_or_models: List[str] = Field(default_factory=list)
    status_transition: Dict[str, str] = Field(description="Status change from base to compared")
    output_differences: Dict[str, Any] = Field(default_factory=dict)
    summary: str

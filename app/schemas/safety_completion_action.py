"""Phase 65: Safety Completion Action Schemas.

Defines schemas for authorization, closure, reconciliation, reopening, and reassessment actions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AuthorizeCompletionRequest(BaseModel):
    """Request payload to record completion authorization."""

    model_config = ConfigDict(extra="ignore")

    authorizer_notes: Optional[str] = None
    permit_limitations: bool = False
    explicit_waivers: Optional[List[str]] = Field(default_factory=list)
    acknowledged_prohibited_claims: bool = True
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CompletionAuthorizationRecord(BaseModel):
    """Record of an authoritative completion authorization."""

    model_config = ConfigDict(extra="ignore")

    authorization_id: str = Field(default_factory=lambda: f"authz-{uuid.uuid4().hex[:12]}")
    completion_id: str
    authorizer_id: str
    authorizer_role: str
    authorized_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    permit_limitations: bool = False
    explicit_waivers: List[str] = Field(default_factory=list)
    authorizer_notes: Optional[str] = None
    package_revision: str = "v1.0.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CloseCompletionWorkflowRequest(BaseModel):
    """Request payload to request controlled workflow closure."""

    model_config = ConfigDict(extra="ignore")

    closure_notes: Optional[str] = None
    post_closure_monitoring_registered: bool = False
    monitoring_reference: Optional[str] = None
    acknowledged_closure_invariants: bool = True
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CompletionClosureRecord(BaseModel):
    """Record of a controlled coordination workflow closure."""

    model_config = ConfigDict(extra="ignore")

    closure_id: str = Field(default_factory=lambda: f"cls-{uuid.uuid4().hex[:12]}")
    completion_id: str
    closed_by: str
    closed_by_role: str
    closed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    post_closure_monitoring_registered: bool = False
    monitoring_reference: Optional[str] = None
    closure_notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReopenCompletionWorkflowRequest(BaseModel):
    """Request payload to reopen a closed or stale completion workflow."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    reopen_trigger: str  # e.g., MATERIAL_NEW_OUTCOME, INVALIDATED_OUTCOME, CONFLICTED_EVIDENCE
    new_evidence_refs: Optional[List[str]] = Field(default_factory=list)
    destination_phase_refs: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CompletionReopenRecord(BaseModel):
    """Record of a workflow reopening event."""

    model_config = ConfigDict(extra="ignore")

    reopen_id: str = Field(default_factory=lambda: f"reopen-{uuid.uuid4().hex[:12]}")
    completion_id: str
    previous_state: str
    reopened_by: str
    reopened_by_role: str
    reason: str
    reopen_trigger: str
    reopened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    preserved_closure_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReassessCompletionWorkflowRequest(BaseModel):
    """Request payload to request reassessment of completion context."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    changed_context_summary: str
    target_authoritative_phase: str = "PHASE_62_REASSESSMENT"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReconcileCompletionWorkflowRequest(BaseModel):
    """Request payload to trigger on-demand reconciliation of updated outcomes/follow-ups."""

    model_config = ConfigDict(extra="ignore")

    force_refresh: bool = False
    correlation_id: Optional[str] = None

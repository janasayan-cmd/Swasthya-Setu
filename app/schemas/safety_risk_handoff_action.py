"""Phase 64: Clinical Safety Risk Handoff Action Schemas.

Defines request schemas for submitting, reconciling, retrying, cancelling,
and escalating handoffs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SubmitHandoffRequest(BaseModel):
    """Request to submit a pending handoff to its destination adapter."""

    model_config = ConfigDict(extra="ignore")

    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReconcileHandoffRequest(BaseModel):
    """Request to perform or re-evaluate outcome reconciliation."""

    model_config = ConfigDict(extra="ignore")

    reason: Optional[str] = "Routine operational reconciliation check"
    idempotency_key: Optional[str] = None


class RetryHandoffRequest(BaseModel):
    """Request to schedule a bounded retry for an interrupted or failed handoff."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    idempotency_key: Optional[str] = None


class CancelHandoffRequest(BaseModel):
    """Request to cancel a handoff where supported by the destination contract."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    idempotency_key: Optional[str] = None


class EscalateHandoffRequest(BaseModel):
    """Request to escalate an unresolved operational handoff to governance review."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    severity: Optional[str] = "HIGH"
    idempotency_key: Optional[str] = None

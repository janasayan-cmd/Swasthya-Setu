"""Phase 51: Safety Change Approval & Explicit Risk Acceptance Schemas.

Defines schemas for authorized approval binding, explicit risk acceptance,
stale-approval detection, and separation of duties enforcement.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_governance import (
    RiskImpact,
    RiskLikelihood,
    RiskSeverity,
    RolloutScopeType,
)


class RiskAcceptanceRequest(BaseModel):
    """Request by an authorized safety authority to accept residual risk."""

    model_config = ConfigDict(extra="ignore")

    residual_risk_severity: RiskSeverity
    residual_risk_likelihood: RiskLikelihood
    residual_risk_impact: RiskImpact
    acceptance_scope: str = Field(min_length=3)
    reason: str = Field(min_length=10)
    evidence_summary: str = Field(min_length=5)
    expires_in_days: Optional[int] = Field(default=90, ge=1, le=365)
    expected_risk_version: Optional[int] = None
    idempotency_key: Optional[str] = None


class RiskAcceptanceRecord(BaseModel):
    """Authoritative record of an explicit risk acceptance."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"acc-{uuid.uuid4().hex[:12]}")
    risk_id: str
    bound_risk_version: int
    residual_risk_severity: RiskSeverity
    residual_risk_likelihood: RiskLikelihood
    residual_risk_impact: RiskImpact
    acceptance_scope: str
    reason: str
    evidence_summary: str
    authority_id: str
    authority_role: str
    is_temporary: bool = True
    expires_at: Optional[datetime] = None
    is_expired: bool = False
    accepted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyChangeApprovalRequest(BaseModel):
    """Request to formally approve, reject, or defer a safety change."""

    model_config = ConfigDict(extra="ignore")

    decision: str = Field(description="'APPROVE', 'REJECT', or 'DEFER'")
    approval_scope: RolloutScopeType = Field(default=RolloutScopeType.INTERNAL)
    scope_details: Dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(min_length=5)
    bound_risk_version: int
    bound_change_version: int
    bound_evidence_hash: Optional[str] = None
    idempotency_key: Optional[str] = None


class SafetyChangeApprovalRecord(BaseModel):
    """Authoritative record of an explicit safety change approval."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:12]}")
    change_id: str
    decision: str
    approver_id: str
    approver_role: str
    bound_risk_version: int
    bound_change_version: int
    bound_evidence_hash: Optional[str] = None
    approval_scope: RolloutScopeType
    scope_details: Dict[str, Any] = Field(default_factory=dict)
    notes: str
    is_stale: bool = False
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

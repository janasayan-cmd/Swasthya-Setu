"""Phase 88: Recovery Execution Monitoring and Outcome Reconciliation Schemas.

Defines schemas for tracking operational recovery execution progress, reporting strategy deviations,
and verifying capability restoration evidence (integrating with Phase 73 and Phase 80).
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    ExecutionTrackingStatus,
)


class ExecutionMilestoneProgress(BaseModel):
    milestone_id: str
    milestone_name: str
    target_timestamp: Optional[datetime] = None
    completed_timestamp: Optional[datetime] = None
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, DELAYED, BLOCKED
    notes: Optional[str] = None


class RecoveryExecutionTrackingRecord(BaseModel):
    execution_id: str
    tenant_id: str
    handoff_id: str
    strategy_id: str
    status: ExecutionTrackingStatus = ExecutionTrackingStatus.PLANNED
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    milestones: List[ExecutionMilestoneProgress] = Field(default_factory=list)
    reported_deviations: List[str] = Field(default_factory=list)
    blocked_activities: List[str] = Field(default_factory=list)
    capability_restoration_evidence_ref: Optional[str] = None
    restoration_verified_by: Optional[str] = None
    restoration_verified_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class UpdateExecutionProgressRequest(BaseModel):
    progress_pct: float = Field(ge=0.0, le=100.0)
    notes: Optional[str] = None


class ReportExecutionDeviationRequest(BaseModel):
    deviation_description: str
    root_cause_explanation: str
    compensating_safeguards: Optional[str] = None


class SubmitRestorationVerificationRequest(BaseModel):
    restoration_evidence_ref: str
    verification_notes: str

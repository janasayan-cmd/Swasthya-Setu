"""Phase 80: Governance Recovery Coordination and Verification Schemas.

Defines schemas and models for:
- Tracking capability restoration progress
- Distinguishing technical restoration from operational restoration
- Independent verification and sign-off (separation of duties)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class RecoveryStatus(str, Enum):
    """Restoration lifecycle state of a governance capability."""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PARTIALLY_RESTORED = "PARTIALLY_RESTORED"
    TECHNICALLY_RESTORED = "TECHNICALLY_RESTORED"
    OPERATIONALLY_RESTORED = "OPERATIONALLY_RESTORED"
    VERIFIED = "VERIFIED"
    RESTRICTED_OPERATION = "RESTRICTED_OPERATION"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    CLOSED = "CLOSED"


class GovernanceRecoveryRecord(BaseModel):
    """Authoritative record monitoring recovery and verified restoration of governance operations."""
    model_config = ConfigDict(extra="forbid")

    recovery_id: str
    tenant_id: str
    disruption_id: str
    capability_id: str
    pre_disruption_operating_state: str
    recovery_start_time: str
    recovery_milestones: List[Dict[str, Any]] = Field(default_factory=list)
    recovery_status: RecoveryStatus
    evidence_of_restored_functionality: str = ""
    responsible_verifier_id: Optional[str] = None
    verification_timestamp: Optional[str] = None
    verification_notes: Optional[str] = None
    outstanding_limitations: str = ""
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateRecoveryRecordRequest(BaseModel):
    """Request to initialize recovery monitoring for an affected capability."""
    model_config = ConfigDict(extra="forbid")

    disruption_id: str
    capability_id: str
    pre_disruption_operating_state: str = "Active 24x7 Triage Operations"
    initial_milestone: Optional[str] = "Primary database connectivity restored"


class UpdateRecoveryStatusRequest(BaseModel):
    """Request to update capability recovery status and record progress milestone."""
    model_config = ConfigDict(extra="forbid")

    recovery_status: RecoveryStatus
    milestone_description: str
    evidence_notes: Optional[str] = None
    outstanding_limitations: Optional[str] = None


class VerifyRecoveryRestorationRequest(BaseModel):
    """Request to independently verify operational restoration (enforces separation of duties)."""
    model_config = ConfigDict(extra="forbid")

    verification_evidence_reference: str
    verification_notes: str
    outstanding_limitations: Optional[str] = ""

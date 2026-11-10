"""Phase 66: Clinical Safety Post-Closure Verification Schemas.

Defines schemas for post-closure integrity verification, verification run lifecycles,
and verification result evaluations.

Mandatory Safety Invariants:
1. Phase 65 closure does not mean that clinical risk has been eliminated.
2. A valid historical closure does not guarantee that the workflow remains valid indefinitely.
3. Post-closure verification does not independently certify clinical safety.
4. A change in an authoritative source does not automatically authorize reopening or modifying that source.
5. A detected discrepancy does not establish that a clinical error occurred.
6. A missing response from a dependency does not establish that the underlying workflow failed or succeeded.
7. A successful reconciliation does not replace clinical review, risk acceptance, assurance, or effectiveness evaluation.
8. A system-generated recommendation does not constitute an authorized governance decision.
9. A historical closure must remain auditable even when its current status becomes stale, conflicted, or reopened.
10. Phase 66 must never silently rewrite a previous closure decision to make it appear that the original decision never occurred.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class VerificationLifecycleState(str, Enum):
    """Lifecycle states for Phase 66 post-closure verification runs."""

    NOT_SCHEDULED = "NOT_SCHEDULED"
    SCHEDULED = "SCHEDULED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_LIMITATIONS = "VERIFIED_WITH_LIMITATIONS"
    CHANGE_DETECTED = "CHANGE_DETECTED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    REOPEN_RECOMMENDED = "REOPEN_RECOMMENDED"
    REOPEN_AUTHORIZATION_PENDING = "REOPEN_AUTHORIZATION_PENDING"
    REOPENED = "REOPENED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class TriggerPostClosureVerificationRequest(BaseModel):
    """Request payload to trigger a post-closure verification run."""

    model_config = ConfigDict(extra="ignore")

    policy_version: Optional[str] = "v1.0.0"
    reverification_reason: Optional[str] = "Governed periodic integrity verification"
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    force_deep_check: bool = False
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class VerificationRetryRequest(BaseModel):
    """Request payload to retry a failed or incomplete verification run."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PostClosureVerificationRecord(BaseModel):
    """Domain model representing an authoritative post-closure verification execution run."""

    model_config = ConfigDict(extra="ignore")

    verification_id: str = Field(default_factory=lambda: f"verif-{uuid.uuid4().hex[:12]}")
    completion_id: str
    organization_id: str
    facility_id: str
    state: VerificationLifecycleState = VerificationLifecycleState.PENDING

    # Historical and current context
    historical_completion_state: str = "CLOSED"
    current_coordination_state: str = "CLOSED"

    # Evaluation outcomes
    reassessment_required: bool = False
    reopen_recommended: bool = False
    reopen_authorized: bool = False
    reopened: bool = False

    # Policy and checks
    policy_version: str = "v1.0.0"
    findings_count: int = 0
    material_findings_count: int = 0
    limitations: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    evaluated_checks: Dict[str, Any] = Field(default_factory=dict)
    evidence_references: List[str] = Field(default_factory=list)

    # Retry and execution tracking
    retry_count: int = 0
    max_retries: int = 3
    idempotency_key: Optional[str] = None
    correlation_id: str = Field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}")
    triggered_by: str = "system"
    triggered_by_role: str = "SYSTEM"

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    # Audit history
    history: List[Dict[str, Any]] = Field(default_factory=list)
    version: int = 1

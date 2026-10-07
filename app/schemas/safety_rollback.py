"""Phase 51: Safety Change Implementation & Rollback Schemas.

Defines schemas for governed implementation gating, controlled execution,
and safe rollback without history deletion or audit erasure.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_governance import RolloutScopeType


class SafetyChangeImplementationRequest(BaseModel):
    """Request to execute an approved safety change through authoritative subsystems."""

    model_config = ConfigDict(extra="ignore")

    execution_notes: Optional[str] = None
    override_scope: Optional[RolloutScopeType] = None
    expected_change_version: Optional[int] = None
    idempotency_key: Optional[str] = None


class SafetyChangeImplementationRecord(BaseModel):
    """Authoritative record of a safety change implementation execution."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"impl-{uuid.uuid4().hex[:12]}")
    change_id: str
    implemented_version: str
    implementer_id: str
    implementer_role: str
    subsystem_response: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    implemented_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyChangeRollbackRequest(BaseModel):
    """Request to rollback a safety change to a previous verified state."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=5)
    rollback_scope: RolloutScopeType = Field(default=RolloutScopeType.INTERNAL)
    target_reversion_version: str = Field(description="Target configuration or policy version to restore")
    notes: Optional[str] = None
    expected_change_version: Optional[int] = None
    idempotency_key: Optional[str] = None


class SafetyChangeRollbackRecord(BaseModel):
    """Authoritative record of an executed safety rollback."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"rbk-{uuid.uuid4().hex[:12]}")
    change_id: str
    reason: str
    rollback_scope: RolloutScopeType
    target_reversion_version: str
    rolled_back_by_id: str
    rolled_back_by_role: str
    history_preserved: bool = Field(default=True, description="Guarantees audit and change history was preserved")
    subsystem_response: Dict[str, Any] = Field(default_factory=dict)
    rolled_back_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

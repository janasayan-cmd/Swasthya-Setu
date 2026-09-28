"""Idempotency records and schemas (Phase 22).

Enforces:
- Deterministic duplicate detection.
- Safe replay of identical operations.
- Prevention of concurrent race-condition execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class IdempotencyState(str, Enum):
    """Execution status of an idempotent operation."""

    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IdempotencyRecord(BaseModel):
    """Persisted idempotency key and execution outcome."""

    model_config = ConfigDict(from_attributes=True)

    key: str = Field(description="Deterministic hashed or supplied idempotency key")
    operation_type: str = Field(description="Operation discriminator")
    resource_id: str = Field(description="Associated resource identifier")
    state: IdempotencyState = Field(default=IdempotencyState.PROCESSING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    result_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

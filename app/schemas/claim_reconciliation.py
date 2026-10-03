"""Phase 33 — Claim Reconciliation Schemas.

CRITICAL INVARIANTS:
- RECONCILIATION MUST DETECT MISMATCHES WITHOUT BLIND OVERWRITES.
- UNKNOWN EXTERNAL STATUS REQUIRES EXPLICIT RECONCILIATION.
- DISCREPANCIES MUST BE AUDITABLE.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.claim import ClaimStatus


class ClaimReconciliationStatus(str, Enum):
    """Reconciliation state between HealthSetu ledger and payer state."""
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


class ClaimDiscrepancyType(str, Enum):
    """Categorized discrepancy types discovered during reconciliation."""
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    MISSING_EXTERNAL_RECORD = "MISSING_EXTERNAL_RECORD"
    MISSING_INTERNAL_RECORD = "MISSING_INTERNAL_RECORD"
    ITEM_MISMATCH = "ITEM_MISMATCH"
    AUTHORIZATION_MISMATCH = "AUTHORIZATION_MISMATCH"
    PAYMENT_MISMATCH = "PAYMENT_MISMATCH"
    STALE_CLAIM = "STALE_CLAIM"


class ClaimReconciliationResponse(BaseModel):
    """Claim reconciliation record view."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    claim_number: str
    status: ClaimReconciliationStatus
    discrepancy_type: Optional[ClaimDiscrepancyType] = None
    internal_amount_in_minor_units: int
    external_amount_in_minor_units: Optional[int] = None
    internal_status: ClaimStatus
    external_status: Optional[str] = None
    details: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime


class ClaimReconciliationRecord(BaseModel):
    """Internal database and audit model for claim reconciliation findings."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    claim_number: str
    status: ClaimReconciliationStatus = ClaimReconciliationStatus.PENDING
    discrepancy_type: Optional[ClaimDiscrepancyType] = None
    internal_amount_in_minor_units: int
    external_amount_in_minor_units: Optional[int] = None
    internal_status: ClaimStatus
    external_status: Optional[str] = None
    details: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_response(self) -> ClaimReconciliationResponse:
        return ClaimReconciliationResponse(
            id=self.id,
            claim_id=self.claim_id,
            claim_number=self.claim_number,
            status=self.status,
            discrepancy_type=self.discrepancy_type,
            internal_amount_in_minor_units=self.internal_amount_in_minor_units,
            external_amount_in_minor_units=self.external_amount_in_minor_units,
            internal_status=self.internal_status,
            external_status=self.external_status,
            details=self.details,
            resolved_at=self.resolved_at,
            resolved_by=self.resolved_by,
            created_at=self.created_at,
        )

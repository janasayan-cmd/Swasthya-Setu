"""Financial Reconciliation schemas for Phase 32 — Billing, Payments & Financial Transaction Management.

CRITICAL INVARIANTS:
- Never silently overwrite financial records.
- Compare: amount, currency, status, provider reference, timestamps.
- Flag discrepancies for audit and controlled administrative resolution.
- FINANCIAL RECONCILIATION ≠ CLINICAL RECORD RECONCILIATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FinancialReconciliationStatus(str, Enum):
    """Status of financial reconciliation."""
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


class FinancialDiscrepancyType(str, Enum):
    """Types of financial discrepancies discovered during reconciliation."""
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    MISSING_IN_PROVIDER = "MISSING_IN_PROVIDER"
    MISSING_IN_SYSTEM = "MISSING_IN_SYSTEM"
    DUPLICATE_PROVIDER_TRANSACTION = "DUPLICATE_PROVIDER_TRANSACTION"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


class FinancialReconciliationRecord(BaseModel):
    """Authoritative record of a single transaction reconciliation event."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:12]}")
    payment_id: str
    provider_transaction_id: Optional[str] = None
    status: FinancialReconciliationStatus = Field(default=FinancialReconciliationStatus.PENDING)
    discrepancy_type: Optional[FinancialDiscrepancyType] = None
    system_amount_in_minor_units: int
    provider_amount_in_minor_units: Optional[int] = None
    system_currency: str = "INR"
    provider_currency: Optional[str] = None
    system_status: str
    provider_status: Optional[str] = None
    resolution_notes: Optional[str] = None
    reconciled_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FinancialReconciliationReport(BaseModel):
    """Aggregated reconciliation batch report."""
    total_checked: int = 0
    matched: int = 0
    mismatched: int = 0
    unknown: int = 0
    resolved: int = 0
    records: List[FinancialReconciliationRecord] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

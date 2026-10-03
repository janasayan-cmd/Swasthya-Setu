"""Pydantic schemas for Diagnostic Reconciliation & Integrity (Phase 34 & Phase 26).

SAFETY & ARCHITECTURAL INVARIANTS:
- DATA QUALITY FINDING != CLINICAL DIAGNOSIS
- RECONCILIATION DISCREPANCY != AUTOMATIC RESULT MERGE
- NEVER AUTOMATICALLY MERGE CONFLICTING CLINICAL RESULTS
- CLINICAL SAFETY PRECEDES DATA HARMONIZATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReconciliationStatus(str, Enum):
    """Integrity evaluation outcome."""

    CLEAN = "CLEAN"
    DISCREPANCY_DETECTED = "DISCREPANCY_DETECTED"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class DiscrepancyType(str, Enum):
    """Categorization of diagnostic integrity discrepancies."""

    DUPLICATE_RESULT = "DUPLICATE_RESULT"
    CONFLICTING_RESULT = "CONFLICTING_RESULT"
    CORRECTED_RESULT = "CORRECTED_RESULT"
    STALE_RESULT = "STALE_RESULT"
    MISSING_RESULT = "MISSING_RESULT"
    PATIENT_MISMATCH = "PATIENT_MISMATCH"
    ORDER_MISMATCH = "ORDER_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    PROVIDER_MISMATCH = "PROVIDER_MISMATCH"
    REFERENCE_RANGE_MISMATCH = "REFERENCE_RANGE_MISMATCH"
    MISSING_PROVENANCE = "MISSING_PROVENANCE"
    MISSING_UNIT = "MISSING_UNIT"
    INVALID_VALUE = "INVALID_VALUE"


class DiscrepancySeverity(str, Enum):
    """Severity of reconciliation discrepancy."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ReconciliationFinding(BaseModel):
    """Specific discrepancy detected during integrity verification."""

    finding_id: str
    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity
    description: str
    affected_order_id: Optional[str] = None
    affected_result_id: Optional[str] = None
    affected_patient_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReconciliationSummary(BaseModel):
    """Aggregate report from a diagnostic reconciliation audit run."""

    model_config = ConfigDict(populate_by_name=True)

    reconciliation_id: str
    order_id: Optional[str] = None
    patient_id: Optional[str] = None
    status: ReconciliationStatus
    total_checked: int = Field(ge=0)
    clean_count: int = Field(ge=0)
    discrepancy_count: int = Field(ge=0)
    findings: List[ReconciliationFinding] = Field(default_factory=list)
    reconciled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

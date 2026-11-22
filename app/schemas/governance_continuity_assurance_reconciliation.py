"""Phase 81: Decision and Evidence Reconciliation Assurance Schemas.

Validates the integrity of records reconciled after continuity activation,
ensuring provenance preservation, conflict routing, and audit trail completeness.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class ReconciliationIntegrityStatus(str, Enum):
    VERIFIED_INTEGRAL = "VERIFIED_INTEGRAL"
    RECONCILIATION_DELAYED = "RECONCILIATION_DELAYED"
    UNRESOLVED_CONFLICT_DETECTED = "UNRESOLVED_CONFLICT_DETECTED"
    MISSING_AUTHORITY_EVIDENCE = "MISSING_AUTHORITY_EVIDENCE"
    INCOMPLETE_AUDIT_TRAIL = "INCOMPLETE_AUDIT_TRAIL"
    UNVERIFIED_TEMPORARY_RECORDS = "UNVERIFIED_TEMPORARY_RECORDS"


class AssessReconciliationIntegrityRequest(BaseModel):
    reconciliation_batch_id: str
    activation_id: str
    total_temporary_decisions_recorded: int
    total_decisions_reconciled: int
    unresolved_conflict_ids: List[str] = Field(default_factory=list)
    has_full_provenance: bool = True
    receiving_workflow_references: List[str] = Field(default_factory=list)  # Phase 72, 63, 54, 49
    notes: Optional[str] = None


class ReconciliationAssuranceRecord(BaseModel):
    assurance_id: str
    reconciliation_batch_id: str
    activation_id: str
    total_temporary_decisions: int
    total_reconciled: int
    unresolved_conflicts_count: int = 0
    unresolved_conflict_ids: List[str] = Field(default_factory=list)
    integrity_status: ReconciliationIntegrityStatus = ReconciliationIntegrityStatus.VERIFIED_INTEGRAL
    has_full_provenance: bool = True
    receiving_workflow_references: List[str] = Field(default_factory=list)
    findings_generated: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None
    evaluated_by: str
    evaluated_at: datetime
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER

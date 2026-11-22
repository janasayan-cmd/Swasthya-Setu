"""Phase 80: Decision and Evidence Continuity & Reconciliation Schemas.

Defines schemas and models for:
- Tracking decisions made during disruptions
- Controlled, audited reconciliation into authoritative workflows (Phase 72, 63, 54, 49)
- Conflict detection and preservation of original provenance
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ReconciliationStatus(str, Enum):
    """Reconciliation state of temporary governance decisions and evidence."""
    PENDING = "PENDING"
    UNDER_RECONCILIATION = "UNDER_RECONCILIATION"
    RECONCILED = "RECONCILED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    REJECTED = "REJECTED"


class TemporaryGovernanceDecisionRecord(BaseModel):
    """Authoritative record for a governance decision executed under continuity arrangements."""
    model_config = ConfigDict(extra="forbid")

    temporary_decision_id: str
    tenant_id: str
    activation_id: str
    decision_title: str
    decision_summary: str
    decision_authority_role: str
    authorized_decision_maker_id: str
    delegation_reference: Optional[str] = None
    decision_timestamp: str
    supporting_evidence_references: List[str] = Field(default_factory=list)
    temporary_documentation_reference: str
    reconciliation_status: ReconciliationStatus
    reconciliation_timestamp: Optional[str] = None
    receiving_authoritative_record_id: Optional[str] = Field(None, description="Receiving Phase 72/63/54/49 reference")
    reconciled_by: Optional[str] = None
    conflict_description: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class RecordTemporaryDecisionRequest(BaseModel):
    """Request to capture a decision made under continuity arrangements."""
    model_config = ConfigDict(extra="forbid")

    activation_id: str
    decision_title: str
    decision_summary: str
    decision_authority_role: str
    authorized_decision_maker_id: str
    delegation_reference: Optional[str] = None
    decision_timestamp: str
    supporting_evidence_references: Optional[List[str]] = None
    temporary_documentation_reference: str


class SubmitReconciliationRequest(BaseModel):
    """Request to reconcile temporary decision into authoritative system."""
    model_config = ConfigDict(extra="forbid")

    receiving_authoritative_record_id: str
    reconciliation_notes: Optional[str] = None


class ReviewReconciliationConflictRequest(BaseModel):
    """Request to review and disposition a reconciliation conflict."""
    model_config = ConfigDict(extra="forbid")

    resolution_disposition: ReconciliationStatus = Field(..., description="RECONCILED or REJECTED")
    conflict_resolution_notes: str
    receiving_authoritative_record_id: Optional[str] = None

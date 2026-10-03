"""Phase 33 — Payer Claim Adjudication & Response Schemas.

CRITICAL INVARIANTS:
- PAYER RESPONSE ≠ CLINICAL TRUTH.
- NEVER BLINDLY MAP UNFAMILIAR STATUS TO APPROVED.
- UNKNOWN STATUS MUST BE RECONCILED.
- SEPARATE PAYER REIMBURSEMENT FROM PATIENT RESPONSIBILITY.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.claim import ClaimStatus


class ClaimItemAdjudication(BaseModel):
    """Payer line item adjudication result."""
    model_config = ConfigDict(from_attributes=True)

    item_id: Optional[str] = None
    service_code: Optional[str] = None
    charged_amount_in_minor_units: int
    allowed_amount_in_minor_units: int
    paid_amount_in_minor_units: int
    patient_responsibility_in_minor_units: int = 0
    denial_code: Optional[str] = None
    denial_reason: Optional[str] = None


class PayerClaimAdjudication(BaseModel):
    """Normalized response parsed from external payer adjudication."""
    model_config = ConfigDict(from_attributes=True)

    provider_claim_reference: str
    status: ClaimStatus
    approved_amount_in_minor_units: int = 0
    payer_paid_amount_in_minor_units: int = 0
    patient_responsibility_in_minor_units: int = 0
    deductible_in_minor_units: int = 0
    copay_in_minor_units: int = 0
    coinsurance_in_minor_units: int = 0
    denial_reason: Optional[str] = None
    denial_code: Optional[str] = None
    item_adjudications: List[ClaimItemAdjudication] = Field(default_factory=list)
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    response_timestamp: datetime = Field(default_factory=datetime.utcnow)


class ClaimResponseRecord(BaseModel):
    """Internal model for persisted claim response / EOB / remittance advice."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    provider_claim_reference: str
    adjudication: PayerClaimAdjudication
    created_at: datetime = Field(default_factory=datetime.utcnow)

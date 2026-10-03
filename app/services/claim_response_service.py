"""Payer Claim Adjudication & Response Service (Phase 33).

Parses authoritative Remittance Advice (ERA) / Explanation of Benefits (EOB) from payers.
CRITICAL INVARIANTS:
- PAYER RESPONSE ≠ CLINICAL TRUTH.
- NEVER BLINDLY MAP UNFAMILIAR STATUS TO APPROVED.
- SEPARATE PAYER REIMBURSEMENT FROM PATIENT RESPONSIBILITY.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    ClaimInvalidStateException,
    ClaimNotFoundException,
)
from app.repositories.claim_repository import ClaimRepository
from app.schemas.claim import ClaimResponse, ClaimStatus
from app.schemas.claim_response import PayerClaimAdjudication
from app.services.insurance_validation_service import InsuranceValidationService

logger = logging.getLogger(__name__)


class ClaimResponseService:
    """Service processing external payer adjudication decisions."""

    def __init__(self, claim_repo: Optional[ClaimRepository] = None) -> None:
        self.claim_repo = claim_repo or ClaimRepository()

    def process_adjudication(
        self,
        claim_id: str,
        adjudication: PayerClaimAdjudication,
    ) -> ClaimResponse:
        """Apply adjudicated decision and line-item breakdowns to internal claim."""
        claim = self.claim_repo.get(claim_id)
        if not claim:
            raise ClaimNotFoundException(f"Claim {claim_id} not found.")

        # Validate lifecycle transition
        InsuranceValidationService.validate_claim_transition(claim.status, adjudication.status)

        claim.status = adjudication.status
        claim.approved_amount_in_minor_units = adjudication.approved_amount_in_minor_units
        claim.payer_paid_amount_in_minor_units = adjudication.payer_paid_amount_in_minor_units
        claim.patient_responsibility_in_minor_units = adjudication.patient_responsibility_in_minor_units
        claim.denial_reason = adjudication.denial_reason
        claim.denial_code = adjudication.denial_code
        claim.adjudication_timestamp = datetime.now(timezone.utc)
        claim.raw_response = adjudication.raw_response

        # Map line item adjudications if provided
        if adjudication.item_adjudications:
            item_map = {adj.item_id: adj for adj in adjudication.item_adjudications if adj.item_id}
            for item in claim.items:
                if item.id in item_map:
                    adj = item_map[item.id]
                    item.approved_amount_in_minor_units = adj.allowed_amount_in_minor_units
                    item.patient_responsibility_in_minor_units = adj.patient_responsibility_in_minor_units
                    item.denial_reason = adj.denial_reason

        updated = self.claim_repo.update(claim)
        logger.info(
            f"Adjudicated claim {updated.claim_number}: status={updated.status.value}, "
            f"payer_paid={updated.payer_paid_amount_in_minor_units}, patient_resp={updated.patient_responsibility_in_minor_units}"
        )
        return updated.to_response()

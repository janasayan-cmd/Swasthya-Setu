"""Claim Reconciliation Service (Phase 33).

Detects and records discrepancies between HealthSetu financial ledgers and external payer clearinghouse state.
CRITICAL INVARIANTS:
- RECONCILIATION DETECTS MISMATCHES WITHOUT BLIND OVERWRITES.
- DISCREPANCIES MUST BE AUDITABLE.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    ClaimDisabledException,
    ClaimNotFoundException,
)
from app.integrations.payers.base import PayerProvider
from app.integrations.payers.providers.mock import MockPayerProvider
from app.repositories.claim_reconciliation_repository import ClaimReconciliationRepository
from app.repositories.claim_repository import ClaimRepository
from app.schemas.claim import ClaimStatus
from app.schemas.claim_reconciliation import (
    ClaimDiscrepancyType,
    ClaimReconciliationRecord,
    ClaimReconciliationResponse,
    ClaimReconciliationStatus,
)

logger = logging.getLogger(__name__)


class ClaimReconciliationService:
    """Service auditing and reconciling internal claims against external payer state."""

    def __init__(
        self,
        claim_repo: Optional[ClaimRepository] = None,
        rec_repo: Optional[ClaimReconciliationRepository] = None,
        provider: Optional[PayerProvider] = None,
    ) -> None:
        self.claim_repo = claim_repo or ClaimRepository()
        self.rec_repo = rec_repo or ClaimReconciliationRepository()
        self.provider = provider or MockPayerProvider()

    def _ensure_enabled(self) -> None:
        if not settings.INSURANCE_ENABLED or not settings.CLAIM_RECONCILIATION_ENABLED:
            raise ClaimDisabledException("Claim reconciliation subsystem is disabled.")

    async def reconcile_claim(self, claim_id: str) -> ClaimReconciliationResponse:
        """Execute reconciliation comparison for a specific claim."""
        self._ensure_enabled()

        claim = self.claim_repo.get(claim_id)
        if not claim:
            raise ClaimNotFoundException(f"Claim {claim_id} not found.")

        rec_id = f"clm_rec_{uuid.uuid4().hex[:12]}"
        ref = claim.provider_claim_reference or ""

        if not ref:
            record = ClaimReconciliationRecord(
                id=rec_id,
                claim_id=claim.id,
                claim_number=claim.claim_number,
                status=ClaimReconciliationStatus.MISMATCHED,
                discrepancy_type=ClaimDiscrepancyType.MISSING_EXTERNAL_RECORD,
                internal_amount_in_minor_units=claim.total_amount_in_minor_units,
                internal_status=claim.status,
                details="Claim has no provider reference; never transmitted to payer",
            )
            saved = self.rec_repo.create(record)
            return saved.to_response()

        # Query provider reconciliation endpoint
        prov_res = await self.provider.reconcile_claim(ref, claim.total_amount_in_minor_units)

        if prov_res.external_status == "MISSING":
            status = ClaimReconciliationStatus.MISMATCHED
            discrepancy = ClaimDiscrepancyType.MISSING_EXTERNAL_RECORD
            details = f"Payer clearinghouse has no record of claim reference {ref}"
        elif not prov_res.matched:
            status = ClaimReconciliationStatus.MISMATCHED
            discrepancy = ClaimDiscrepancyType.AMOUNT_MISMATCH
            details = (
                f"Amount mismatch: internal={claim.total_amount_in_minor_units}, "
                f"external={prov_res.external_amount_in_minor_units}"
            )
        else:
            status = ClaimReconciliationStatus.MATCHED
            discrepancy = None
            details = "All amounts and clearinghouse states matched perfectly"

        record = ClaimReconciliationRecord(
            id=rec_id,
            claim_id=claim.id,
            claim_number=claim.claim_number,
            status=status,
            discrepancy_type=discrepancy,
            internal_amount_in_minor_units=claim.total_amount_in_minor_units,
            external_amount_in_minor_units=prov_res.external_amount_in_minor_units,
            internal_status=claim.status,
            external_status=prov_res.external_status,
            details=details,
        )

        saved = self.rec_repo.create(record)
        logger.info(
            f"Claim reconciliation finished: claim={claim.claim_number}, status={saved.status.value}, "
            f"discrepancy={saved.discrepancy_type}"
        )
        return saved.to_response()

    def list_reconciliation_records(
        self,
        status: Optional[ClaimReconciliationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[list[ClaimReconciliationResponse], int]:
        """List historical reconciliation records."""
        self._ensure_enabled()
        records, total = self.rec_repo.list_all(status=status, limit=limit, offset=offset)
        return [r.to_response() for r in records], total

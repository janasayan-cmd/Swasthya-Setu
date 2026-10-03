"""Asynchronous Background Insurance Tasks (Phase 33).

Executes background jobs for:
- Eligibility check execution
- Pre-authorization submission and status sync
- Claim submission and background reconciliation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def run_eligibility_check_task(
    coverage_id: str,
    service_type: Optional[str] = None,
    date_of_service: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute background eligibility inquiry."""
    from app.api.deps import get_eligibility_service
    from app.schemas.eligibility import EligibilityCheckRequest
    from app.schemas.user import AuthenticatedUserContext

    system_ctx = AuthenticatedUserContext(
        user_id="usr-system-worker",
        email="system-worker@healthsetu.org",
        role="SYSTEM_ADMIN",
    )
    svc = get_eligibility_service()
    req = EligibilityCheckRequest(
        coverage_id=coverage_id,
        service_type=service_type or "GENERAL",
        date_of_service=date_of_service,
    )
    res = await svc.verify_eligibility(system_ctx, req)
    return {"status": res.status.value, "check_id": res.id}


async def run_claim_submission_task(
    claim_id: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute background claim submission to external clearinghouse."""
    from app.api.deps import get_claim_service
    from app.schemas.claim import ClaimSubmitRequest
    from app.schemas.user import AuthenticatedUserContext

    system_ctx = AuthenticatedUserContext(
        user_id="usr-system-worker",
        email="system-worker@healthsetu.org",
        role="SYSTEM_ADMIN",
    )
    svc = get_claim_service()
    req = ClaimSubmitRequest(idempotency_key=idempotency_key)
    res = await svc.submit_claim(system_ctx, claim_id, req)
    return {
        "status": res.status.value,
        "claim_number": res.claim_number,
        "provider_reference": res.provider_claim_reference,
    }


async def run_claim_reconciliation_task(claim_id: str) -> Dict[str, Any]:
    """Execute periodic authoritative claim reconciliation."""
    from app.api.deps import get_claim_reconciliation_service

    svc = get_claim_reconciliation_service()
    res = await svc.reconcile_claim(claim_id)
    return {
        "status": res.status.value,
        "discrepancy": res.discrepancy_type.value if res.discrepancy_type else None,
    }

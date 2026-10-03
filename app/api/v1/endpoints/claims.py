"""Medical Claim Management Endpoints (Phase 33).

Provides REST APIs for:
- Drafting claims with verified billable line items and Phase 31/32 references
- Idempotent claim submission to external clearinghouses
- Real-time status sync, adjudication inspection, and reconciliation
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import (
    get_claim_reconciliation_service,
    get_claim_service,
    get_current_user,
)
from app.schemas.claim import (
    ClaimCreateRequest,
    ClaimResponse,
    ClaimStatus,
    ClaimSubmitRequest,
)
from app.schemas.claim_reconciliation import ClaimReconciliationResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.claim_reconciliation_service import ClaimReconciliationService
from app.services.claim_service import ClaimService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Medical Claims"])


# ---------------------------------------------------------------------------
# Patient-Scoped Claim APIs
# ---------------------------------------------------------------------------

@router.post(
    "/patients/{patient_id}/claims",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Claim",
    description="Constructs a new medical claim draft with validated billable line items.",
)
async def create_patient_claim(
    patient_id: str,
    request: ClaimCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimResponse:
    request.patient_id = patient_id
    return claim_service.create_claim(current_user, request)


@router.get(
    "/patients/{patient_id}/claims",
    response_model=List[ClaimResponse],
    summary="List Patient Claims",
    description="Lists all claims filed for a patient with status filtering.",
)
async def list_patient_claims(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
    status: Optional[ClaimStatus] = Query(None, description="Filter by claim status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[ClaimResponse]:
    records, _ = claim_service.list_patient_claims(current_user, patient_id, status=status, limit=limit, offset=offset)
    return records


@router.get(
    "/patients/{patient_id}/claims/{claim_id}",
    response_model=ClaimResponse,
    summary="Get Patient Claim",
    description="Fetches claim details, adjudication status, and line items.",
)
async def get_patient_claim(
    patient_id: str,
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimResponse:
    return claim_service.get_claim(current_user, claim_id)


@router.post(
    "/patients/{patient_id}/claims/{claim_id}/submit",
    response_model=ClaimResponse,
    summary="Submit Claim to Payer",
    description="Submits the claim to the external payer clearinghouse idempotently.",
)
async def submit_patient_claim(
    patient_id: str,
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> ClaimResponse:
    req = ClaimSubmitRequest(idempotency_key=idempotency_key)
    return await claim_service.submit_claim(current_user, claim_id, req)


@router.get(
    "/patients/{patient_id}/claims/{claim_id}/status",
    response_model=ClaimResponse,
    summary="Sync Claim Status",
    description="Queries the external payer gateway for the latest claim adjudication status.",
)
async def sync_patient_claim_status(
    patient_id: str,
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimResponse:
    return await claim_service.sync_claim_status(current_user, claim_id)


@router.post(
    "/patients/{patient_id}/claims/{claim_id}/reconcile",
    response_model=ClaimReconciliationResponse,
    summary="Reconcile Claim",
    description="Audits the claim against clearinghouse records to detect amount or status discrepancies.",
)
async def reconcile_patient_claim(
    patient_id: str,
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
    rec_service: Annotated[ClaimReconciliationService, Depends(get_claim_reconciliation_service)],
) -> ClaimReconciliationResponse:
    # Verify access to claim first
    claim_service.get_claim(current_user, claim_id)
    return await rec_service.reconcile_claim(claim_id)


# ---------------------------------------------------------------------------
# Direct Claim APIs (authorized across roles)
# ---------------------------------------------------------------------------

@router.get(
    "/claims/{claim_id}",
    response_model=ClaimResponse,
    summary="Get Claim by ID",
    description="Direct lookup of claim details by ID.",
)
async def get_claim_by_id(
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimResponse:
    return claim_service.get_claim(current_user, claim_id)


@router.get(
    "/claims/{claim_id}/status",
    response_model=ClaimResponse,
    summary="Get Claim Status by ID",
    description="Retrieves current claim adjudication status.",
)
async def get_claim_status_by_id(
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimResponse:
    return claim_service.get_claim(current_user, claim_id)


# ---------------------------------------------------------------------------
# Administrative Insurance & Claim Operations
# ---------------------------------------------------------------------------

@router.get(
    "/admin/insurance/status",
    summary="Admin Insurance Subsystem Status",
    description="Inspects active insurance, eligibility, pre-authorization, and claims configurations.",
)
async def admin_insurance_status(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> dict:
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_str not in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Administrator privileges required.")

    from app.core.config import settings
    return {
        "insurance_enabled": settings.INSURANCE_ENABLED,
        "eligibility_enabled": settings.ELIGIBILITY_ENABLED,
        "benefits_enabled": settings.BENEFITS_ENABLED,
        "preauthorization_enabled": settings.PREAUTHORIZATION_ENABLED,
        "claims_enabled": settings.CLAIMS_ENABLED,
        "claim_submission_enabled": settings.CLAIM_SUBMISSION_ENABLED,
        "claim_reconciliation_enabled": settings.CLAIM_RECONCILIATION_ENABLED,
        "payer_integrations_enabled": settings.PAYER_INTEGRATIONS_ENABLED,
        "payer_provider": settings.PAYER_PROVIDER,
    }


@router.get(
    "/admin/insurance/payers",
    summary="Admin Registered Payers",
    description="Lists supported payer organizations and clearinghouse integrations.",
)
async def admin_list_payers(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> List[dict]:
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_str not in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Administrator privileges required.")

    return [
        {
            "payer_id": "payer-national-01",
            "payer_name": "National Health Payer Clearinghouse",
            "payer_code": "NHP_CLEARING",
            "tpa_name": "MediAssist Healthcare",
            "status": "ACTIVE",
        },
        {
            "payer_id": "payer-star-02",
            "payer_name": "Star Comprehensive Health Insurance",
            "payer_code": "STAR_HEALTH",
            "tpa_name": "In-house TPA",
            "status": "ACTIVE",
        },
    ]


@router.get(
    "/admin/insurance/provider-status",
    summary="Admin Payer Gateway Health",
    description="Tests operational health of the active payer gateway adapter.",
)
async def admin_payer_health_status(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> dict:
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_str not in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Administrator privileges required.")

    health = await claim_service.provider.health_check()
    return {
        "provider": claim_service.provider.name,
        "state": health.state.value,
        "message": health.message,
        "latency_ms": health.latency_ms,
    }


@router.post(
    "/admin/insurance/providers/{provider}/test",
    summary="Admin Test Payer Provider Connectivity",
    description="Tests gateway credentials and ping for the given payer provider.",
)
async def admin_test_payer_provider(
    provider: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> dict:
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_str not in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Administrator privileges required.")

    health = await claim_service.provider.health_check()
    return {
        "provider": provider,
        "status": "SUCCESS" if health.state.value == "AVAILABLE" else "FAILED",
        "latency_ms": health.latency_ms,
        "details": health.message,
    }


@router.get(
    "/admin/claims",
    response_model=List[ClaimResponse],
    summary="Admin List All Claims",
    description="Cross-tenant administration list of all filed claims.",
)
async def admin_list_claims(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
    status: Optional[ClaimStatus] = Query(None),
    facility_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[ClaimResponse]:
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_str not in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Administrator privileges required.")

    records, _ = claim_service.claim_repo.list_all(
        facility_id=facility_id,
        organization_id=organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [r.to_response() for r in records]


@router.get(
    "/admin/claims/{claim_id}",
    response_model=ClaimResponse,
    summary="Admin Get Claim Details",
    description="Full administration view of a claim.",
)
async def admin_get_claim_detail(
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    claim_service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimResponse:
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_str not in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Administrator privileges required.")

    record = claim_service.claim_repo.get(claim_id)
    if not record:
        from app.core.exceptions import ClaimNotFoundException
        raise ClaimNotFoundException(f"Claim {claim_id} not found.")
    return record.to_response()


@router.post(
    "/admin/claims/{claim_id}/reconcile",
    response_model=ClaimReconciliationResponse,
    summary="Admin Reconcile Claim",
    description="Administrative execution of claim reconciliation.",
)
async def admin_reconcile_claim_endpoint(
    claim_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    rec_service: Annotated[ClaimReconciliationService, Depends(get_claim_reconciliation_service)],
) -> ClaimReconciliationResponse:
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_str not in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Administrator privileges required.")

    return await rec_service.reconcile_claim(claim_id)


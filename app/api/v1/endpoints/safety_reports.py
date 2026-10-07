"""Phase 53: Clinical Safety Assurance Reporting, Evidence Consolidation & Governed Safety Oversight APIs.

Endpoints:
  POST /safety-reports                      — Request report generation
  POST /safety-reports/{report_id}/generate — Execute report generation
  GET  /safety-reports                      — List safety reports
  GET  /safety-reports/{report_id}          — Get report details
  POST /safety-reports/{report_id}/review   — Submit human review
  POST /safety-reports/{report_id}/publish  — Publish safety report

Client trust boundary:
  - actor_id, reviewer_id, organization_id derived from authenticated session context.
  - Calculations and aggregations are fully deterministic and bound by evidence.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_report import (
    SafetyReportRecord,
    SafetyReportRequest,
    SafetyReportReviewSubmission,
    SafetyReportType,
    SafetyReportLifecycleState,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_report_service import safety_report_service
from app.services.safety_report_review_service import safety_report_review_service
from app.repositories.safety_report_repository import safety_report_repository

router = APIRouter(
    prefix="/safety-reports",
    tags=["Clinical Safety Assurance Reporting & Governed Safety Oversight"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


@router.post(
    "",
    response_model=StandardSuccessResponse[SafetyReportRecord],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request Safety Report",
)
async def request_safety_report(
    http_request: Request,
    request_body: SafetyReportRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyReportRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    report = safety_report_service.request_report(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
        actor_facility_id=actor_fac_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=report,
        request_id=req_id,
    )


@router.post(
    "/{report_id}/generate",
    response_model=StandardSuccessResponse[SafetyReportRecord],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute Report Generation",
)
async def generate_safety_report(
    report_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyReportRecord]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    report = safety_report_repository.get_report(report_id)
    if report and actor_org_id and report.organization_id != actor_org_id:
        raise AppException(
            code=ErrorCode.SAFETY_REPORT_ACCESS_DENIED,
            message="Access denied to safety report.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    generated_report = safety_report_service.generate_report(report_id)

    return StandardSuccessResponse(
        success=True,
        data=generated_report,
        request_id=req_id,
    )


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyReportRecord]],
    summary="List Safety Reports",
)
async def list_safety_reports(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    report_type: Optional[SafetyReportType] = Query(None),
    lifecycle_state: Optional[SafetyReportLifecycleState] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyReportRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    reports = safety_report_repository.list_reports(
        organization_id=actor_org_id,
        facility_id=actor_fac_id,
        report_type=report_type,
        lifecycle_state=lifecycle_state,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=reports,
        request_id=req_id,
    )


@router.get(
    "/{report_id}",
    response_model=StandardSuccessResponse[SafetyReportRecord],
    summary="Get Safety Report Details",
)
async def get_safety_report(
    report_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyReportRecord]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    
    report = safety_report_repository.get_report(report_id)
    if not report:
        raise AppException(
            code=ErrorCode.SAFETY_REPORT_NOT_FOUND,
            message="Safety report not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    
    if actor_org_id and report.organization_id and report.organization_id != actor_org_id:
        raise AppException(
            code=ErrorCode.SAFETY_REPORT_ACCESS_DENIED,
            message="Access denied to safety report.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return StandardSuccessResponse(
        success=True,
        data=report,
        request_id=req_id,
    )


@router.post(
    "/{report_id}/review",
    response_model=StandardSuccessResponse[SafetyReportRecord],
    summary="Submit Human Report Review",
)
async def submit_report_review(
    report_id: str,
    http_request: Request,
    request_body: SafetyReportReviewSubmission,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyReportRecord]:
    req_id = _req_id(http_request)
    reviewer_id = str(getattr(current_user, "id", "unknown"))
    reviewer_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    report = safety_report_review_service.submit_review(
        report_id=report_id,
        submission=request_body,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        reviewer_authorization_basis=f"role:{reviewer_role}",
        organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=report,
        request_id=req_id,
    )


@router.post(
    "/{report_id}/publish",
    response_model=StandardSuccessResponse[SafetyReportRecord],
    summary="Publish Safety Report",
)
async def publish_safety_report(
    report_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyReportRecord]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)

    report = safety_report_service.publish_report(
        report_id=report_id,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=report,
        request_id=req_id,
    )

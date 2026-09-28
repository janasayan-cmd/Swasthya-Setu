"""Asynchronous Job orchestration and status endpoints (Phase 22).

Enables clients to:
- Enqueue long-running background tasks.
- Poll task lifecycle progress with zero PHI leakage.
- Cancel queued tasks.
- Manually retry failed or cancelled operations.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import get_current_user, get_job_service
from app.core.logging import request_id_ctx_var
from app.schemas.auth import UserRole
from app.schemas.job import (
    JobCancelResponse,
    JobCreate,
    JobRecord,
    JobResponse,
    JobRetryResponse,
    JobStatusResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Asynchronous Jobs"])


def _to_job_response(job: JobRecord) -> JobResponse:
    """Format internal JobRecord to public JobResponse schema."""
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        patient_id=job.patient_id,
        resource_type=job.resource_type,
        resource_id=job.resource_id,
        operation_type=job.operation_type,
        attempt=job.attempt,
        max_retries=job.max_retries,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
        error_message=job.error_message,
        error_category=job.error_category,
        result=job.result,
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue an asynchronous job",
)
async def enqueue_job(
    payload: JobCreate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Enqueue a long-running background task with idempotency and audit tracking."""
    corr_id = request_id_ctx_var.get() or "unknown"
    job = await job_service.enqueue_job(
        payload=payload,
        actor_id=current_user.user_id,
        correlation_id=corr_id,
    )
    return _to_job_response(job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve full job details",
)
async def get_job_details(
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Fetch complete metadata and non-PHI results for an asynchronous job."""
    is_admin = current_user.role == UserRole.ADMIN
    job = await job_service.get_job(
        job_id=job_id,
        actor_id=current_user.user_id,
        is_admin=is_admin,
    )
    return _to_job_response(job)


@router.get(
    "/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Poll job execution status",
)
async def get_job_status(
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobStatusResponse:
    """Lightweight polling endpoint to check status without fetching full payload."""
    is_admin = current_user.role == UserRole.ADMIN
    job = await job_service.get_job(
        job_id=job_id,
        actor_id=current_user.user_id,
        is_admin=is_admin,
    )
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        attempt=job.attempt,
        created_at=job.created_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
        is_terminal=job.is_terminal,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=JobCancelResponse,
    summary="Cancel a queued job",
)
async def cancel_job(
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobCancelResponse:
    """Cancel a pending job before it begins worker execution."""
    is_admin = current_user.role == UserRole.ADMIN
    job = await job_service.cancel_job(
        job_id=job_id,
        actor_id=current_user.user_id,
        is_admin=is_admin,
    )
    return JobCancelResponse(
        job_id=job.id,
        status=job.status,
        message=f"Job '{job.id}' has been cancelled.",
    )


@router.post(
    "/{job_id}/retry",
    response_model=JobRetryResponse,
    summary="Retry a failed job",
)
async def retry_job(
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobRetryResponse:
    """Manually re-enqueue a failed or cancelled job."""
    is_admin = current_user.role == UserRole.ADMIN
    job = await job_service.retry_job(
        job_id=job_id,
        actor_id=current_user.user_id,
        is_admin=is_admin,
    )
    return JobRetryResponse(
        job_id=job.id,
        status=job.status,
        attempt=job.attempt,
        message=f"Job '{job.id}' scheduled for retry.",
    )

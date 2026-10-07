"""Phase 53: Safety Report Validation Service.

Validates report requests, ensuring scope, temporal integrity,
and idempotency constraints are respected.
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_report import SafetyReportRequest, SafetyReportRecord


class SafetyReportValidationService:
    """Validates safety report preconditions and integrity constraints."""

    def validate_report_request(
        self,
        request: SafetyReportRequest,
        actor_organization_id: Optional[str],
        actor_facility_id: Optional[str],
    ) -> None:
        """Validate request against actor authorization context."""
        
        # Temporal validity
        if request.time_period_end <= request.time_period_start:
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_SCOPE_INVALID,
                message="Report end time must be strictly after start time.",
                status_code=422,
            )
            
        # Scope authorization: if client provides org, it must match actor's (tenant isolation)
        if (
            request.organization_id
            and actor_organization_id
            and request.organization_id != actor_organization_id
        ):
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_UNAUTHORIZED,
                message="Requested organization scope does not match authenticated context.",
                status_code=403,
            )
            
        if (
            request.facility_id
            and actor_facility_id
            and request.facility_id != actor_facility_id
        ):
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_UNAUTHORIZED,
                message="Requested facility scope does not match authenticated context.",
                status_code=403,
            )

    def validate_concurrency(self, record: SafetyReportRecord, expected_version: int) -> None:
        """Enforce optimistic concurrency on report state changes."""
        if record.report_version != expected_version:
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_VERSION_CONFLICT,
                message=f"Concurrency conflict: expected version {expected_version}, got {record.report_version}.",
                status_code=409,
            )


# Global singleton
safety_report_validation_service = SafetyReportValidationService()

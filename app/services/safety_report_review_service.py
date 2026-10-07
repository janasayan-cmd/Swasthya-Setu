"""Phase 53: Safety Report Review Service.

Handles human governance review of generated safety reports.
Ensures that AI cannot make authoritative report acceptances.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_report import (
    SafetyReportRecord,
    SafetyReportLifecycleState,
    SafetyReportReviewSubmission,
    SafetyReportReviewDecision,
)
from app.repositories.safety_report_repository import safety_report_repository
from app.services.safety_report_validation_service import safety_report_validation_service

logger = logging.getLogger("app.services.safety_report_review_service")


class SafetyReportReviewService:
    """Manages governed review workflow for safety reports."""

    def __init__(self):
        self._repo = safety_report_repository
        self._validation = safety_report_validation_service

    def submit_review(
        self,
        report_id: str,
        submission: SafetyReportReviewSubmission,
        reviewer_id: str,
        reviewer_role: str,
        reviewer_authorization_basis: str,
        organization_id: Optional[str] = None,
    ) -> SafetyReportRecord:
        """Submit a human review for a generated safety report."""
        report = self._repo.get_report(report_id)
        if not report:
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_NOT_FOUND,
                message=f"Safety report '{report_id}' not found.",
                status_code=404,
            )

        if organization_id and report.organization_id and report.organization_id != organization_id:
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_ACCESS_DENIED,
                message="Cannot review report outside your organization scope.",
                status_code=403,
            )

        if report.lifecycle_state not in (
            SafetyReportLifecycleState.REVIEW_REQUIRED,
            SafetyReportLifecycleState.UNDER_REVIEW,
            SafetyReportLifecycleState.GENERATED,
        ):
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_INVALID_STATE,
                message=f"Report cannot be reviewed in state '{report.lifecycle_state.value}'.",
                status_code=409,
            )

        self._validation.validate_concurrency(report, submission.report_version)

        # Update record with review decision
        now = datetime.now(timezone.utc)
        report.reviewer_id = reviewer_id
        report.reviewer_role = reviewer_role
        report.reviewer_authorization_basis = reviewer_authorization_basis
        report.review_decision = submission.decision
        report.review_summary = submission.review_summary
        report.review_limitations = submission.review_limitations
        report.reviewed_at = now
        report.report_version += 1

        # Determine next lifecycle state based on decision
        if submission.decision in (
            SafetyReportReviewDecision.ACCEPT_REPORT,
            SafetyReportReviewDecision.ACCEPT_WITH_LIMITATIONS,
        ):
            report.lifecycle_state = SafetyReportLifecycleState.APPROVED_FOR_USE
        elif submission.decision == SafetyReportReviewDecision.REJECT_REPORT:
            report.lifecycle_state = SafetyReportLifecycleState.REJECTED
        elif submission.decision == SafetyReportReviewDecision.REQUEST_REVISION:
            report.lifecycle_state = SafetyReportLifecycleState.REOPENED
        else:
            # Escalations mean it needs more action, usually keeping it under review or similar
            report.lifecycle_state = SafetyReportLifecycleState.UNDER_REVIEW
            
        logger.info(
            "Report review submitted",
            extra={
                "report_id": report_id,
                "decision": submission.decision.value,
                "reviewer_id": reviewer_id,
            }
        )
        
        return self._repo.save_report(report)


# Global singleton
safety_report_review_service = SafetyReportReviewService()

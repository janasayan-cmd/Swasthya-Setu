"""Phase 53: Safety Report Orchestration Service.

Primary orchestrator for the safety report lifecycle:
REQUEST → AUTHORIZE → AGGREGATE → GENERATE → REVIEW → PUBLISH.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_report import (
    SafetyReportRequest,
    SafetyReportRecord,
    SafetyReportScope,
    SafetyReportLifecycleState,
    ControlFinding,
    EvidenceGapRecord,
)
from app.repositories.safety_report_repository import safety_report_repository
from app.repositories.safety_assurance_repository import safety_assurance_repository
from app.services.safety_report_validation_service import safety_report_validation_service
from app.services.safety_report_aggregation_service import safety_report_aggregation_service

logger = logging.getLogger("app.services.safety_report_service")


class SafetyReportService:
    """Primary orchestrator for Phase 53 governed safety oversight reporting."""

    def __init__(self):
        self._repo = safety_report_repository
        self._assurance_repo = safety_assurance_repository
        self._validation = safety_report_validation_service
        self._aggregation = safety_report_aggregation_service

    def request_report(
        self,
        request: SafetyReportRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str] = None,
        actor_facility_id: Optional[str] = None,
    ) -> SafetyReportRecord:
        """Initiate a safety report request."""
        self._validation.validate_report_request(
            request, actor_organization_id, actor_facility_id
        )

        if request.idempotency_key:
            existing = self._repo.get_by_idempotency_key(request.idempotency_key)
            if existing:
                return existing

        resolved_org_id = actor_organization_id or request.organization_id
        resolved_fac_id = request.facility_id

        scope = SafetyReportScope(
            organization_id=resolved_org_id,
            facility_id=resolved_fac_id,
            department_id=request.department_id,
            workflow_id=request.workflow_id,
            control_id=request.control_id,
            control_category=request.control_category,
            time_period_start=request.time_period_start,
            time_period_end=request.time_period_end,
        )

        record = SafetyReportRecord(
            report_type=request.report_type,
            scope=scope,
            requested_by_id=actor_id,
            requested_by_role=actor_role,
            organization_id=resolved_org_id,
            facility_id=resolved_fac_id,
            idempotency_key=request.idempotency_key,
        )

        record = self._repo.save_report(record)
        
        logger.info(
            "Safety report requested",
            extra={"report_id": record.report_id, "type": record.report_type.value}
        )
        return record

    def generate_report(self, report_id: str) -> SafetyReportRecord:
        """
        Execute report generation.
        Collects Phase 52 assurance evaluations, aggregates them, and builds the report.
        """
        report = self._repo.get_report(report_id)
        if not report:
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_NOT_FOUND,
                message=f"Report '{report_id}' not found.",
                status_code=404,
            )

        if report.lifecycle_state != SafetyReportLifecycleState.REQUESTED:
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_INVALID_STATE,
                message=f"Cannot generate report in state {report.lifecycle_state.value}",
                status_code=409,
            )

        report.lifecycle_state = SafetyReportLifecycleState.EVIDENCE_COLLECTING
        self._repo.save_report(report)

        # Retrieve relevant Phase 52 evaluations based on scope
        evaluations = self._assurance_repo.list_evaluations(
            organization_id=report.scope.organization_id,
            facility_id=report.scope.facility_id,
            limit=1000,
        )

        # Filter by time period
        evaluations = [
            e for e in evaluations 
            if e.evaluated_at 
            and report.scope.time_period_start <= e.evaluated_at <= report.scope.time_period_end
        ]

        # Further scope filtering
        if report.scope.control_id:
            evaluations = [e for e in evaluations if e.control_id == report.scope.control_id]
        if report.scope.control_category:
            evaluations = [e for e in evaluations if e.control_category == report.scope.control_category]

        report.lifecycle_state = SafetyReportLifecycleState.AGGREGATING
        self._repo.save_report(report)

        distribution, findings = self._aggregation.aggregate_evaluations(evaluations)
        quality = self._aggregation.assess_report_quality(findings)

        report.distribution = distribution
        report.control_findings = findings
        report.quality_state = quality
        
        # Calculate trends based on findings
        report.degradations_detected = sum(1 for f in findings if f.degradation_state != "STABLE")
        report.regressions_detected = sum(1 for f in findings if f.regression_detected)

        report.lifecycle_state = SafetyReportLifecycleState.GENERATED
        report.generated_at = datetime.now(timezone.utc)
        
        # Determine if review is required (e.g. if quality is low, or there are degradations)
        if report.degradations_detected > 0 or report.quality_state == "INSUFFICIENT_EVIDENCE":
            report.lifecycle_state = SafetyReportLifecycleState.REVIEW_REQUIRED

        logger.info(
            "Safety report generated",
            extra={"report_id": report_id, "quality": quality.value}
        )
        
        return self._repo.save_report(report)

    def publish_report(self, report_id: str, actor_organization_id: Optional[str] = None) -> SafetyReportRecord:
        """Publish an approved report."""
        report = self._repo.get_report(report_id)
        if not report:
            raise AppException(ErrorCode.SAFETY_REPORT_NOT_FOUND)
            
        if actor_organization_id and report.organization_id and report.organization_id != actor_organization_id:
            raise AppException(ErrorCode.SAFETY_REPORT_ACCESS_DENIED)

        if report.lifecycle_state not in (
            SafetyReportLifecycleState.APPROVED_FOR_USE,
            SafetyReportLifecycleState.GENERATED, # If no review was required
        ):
            raise AppException(
                code=ErrorCode.SAFETY_REPORT_INVALID_STATE,
                message="Report must be approved or generated (without required review) to publish.",
                status_code=409,
            )

        report.lifecycle_state = SafetyReportLifecycleState.PUBLISHED
        report.published_at = datetime.now(timezone.utc)
        report.report_version += 1
        
        return self._repo.save_report(report)


# Global singleton
safety_report_service = SafetyReportService()

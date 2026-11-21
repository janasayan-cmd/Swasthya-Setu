"""Phase 76: Benefit Performance Indicators & Measurement Intake Service.

Coordinates:
- Configurable benefit performance indicators
- Reproducible indicator outcome calculations (no missing value defaulting)
- Structured measurement intake, evidence verification, and separation of duties
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_benefit_assurance_repository import (
    GovernanceBenefitAssuranceRepository,
    get_governance_benefit_assurance_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_benefit_indicator_measurement import (
    AssessIndicatorRequest,
    BenefitIndicatorRecord,
    BenefitMeasurementRecord,
    CreateIndicatorRequest,
    CreateMeasurementRequest,
    ExpectedDirection,
    IndicatorAssessmentResult,
    IndicatorOutcome,
    MeasurementStatus,
    RejectMeasurementRequest,
    ValidateMeasurementRequest,
)


class GovernanceBenefitIndicatorMeasurementService:
    """Service governing indicator configurations, reproducible assessment, and measurement validation."""

    def __init__(
        self,
        repository: Optional[GovernanceBenefitAssuranceRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_benefit_assurance_repository()

    # -------------------------------------------------------------------------
    # Indicators
    # -------------------------------------------------------------------------

    def create_indicator(
        self,
        benefit_id: str,
        request: CreateIndicatorRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitIndicatorRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        indicator_id = f"ind_{uuid.uuid4().hex[:12]}"

        record = BenefitIndicatorRecord(
            indicator_id=indicator_id,
            benefit_id=benefit_id,
            tenant_id=user_tenant,
            name=request.name,
            description=request.description,
            indicator_type=request.indicator_type,
            calculation_methodology=request.calculation_methodology,
            unit=request.unit,
            expected_direction=request.expected_direction,
            baseline_reference=request.baseline_reference or benefit.active_baseline_id,
            target_reference=request.target_reference or benefit.active_target_id,
            measurement_frequency=request.measurement_frequency,
            organizational_scope=request.organizational_scope,
            source_system=request.source_system,
            data_quality_rules=request.data_quality_rules,
            responsible_owner_id=request.responsible_owner_id,
            verification_requirements=request.verification_requirements,
            version=1,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_indicator(record)

    def list_indicators(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[BenefitIndicatorRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_indicators_for_benefit(benefit_id, user_tenant)

    def get_indicator(
        self,
        indicator_id: str,
        current_user: AuthenticatedUserContext,
    ) -> BenefitIndicatorRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        indicator = self.repo.get_indicator(indicator_id)
        if not indicator or indicator.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_INDICATOR_NOT_FOUND,
                message=f"Indicator '{indicator_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return indicator

    def assess_indicator(
        self,
        indicator_id: str,
        request: AssessIndicatorRequest,
        current_user: AuthenticatedUserContext,
    ) -> IndicatorAssessmentResult:
        indicator = self.get_indicator(indicator_id, current_user)
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        # Never infer success from a missing value
        if request.observed_value is None and not request.qualitative_state:
            return IndicatorAssessmentResult(
                indicator_id=indicator_id,
                benefit_id=indicator.benefit_id,
                assessment_period=request.assessment_period,
                outcome=IndicatorOutcome.INSUFFICIENT_DATA,
                observed_value=None,
                qualitative_state=None,
                details={"reason": "Neither quantitative value nor qualitative state was provided."},
                calculated_at=datetime.now(timezone.utc).isoformat(),
                assessed_by=current_user.user_id,
            )

        baseline_val: Optional[float] = None
        target_val: Optional[float] = None

        if indicator.baseline_reference:
            bsl = self.repo.get_baseline(indicator.baseline_reference)
            if bsl and bsl.baseline_value is not None:
                baseline_val = bsl.baseline_value

        if indicator.target_reference:
            tgt = self.repo.get_target(indicator.target_reference)
            if tgt and tgt.target_value is not None:
                target_val = tgt.target_value

        outcome = IndicatorOutcome.UNABLE_TO_DETERMINE
        obs = request.observed_value

        if obs is not None and target_val is not None:
            if indicator.expected_direction == ExpectedDirection.INCREASING:
                if obs >= target_val:
                    outcome = IndicatorOutcome.TARGET_EXCEEDED if obs > target_val else IndicatorOutcome.TARGET_ACHIEVED
                elif baseline_val is not None and obs > baseline_val:
                    outcome = IndicatorOutcome.IMPROVING
                elif baseline_val is not None and obs < baseline_val:
                    outcome = IndicatorOutcome.BELOW_BASELINE
                else:
                    outcome = IndicatorOutcome.TARGET_PARTIALLY_ACHIEVED
            elif indicator.expected_direction == ExpectedDirection.DECREASING:
                if obs <= target_val:
                    outcome = IndicatorOutcome.TARGET_EXCEEDED if obs < target_val else IndicatorOutcome.TARGET_ACHIEVED
                elif baseline_val is not None and obs < baseline_val:
                    outcome = IndicatorOutcome.IMPROVING
                elif baseline_val is not None and obs > baseline_val:
                    outcome = IndicatorOutcome.BELOW_BASELINE
                else:
                    outcome = IndicatorOutcome.TARGET_PARTIALLY_ACHIEVED
            else:
                outcome = IndicatorOutcome.TARGET_ACHIEVED if obs == target_val else IndicatorOutcome.IMPROVING
        elif request.qualitative_state:
            outcome = IndicatorOutcome.TARGET_ACHIEVED

        return IndicatorAssessmentResult(
            indicator_id=indicator_id,
            benefit_id=indicator.benefit_id,
            assessment_period=request.assessment_period,
            outcome=outcome,
            observed_value=request.observed_value,
            qualitative_state=request.qualitative_state,
            baseline_value=baseline_val,
            target_value=target_val,
            details={
                "calculation_methodology": indicator.calculation_methodology,
                "unit": indicator.unit,
                "supporting_evidence_count": len(request.supporting_evidence_refs),
            },
            calculated_at=datetime.now(timezone.utc).isoformat(),
            assessed_by=current_user.user_id,
        )

    # -------------------------------------------------------------------------
    # Measurements
    # -------------------------------------------------------------------------

    def create_measurement(
        self,
        benefit_id: str,
        request: CreateMeasurementRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitMeasurementRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        indicator = self.repo.get_indicator(request.indicator_id)
        if not indicator or indicator.benefit_id != benefit_id or indicator.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_INDICATOR_NOT_FOUND,
                message=f"Indicator '{request.indicator_id}' does not belong to benefit '{benefit_id}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate units comparability
        if indicator.unit.strip().lower() != request.unit.strip().lower():
            raise AppException(
                code=ErrorCode.MEASUREMENT_VALIDATION_ERROR,
                message=f"Measurement unit '{request.unit}' is incompatible with indicator unit '{indicator.unit}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        measurement_id = f"meas_{uuid.uuid4().hex[:12]}"

        record = BenefitMeasurementRecord(
            measurement_id=measurement_id,
            benefit_id=benefit_id,
            indicator_id=request.indicator_id,
            tenant_id=user_tenant,
            measurement_period=request.measurement_period,
            observed_value=request.observed_value,
            qualitative_state=request.qualitative_state,
            unit=request.unit,
            source_reference=request.source_reference,
            source_system=request.source_system,
            collection_timestamp=now,
            data_freshness_days=0,
            organizational_scope=request.organizational_scope,
            evidence_references=request.evidence_references,
            validation_status=MeasurementStatus.SUBMITTED,
            reviewer_id=None,
            verification_timestamp=None,
            validation_notes=None,
            limitations=request.limitations,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_measurement(record)

    def list_measurements(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[BenefitMeasurementRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_measurements_for_benefit(benefit_id, user_tenant)

    def get_measurement(
        self,
        measurement_id: str,
        current_user: AuthenticatedUserContext,
    ) -> BenefitMeasurementRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        measurement = self.repo.get_measurement(measurement_id)
        if not measurement or measurement.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_MEASUREMENT_NOT_FOUND,
                message=f"Measurement '{measurement_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return measurement

    def validate_measurement(
        self,
        measurement_id: str,
        request: ValidateMeasurementRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitMeasurementRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        measurement = self.get_measurement(measurement_id, current_user)

        # Separation of duties: creator cannot validate their own measurement
        if measurement.created_by == current_user.user_id:
            raise AppException(
                code=ErrorCode.BENEFIT_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: measurement submitter cannot validate their own measurement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        now = datetime.now(timezone.utc).isoformat()
        measurement.validation_status = MeasurementStatus.VALIDATED
        measurement.reviewer_id = current_user.user_id
        measurement.verification_timestamp = now
        measurement.validation_notes = request.validation_notes
        measurement.updated_at = now
        return self.repo.save_measurement(measurement)

    def reject_measurement(
        self,
        measurement_id: str,
        request: RejectMeasurementRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitMeasurementRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        measurement = self.get_measurement(measurement_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        measurement.validation_status = MeasurementStatus.REJECTED
        measurement.reviewer_id = current_user.user_id
        measurement.verification_timestamp = now
        measurement.validation_notes = f"REJECTED: {request.rejection_reason}"
        measurement.updated_at = now
        return self.repo.save_measurement(measurement)

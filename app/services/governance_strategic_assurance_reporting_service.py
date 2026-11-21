"""Phase 77: Governance Strategic Assurance Reporting Service.

Generates multi-level maturity reports, assurance coverage evaluations,
and longitudinal trend reports preserving methodology/framework comparability.
"""

from typing import Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_assurance_evidence import EvidenceVerificationStatus
from app.schemas.governance_assurance_reporting import (
    CoverageAnalysisResponse,
    LongitudinalTrendPoint,
    LongitudinalTrendReportResponse,
    MaturityRadarDimension,
    MaturityReportResponse,
)
from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    MaturityDimensionEnum,
    MaturityLevelEnum,
)


_NUMERIC_LEVELS: Dict[MaturityLevelEnum, float] = {
    MaturityLevelEnum.LEVEL_1_INITIAL: 1.0,
    MaturityLevelEnum.LEVEL_2_DEVELOPING: 2.0,
    MaturityLevelEnum.LEVEL_3_DEFINED: 3.0,
    MaturityLevelEnum.LEVEL_4_MANAGED: 4.0,
    MaturityLevelEnum.LEVEL_5_CONTINUOUSLY_IMPROVING: 5.0,
    MaturityLevelEnum.INSUFFICIENT_EVIDENCE: 0.0,
    MaturityLevelEnum.NOT_ASSESSED: 0.0,
    MaturityLevelEnum.UNABLE_TO_DETERMINE: 0.0,
}


class GovernanceStrategicAssuranceReportingService:
    """Provides reporting and analytical insights for strategic governance assurance."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def get_maturity_report(
        self,
        tenant_id: str,
        assessment_id: str,
    ) -> MaturityReportResponse:
        assessment = self.repository.get_assessment(assessment_id)
        if not assessment or assessment.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' was not found.",
                status_code=404,
            )

        dimension_scores: List[MaturityRadarDimension] = []
        for dim_name, d_res in assessment.dimension_results.items():
            dimension_scores.append(
                MaturityRadarDimension(
                    dimension=d_res.dimension,
                    level=d_res.achieved_level,
                    numeric_score=_NUMERIC_LEVELS.get(d_res.achieved_level, 0.0),
                    confidence=d_res.confidence_score,
                )
            )

        return MaturityReportResponse(
            tenant_id=tenant_id,
            assessment_id=assessment.assessment_id,
            scope_type=assessment.scope.scope_type.value,
            scope_name=assessment.scope.scope_name,
            overall_maturity_level=assessment.overall_maturity_level,
            dimension_scores=dimension_scores,
            evidence_coverage_percentage=assessment.evidence_coverage_percentage,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )

    def get_coverage_analysis(
        self,
        tenant_id: str,
    ) -> CoverageAnalysisResponse:
        assessments = self.repository.list_assessments(tenant_id=tenant_id, limit=200)

        unique_scopes = set()
        for asmt in assessments:
            unique_scopes.add((asmt.scope.scope_type.value, asmt.scope.scope_id))

        total_scopes = max(len(unique_scopes), 1)
        scopes_assessed = len(unique_scopes)

        # Collect evidence across assessments
        all_evidence = []
        for asmt in assessments:
            evidence_items = self.repository.list_evidence_for_assessment(
                tenant_id=tenant_id,
                assessment_id=asmt.assessment_id,
            )
            all_evidence.extend(evidence_items)

        availability_count = len(all_evidence)
        adequacy_count = sum(
            1 for ev in all_evidence
            if ev.verification_status == EvidenceVerificationStatus.VERIFIED and not ev.is_stale
        )

        coverage_ratio = round(scopes_assessed / total_scopes, 2)

        scope_breakdown = {}
        for scope_type, scope_id in unique_scopes:
            scope_breakdown[f"{scope_type}:{scope_id}"] = "ASSESSED"

        return CoverageAnalysisResponse(
            tenant_id=tenant_id,
            total_scopes_defined=total_scopes,
            scopes_assessed=scopes_assessed,
            coverage_ratio=coverage_ratio,
            evidence_availability_count=availability_count,
            evidence_adequacy_count=adequacy_count,
            scope_breakdown=scope_breakdown,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )

    def get_longitudinal_trend(
        self,
        tenant_id: str,
        scope_id: str,
    ) -> LongitudinalTrendReportResponse:
        assessments = self.repository.list_assessments(
            tenant_id=tenant_id,
            scope_id=scope_id,
            limit=100,
        )
        if not assessments:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"No assessments found for scope '{scope_id}'.",
                status_code=404,
            )

        # Sort chronologically ascending
        assessments.sort(key=lambda x: x.assessment_date)

        data_points: List[LongitudinalTrendPoint] = []
        previous_version: Optional[str] = None
        version_transition_detected = False

        for asmt in assessments:
            caveat = None
            if previous_version and previous_version != asmt.framework_version:
                version_transition_detected = True
                caveat = f"Framework methodology transitioned from {previous_version} to {asmt.framework_version}. Direct metric comparison has comparability limitations."

            data_points.append(
                LongitudinalTrendPoint(
                    assessment_id=asmt.assessment_id,
                    assessment_date=asmt.assessment_date,
                    framework_version=asmt.framework_version,
                    overall_level=asmt.overall_maturity_level,
                    comparability_caveat=caveat,
                )
            )
            previous_version = asmt.framework_version

        scope_name = assessments[0].scope.scope_name

        return LongitudinalTrendReportResponse(
            tenant_id=tenant_id,
            scope_id=scope_id,
            scope_name=scope_name,
            data_points=data_points,
            version_transition_detected=version_transition_detected,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )

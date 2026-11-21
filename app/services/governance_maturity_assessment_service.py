"""Phase 77: Governance Maturity Assessment Service.

Evaluates organizational governance maturity against structured framework criteria,
ensures reproducible evidence-backed determinations (no missing data defaulting),
and calculates controlled multi-level aggregations.
"""

from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_assurance_evidence import EvidenceVerificationStatus
from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    FrameworkStatus,
    MaturityDimensionEnum,
    MaturityLevelEnum,
)
from app.schemas.governance_maturity_assessment import (
    AggregateMaturityRequest,
    AggregateMaturityResponse,
    AssessmentStatus,
    CreateAssessmentRequest,
    CriterionEvaluationResult,
    DimensionAssessmentResult,
    EvaluateDimensionRequest,
    GovernanceMaturityAssessmentRecord,
    SubmitAssessmentRequest,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


_LEVEL_HIERARCHY = [
    MaturityLevelEnum.LEVEL_1_INITIAL,
    MaturityLevelEnum.LEVEL_2_DEVELOPING,
    MaturityLevelEnum.LEVEL_3_DEFINED,
    MaturityLevelEnum.LEVEL_4_MANAGED,
    MaturityLevelEnum.LEVEL_5_CONTINUOUSLY_IMPROVING,
]

_LEVEL_RANK: Dict[MaturityLevelEnum, int] = {
    MaturityLevelEnum.NOT_ASSESSED: -1,
    MaturityLevelEnum.UNABLE_TO_DETERMINE: -1,
    MaturityLevelEnum.INSUFFICIENT_EVIDENCE: 0,
    MaturityLevelEnum.LEVEL_1_INITIAL: 1,
    MaturityLevelEnum.LEVEL_2_DEVELOPING: 2,
    MaturityLevelEnum.LEVEL_3_DEFINED: 3,
    MaturityLevelEnum.LEVEL_4_MANAGED: 4,
    MaturityLevelEnum.LEVEL_5_CONTINUOUSLY_IMPROVING: 5,
}

_RANK_TO_LEVEL: Dict[int, MaturityLevelEnum] = {
    -1: MaturityLevelEnum.NOT_ASSESSED,
    0: MaturityLevelEnum.INSUFFICIENT_EVIDENCE,
    1: MaturityLevelEnum.LEVEL_1_INITIAL,
    2: MaturityLevelEnum.LEVEL_2_DEVELOPING,
    3: MaturityLevelEnum.LEVEL_3_DEFINED,
    4: MaturityLevelEnum.LEVEL_4_MANAGED,
    5: MaturityLevelEnum.LEVEL_5_CONTINUOUSLY_IMPROVING,
}


class GovernanceMaturityAssessmentService:
    """Manages assessment lifecycle, evidence-backed criteria evaluation, and aggregation."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def create_assessment(
        self,
        tenant_id: str,
        assessor_id: str,
        request: CreateAssessmentRequest,
    ) -> GovernanceMaturityAssessmentRecord:
        framework = self.repository.get_framework(request.framework_id)
        if not framework or framework.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{request.framework_id}' was not found.",
                status_code=404,
            )

        if framework.status not in (FrameworkStatus.ACTIVE, FrameworkStatus.APPROVED):
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_FRAMEWORK_STATE,
                message=f"Cannot initiate assessment on framework with status '{framework.status.value}'. Must be ACTIVE or APPROVED.",
                status_code=400,
            )

        now = _get_utc_now_str()
        assessment_date = request.assessment_date or now

        assessment = GovernanceMaturityAssessmentRecord(
            assessment_id=f"asmt-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            framework_id=request.framework_id,
            framework_version=framework.version,
            scope=request.scope,
            status=AssessmentStatus.DRAFT,
            assessor_id=assessor_id,
            assessment_date=assessment_date,
            dimension_results={},
            overall_maturity_level=MaturityLevelEnum.NOT_ASSESSED,
            summary_findings=request.summary_findings or "",
            evidence_coverage_percentage=0.0,
            independent_review_id=None,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_assessment(assessment)

    def evaluate_dimension(
        self,
        tenant_id: str,
        assessment_id: str,
        request: EvaluateDimensionRequest,
    ) -> GovernanceMaturityAssessmentRecord:
        assessment = self.repository.get_assessment(assessment_id)
        if not assessment or assessment.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' was not found.",
                status_code=404,
            )

        if assessment.status not in (AssessmentStatus.DRAFT, AssessmentStatus.IN_PROGRESS):
            raise AppException(
                code=ErrorCode.INVALID_MATURITY_ASSESSMENT_STATE,
                message=f"Assessment in status '{assessment.status.value}' cannot be evaluated.",
                status_code=400,
            )

        framework = self.repository.get_framework(assessment.framework_id)
        if not framework:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Referenced framework '{assessment.framework_id}' not found.",
                status_code=404,
            )

        dim_def = next((d for d in framework.dimensions if d.dimension == request.dimension), None)
        if not dim_def:
            raise AppException(
                code=ErrorCode.MATURITY_DIMENSION_NOT_FOUND,
                message=f"Dimension '{request.dimension.value}' not defined in framework '{framework.framework_id}'.",
                status_code=404,
            )

        # Retrieve all evidence submitted for this assessment and dimension
        all_evidence = self.repository.list_evidence_for_assessment(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            dimension=request.dimension.value,
        )

        criteria_results: List[CriterionEvaluationResult] = []
        criteria_by_level: Dict[MaturityLevelEnum, List[bool]] = {
            lvl: [] for lvl in _LEVEL_HIERARCHY
        }

        total_criteria = len(dim_def.criteria)
        verified_criteria_count = 0

        for crit in dim_def.criteria:
            matching_verified = [
                ev for ev in all_evidence
                if ev.criterion_id == crit.criterion_id
                and ev.verification_status == EvidenceVerificationStatus.VERIFIED
                and not ev.is_stale
            ]

            is_met = len(matching_verified) > 0
            missing_reasons = []
            if not is_met:
                # No verified evidence: strictly no missing data defaulting
                missing_reasons.append("Missing verified assurance evidence. Missing data cannot default to compliant.")
            else:
                verified_criteria_count += 1

            if crit.target_level in criteria_by_level:
                criteria_by_level[crit.target_level].append(is_met)

            criteria_results.append(
                CriterionEvaluationResult(
                    criterion_id=crit.criterion_id,
                    dimension=crit.dimension,
                    target_level=crit.target_level,
                    is_met=is_met,
                    evidence_count=len(matching_verified),
                    verified_evidence_ids=[ev.evidence_id for ev in matching_verified],
                    missing_evidence_reasons=missing_reasons,
                    evaluation_notes=f"Criterion evaluated against {len(matching_verified)} verified evidence items.",
                )
            )

        # Determine achieved level for this dimension
        # A level is achieved only if ALL criteria for that level and ALL lower levels are met.
        achieved_level = MaturityLevelEnum.INSUFFICIENT_EVIDENCE
        if verified_criteria_count == 0:
            achieved_level = MaturityLevelEnum.INSUFFICIENT_EVIDENCE
        else:
            current_max = MaturityLevelEnum.LEVEL_1_INITIAL
            for lvl in _LEVEL_HIERARCHY:
                crit_met_list = criteria_by_level.get(lvl, [])
                if not crit_met_list:
                    continue
                if all(crit_met_list):
                    current_max = lvl
                else:
                    # Break progression when any higher level criteria are not met
                    break
            achieved_level = current_max

        confidence = round(verified_criteria_count / max(1, total_criteria), 2)
        confidence = min(1.0, max(0.0, confidence))

        dimension_result = DimensionAssessmentResult(
            dimension=request.dimension,
            achieved_level=achieved_level,
            criteria_results=criteria_results,
            strengths=request.strengths or [],
            vulnerabilities=request.vulnerabilities or [],
            confidence_score=confidence,
        )

        dim_results = dict(assessment.dimension_results)
        dim_results[request.dimension.value] = dimension_result

        # Recompute overall maturity level: weakest link among assessed dimensions
        overall_rank = 5
        has_insufficient = False
        for d_res in dim_results.values():
            rank = _LEVEL_RANK.get(d_res.achieved_level, 0)
            if rank <= 0:
                has_insufficient = True
            overall_rank = min(overall_rank, rank)

        if has_insufficient and overall_rank <= 0:
            overall_level = MaturityLevelEnum.INSUFFICIENT_EVIDENCE
        else:
            overall_level = _RANK_TO_LEVEL.get(overall_rank, MaturityLevelEnum.LEVEL_1_INITIAL)

        # Coverage percentage: dimensions assessed / total dimensions in framework
        coverage_pct = round((len(dim_results) / max(1, len(framework.dimensions))) * 100.0, 1)

        now = _get_utc_now_str()
        assessment = assessment.model_copy(
            update={
                "status": AssessmentStatus.IN_PROGRESS,
                "dimension_results": dim_results,
                "overall_maturity_level": overall_level,
                "evidence_coverage_percentage": coverage_pct,
                "updated_at": now,
            }
        )
        return self.repository.save_assessment(assessment)

    def submit_assessment(
        self,
        tenant_id: str,
        assessment_id: str,
        request: SubmitAssessmentRequest,
    ) -> GovernanceMaturityAssessmentRecord:
        assessment = self.repository.get_assessment(assessment_id)
        if not assessment or assessment.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' was not found.",
                status_code=404,
            )

        if assessment.status not in (AssessmentStatus.DRAFT, AssessmentStatus.IN_PROGRESS):
            raise AppException(
                code=ErrorCode.INVALID_MATURITY_ASSESSMENT_STATE,
                message=f"Assessment in status '{assessment.status.value}' cannot be submitted. Only DRAFT or IN_PROGRESS assessments can be submitted.",
                status_code=400,
            )

        if not assessment.dimension_results:
            raise AppException(
                code=ErrorCode.INVALID_MATURITY_ASSESSMENT_STATE,
                message="Cannot submit an assessment with zero evaluated dimensions.",
                status_code=400,
            )

        now = _get_utc_now_str()
        assessment = assessment.model_copy(
            update={
                "status": AssessmentStatus.SUBMITTED,
                "updated_at": now,
            }
        )
        return self.repository.save_assessment(assessment)

    def aggregate_maturity(
        self,
        tenant_id: str,
        request: AggregateMaturityRequest,
    ) -> AggregateMaturityResponse:
        if not request.child_assessment_ids:
            raise AppException(
                code=ErrorCode.INVALID_MATURITY_ASSESSMENT_STATE,
                message="Cannot aggregate empty child assessment list.",
                status_code=400,
            )

        child_assessments = []
        for asmt_id in request.child_assessment_ids:
            asmt = self.repository.get_assessment(asmt_id)
            if not asmt or asmt.tenant_id != tenant_id:
                raise AppException(
                    code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                    message=f"Child assessment '{asmt_id}' not found.",
                    status_code=404,
                )
            if asmt.framework_id != request.framework_id:
                raise AppException(
                    code=ErrorCode.INVALID_MATURITY_ASSESSMENT_STATE,
                    message=f"Child assessment '{asmt_id}' belongs to framework '{asmt.framework_id}', not requested '{request.framework_id}'.",
                    status_code=400,
                )
            child_assessments.append(asmt)

        # Controlled aggregation without double-counting or invalid extrapolation
        # Compute dimension-level minimums across all child assessments
        dim_ranks: Dict[str, int] = {}
        for asmt in child_assessments:
            for dim_name, d_res in asmt.dimension_results.items():
                rank = _LEVEL_RANK.get(d_res.achieved_level, 0)
                if dim_name not in dim_ranks:
                    dim_ranks[dim_name] = rank
                else:
                    dim_ranks[dim_name] = min(dim_ranks[dim_name], rank)

        dimension_levels: Dict[str, MaturityLevelEnum] = {}
        for dim_name, rank in dim_ranks.items():
            dimension_levels[dim_name] = _RANK_TO_LEVEL.get(rank, MaturityLevelEnum.INSUFFICIENT_EVIDENCE)

        overall_agg_rank = min(dim_ranks.values()) if dim_ranks else -1
        overall_agg_level = _RANK_TO_LEVEL.get(overall_agg_rank, MaturityLevelEnum.NOT_ASSESSED)

        return AggregateMaturityResponse(
            parent_scope=request.parent_scope,
            framework_id=request.framework_id,
            aggregated_level=overall_agg_level,
            dimension_levels=dimension_levels,
            child_assessments_counted=len(child_assessments),
            aggregation_methodology="Weakest-link conservative aggregation across child scopes without double-counting.",
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )

    def get_assessment(
        self,
        tenant_id: str,
        assessment_id: str,
    ) -> GovernanceMaturityAssessmentRecord:
        assessment = self.repository.get_assessment(assessment_id)
        if not assessment or assessment.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' was not found.",
                status_code=404,
            )
        return assessment

    def list_assessments(
        self,
        tenant_id: str,
        scope_id: Optional[str] = None,
        scope_type: Optional[str] = None,
        status: Optional[AssessmentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceMaturityAssessmentRecord]:
        return self.repository.list_assessments(
            tenant_id=tenant_id,
            scope_id=scope_id,
            scope_type=scope_type,
            status=status,
            skip=skip,
            limit=limit,
        )

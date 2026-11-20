"""Phase 71: Clinical Safety Governance Audit Finding Analytics & Systemic Risk Insight REST API Endpoints.

Implements endpoints for:
- Historical audit finding analytics, breakdowns, and coverage
- Time-series governance trend analysis across reporting periods
- Repeat-finding candidate detection and human review workflows
- Cross-audit analytical pattern identification and governance referrals
- Systemic issue candidate generation with deterministic priority scoring
- Corrective action recurrence tracking against Phase 54 and Phase 55 references
- Structured, reproducible management review preparation reports and approvals
- Versioned analytical configuration lifecycle

Base Path: /api/v1/governance-audit-intelligence
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.audit_analytics_config import (
    AnalyticsConfigRecord,
    ApproveAnalyticsConfigRequest,
    CreateAnalyticsConfigRequest,
    DeprecateAnalyticsConfigRequest,
)
from app.schemas.audit_analytics_source import ReportingPeriodType
from app.schemas.audit_capa_recurrence import CAPARecurrenceRecord
from app.schemas.audit_governance_report import (
    ApproveManagementReportRequest,
    GenerateManagementReportRequest,
    GovernanceTrendsResponse,
    HistoricalFindingsOverviewResponse,
    ManagementReportRecord,
)
from app.schemas.audit_pattern_systemic import (
    AuditPatternRecord,
    ConfirmSystemicCandidateRequest,
    ReferPatternRequest,
    ReferSystemicCandidateRequest,
    RejectSystemicCandidateRequest,
    ReviewPatternRequest,
    ReviewSystemicCandidateRequest,
    SystemicIssueCandidateRecord,
)
from app.schemas.audit_repeat_finding import (
    ConfirmRepeatFindingRequest,
    RejectRepeatFindingRequest,
    RepeatFindingCandidateRecord,
    ReviewRepeatFindingRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_analytics_config_service import (
    AuditAnalyticsConfigService,
    get_audit_analytics_config_service,
)
from app.services.capa_recurrence_analysis_service import (
    CAPARecurrenceAnalysisService,
    get_capa_recurrence_analysis_service,
)
from app.services.cross_audit_pattern_service import (
    CrossAuditPatternService,
    get_cross_audit_pattern_service,
)
from app.services.historical_audit_analytics_service import (
    HistoricalAuditAnalyticsService,
    get_historical_audit_analytics_service,
)
from app.services.management_review_reporting_service import (
    ManagementReviewReportingService,
    get_management_review_reporting_service,
)
from app.services.repeat_finding_detection_service import (
    RepeatFindingDetectionService,
    get_repeat_finding_detection_service,
)
from app.services.systemic_risk_insight_service import (
    SystemicRiskInsightService,
    get_systemic_risk_insight_service,
)

router = APIRouter(
    prefix="/governance-audit-intelligence",
    tags=["Phase 71 - Clinical Safety Governance Audit Intelligence"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforce that patient role cannot access audit intelligence endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance audit intelligence features.",
            status_code=403,
        )


# =============================================================================
# 1. HISTORICAL AUDIT FINDINGS ANALYTICS
# =============================================================================

@router.get(
    "/analytics/overview",
    response_model=HistoricalFindingsOverviewResponse,
    summary="Get multi-dimensional overview of historical audit findings",
)
def get_historical_findings_overview(
    facility_id: Optional[str] = Query(None),
    period_type: ReportingPeriodType = Query(ReportingPeriodType.LAST_90_DAYS),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> HistoricalFindingsOverviewResponse:
    _ensure_not_patient(current_user)
    return analytics_service.get_overview(
        current_user,
        facility_id=facility_id,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/analytics/findings",
    response_model=HistoricalFindingsOverviewResponse,
    summary="Get aggregated historical findings summary",
)
def get_findings_summary(
    facility_id: Optional[str] = Query(None),
    period_type: ReportingPeriodType = Query(ReportingPeriodType.LAST_90_DAYS),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> HistoricalFindingsOverviewResponse:
    _ensure_not_patient(current_user)
    return analytics_service.get_overview(
        current_user, facility_id=facility_id, period_type=period_type
    )


@router.get(
    "/analytics/findings/trends",
    response_model=GovernanceTrendsResponse,
    summary="Get time-series trends across findings, repeats, backlog, and CAPA",
)
def get_governance_trends(
    facility_id: Optional[str] = Query(None),
    period_type: ReportingPeriodType = Query(ReportingPeriodType.LAST_12_MONTHS),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> GovernanceTrendsResponse:
    _ensure_not_patient(current_user)
    return analytics_service.get_trends(
        current_user,
        facility_id=facility_id,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/analytics/findings/by-severity",
    response_model=Dict[str, int],
    summary="Get finding counts grouped by severity",
)
def get_findings_by_severity(
    facility_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> Dict[str, int]:
    _ensure_not_patient(current_user)
    overview = analytics_service.get_overview(current_user, facility_id=facility_id)
    return overview.findings_by_severity


@router.get(
    "/analytics/findings/by-category",
    response_model=Dict[str, int],
    summary="Get finding counts grouped by category",
)
def get_findings_by_category(
    facility_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> Dict[str, int]:
    _ensure_not_patient(current_user)
    overview = analytics_service.get_overview(current_user, facility_id=facility_id)
    return overview.findings_by_category


@router.get(
    "/analytics/findings/by-control",
    response_model=Dict[str, int],
    summary="Get finding counts grouped by criterion/control",
)
def get_findings_by_control(
    facility_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> Dict[str, int]:
    _ensure_not_patient(current_user)
    overview = analytics_service.get_overview(current_user, facility_id=facility_id)
    return overview.findings_by_control


@router.get(
    "/analytics/findings/by-organization",
    response_model=Dict[str, int],
    summary="Get finding counts grouped by facility/unit",
)
def get_findings_by_organization(
    facility_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> Dict[str, int]:
    _ensure_not_patient(current_user)
    overview = analytics_service.get_overview(current_user, facility_id=facility_id)
    return overview.findings_by_facility


@router.get(
    "/analytics/audit-coverage",
    response_model=Dict[str, Any],
    summary="Get audit coverage statistics",
)
def get_audit_coverage(
    facility_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    analytics_service: HistoricalAuditAnalyticsService = Depends(
        get_historical_audit_analytics_service
    ),
) -> Dict[str, Any]:
    _ensure_not_patient(current_user)
    overview = analytics_service.get_overview(current_user, facility_id=facility_id)
    return overview.audit_coverage_summary


# =============================================================================
# 2. REPEAT-FINDING DETECTION
# =============================================================================

@router.post(
    "/repeat-findings/detect",
    response_model=List[RepeatFindingCandidateRecord],
    summary="Trigger deterministic repeat finding detection",
)
def trigger_repeat_finding_detection(
    audit_id: Optional[str] = Query(None),
    lookback_days: int = Query(365, ge=1, le=1825),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repeat_service: RepeatFindingDetectionService = Depends(
        get_repeat_finding_detection_service
    ),
) -> List[RepeatFindingCandidateRecord]:
    _ensure_not_patient(current_user)
    return repeat_service.detect_repeat_findings(
        current_user, audit_id=audit_id, lookback_days=lookback_days
    )


@router.get(
    "/repeat-findings",
    response_model=List[RepeatFindingCandidateRecord],
    summary="List repeat finding candidates",
)
def list_repeat_finding_candidates(
    facility_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    confidence: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repeat_service: RepeatFindingDetectionService = Depends(
        get_repeat_finding_detection_service
    ),
) -> List[RepeatFindingCandidateRecord]:
    _ensure_not_patient(current_user)
    return repeat_service.list_candidates(
        current_user,
        facility_id=facility_id,
        status=status_filter,
        confidence=confidence,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/repeat-findings/{candidate_id}",
    response_model=RepeatFindingCandidateRecord,
    summary="Get repeat finding candidate details",
)
def get_repeat_finding_candidate(
    candidate_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repeat_service: RepeatFindingDetectionService = Depends(
        get_repeat_finding_detection_service
    ),
) -> RepeatFindingCandidateRecord:
    _ensure_not_patient(current_user)
    return repeat_service.get_candidate(current_user, candidate_id)


@router.post(
    "/repeat-findings/{candidate_id}/review",
    response_model=RepeatFindingCandidateRecord,
    summary="Record human review disposition for a repeat finding candidate",
)
def review_repeat_finding_candidate(
    candidate_id: str,
    payload: ReviewRepeatFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repeat_service: RepeatFindingDetectionService = Depends(
        get_repeat_finding_detection_service
    ),
) -> RepeatFindingCandidateRecord:
    _ensure_not_patient(current_user)
    return repeat_service.review_candidate(current_user, candidate_id, payload)


@router.post(
    "/repeat-findings/{candidate_id}/confirm",
    response_model=RepeatFindingCandidateRecord,
    summary="Confirm a repeat finding candidate",
)
def confirm_repeat_finding_candidate(
    candidate_id: str,
    payload: ConfirmRepeatFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repeat_service: RepeatFindingDetectionService = Depends(
        get_repeat_finding_detection_service
    ),
) -> RepeatFindingCandidateRecord:
    _ensure_not_patient(current_user)
    return repeat_service.confirm_candidate(current_user, candidate_id, payload)


@router.post(
    "/repeat-findings/{candidate_id}/reject",
    response_model=RepeatFindingCandidateRecord,
    summary="Reject a repeat finding candidate",
)
def reject_repeat_finding_candidate(
    candidate_id: str,
    payload: RejectRepeatFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repeat_service: RepeatFindingDetectionService = Depends(
        get_repeat_finding_detection_service
    ),
) -> RepeatFindingCandidateRecord:
    _ensure_not_patient(current_user)
    return repeat_service.reject_candidate(current_user, candidate_id, payload)


# =============================================================================
# 3. CROSS-AUDIT PATTERN ANALYSIS
# =============================================================================

@router.post(
    "/patterns/detect",
    response_model=List[AuditPatternRecord],
    summary="Trigger cross-audit pattern detection",
)
def trigger_pattern_detection(
    min_findings: int = Query(2, ge=2, le=50),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    pattern_service: CrossAuditPatternService = Depends(get_cross_audit_pattern_service),
) -> List[AuditPatternRecord]:
    _ensure_not_patient(current_user)
    return pattern_service.detect_patterns(current_user, min_findings=min_findings)


@router.get(
    "/patterns",
    response_model=List[AuditPatternRecord],
    summary="List cross-audit patterns",
)
def list_audit_patterns(
    category: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    pattern_service: CrossAuditPatternService = Depends(get_cross_audit_pattern_service),
) -> List[AuditPatternRecord]:
    _ensure_not_patient(current_user)
    return pattern_service.list_patterns(
        current_user, category=category, status=status_filter, limit=limit, offset=offset
    )


@router.get(
    "/patterns/{pattern_id}",
    response_model=AuditPatternRecord,
    summary="Get cross-audit pattern details",
)
def get_audit_pattern(
    pattern_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    pattern_service: CrossAuditPatternService = Depends(get_cross_audit_pattern_service),
) -> AuditPatternRecord:
    _ensure_not_patient(current_user)
    return pattern_service.get_pattern(current_user, pattern_id)


@router.post(
    "/patterns/{pattern_id}/review",
    response_model=AuditPatternRecord,
    summary="Review cross-audit pattern",
)
def review_audit_pattern(
    pattern_id: str,
    payload: ReviewPatternRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    pattern_service: CrossAuditPatternService = Depends(get_cross_audit_pattern_service),
) -> AuditPatternRecord:
    _ensure_not_patient(current_user)
    return pattern_service.review_pattern(current_user, pattern_id, payload)


@router.post(
    "/patterns/{pattern_id}/refer",
    response_model=AuditPatternRecord,
    summary="Refer pattern to authoritative governance workflow",
)
def refer_audit_pattern(
    pattern_id: str,
    payload: ReferPatternRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    pattern_service: CrossAuditPatternService = Depends(get_cross_audit_pattern_service),
) -> AuditPatternRecord:
    _ensure_not_patient(current_user)
    return pattern_service.refer_pattern(current_user, pattern_id, payload)


# =============================================================================
# 4. SYSTEMIC ISSUE CANDIDATES
# =============================================================================

@router.post(
    "/systemic-issue-candidates/detect",
    response_model=List[SystemicIssueCandidateRecord],
    summary="Trigger systemic issue candidate detection and priority scoring",
)
def trigger_systemic_candidate_detection(
    min_score: float = Query(2.0, ge=0.0, le=100.0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    systemic_service: SystemicRiskInsightService = Depends(
        get_systemic_risk_insight_service
    ),
) -> List[SystemicIssueCandidateRecord]:
    _ensure_not_patient(current_user)
    return systemic_service.generate_systemic_candidates(current_user, min_score=min_score)


@router.get(
    "/systemic-issue-candidates",
    response_model=List[SystemicIssueCandidateRecord],
    summary="List systemic issue candidates",
)
def list_systemic_candidates(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    systemic_service: SystemicRiskInsightService = Depends(
        get_systemic_risk_insight_service
    ),
) -> List[SystemicIssueCandidateRecord]:
    _ensure_not_patient(current_user)
    return systemic_service.list_candidates(
        current_user, status=status_filter, limit=limit, offset=offset
    )


@router.get(
    "/systemic-issue-candidates/{candidate_id}",
    response_model=SystemicIssueCandidateRecord,
    summary="Get systemic issue candidate details",
)
def get_systemic_candidate(
    candidate_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    systemic_service: SystemicRiskInsightService = Depends(
        get_systemic_risk_insight_service
    ),
) -> SystemicIssueCandidateRecord:
    _ensure_not_patient(current_user)
    return systemic_service.get_candidate(current_user, candidate_id)


@router.post(
    "/systemic-issue-candidates/{candidate_id}/review",
    response_model=SystemicIssueCandidateRecord,
    summary="Record human review disposition for a systemic issue candidate",
)
def review_systemic_candidate(
    candidate_id: str,
    payload: ReviewSystemicCandidateRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    systemic_service: SystemicRiskInsightService = Depends(
        get_systemic_risk_insight_service
    ),
) -> SystemicIssueCandidateRecord:
    _ensure_not_patient(current_user)
    return systemic_service.review_candidate(current_user, candidate_id, payload)


@router.post(
    "/systemic-issue-candidates/{candidate_id}/confirm",
    response_model=SystemicIssueCandidateRecord,
    summary="Confirm a systemic issue candidate",
)
def confirm_systemic_candidate(
    candidate_id: str,
    payload: ConfirmSystemicCandidateRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    systemic_service: SystemicRiskInsightService = Depends(
        get_systemic_risk_insight_service
    ),
) -> SystemicIssueCandidateRecord:
    _ensure_not_patient(current_user)
    return systemic_service.confirm_candidate(current_user, candidate_id, payload)


@router.post(
    "/systemic-issue-candidates/{candidate_id}/reject",
    response_model=SystemicIssueCandidateRecord,
    summary="Reject a systemic issue candidate",
)
def reject_systemic_candidate(
    candidate_id: str,
    payload: RejectSystemicCandidateRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    systemic_service: SystemicRiskInsightService = Depends(
        get_systemic_risk_insight_service
    ),
) -> SystemicIssueCandidateRecord:
    _ensure_not_patient(current_user)
    return systemic_service.reject_candidate(current_user, candidate_id, payload)


@router.post(
    "/systemic-issue-candidates/{candidate_id}/refer",
    response_model=SystemicIssueCandidateRecord,
    summary="Refer systemic issue to authoritative governance workflows",
)
def refer_systemic_candidate(
    candidate_id: str,
    payload: ReferSystemicCandidateRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    systemic_service: SystemicRiskInsightService = Depends(
        get_systemic_risk_insight_service
    ),
) -> SystemicIssueCandidateRecord:
    _ensure_not_patient(current_user)
    return systemic_service.refer_candidate(current_user, candidate_id, payload)


# =============================================================================
# 5. CORRECTIVE ACTION RECURRENCE
# =============================================================================

@router.get(
    "/corrective-actions/recurrence",
    response_model=List[CAPARecurrenceRecord],
    summary="List corrective action recurrence analysis records",
)
def list_corrective_action_recurrences(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    capa_service: CAPARecurrenceAnalysisService = Depends(
        get_capa_recurrence_analysis_service
    ),
) -> List[CAPARecurrenceRecord]:
    _ensure_not_patient(current_user)
    return capa_service.list_recurrences(
        current_user, status=status_filter, limit=limit, offset=offset
    )


@router.get(
    "/corrective-actions/recurrence/{finding_id}",
    response_model=Optional[CAPARecurrenceRecord],
    summary="Get recurrence record for a specific finding",
)
def get_corrective_action_recurrence_by_finding(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    capa_service: CAPARecurrenceAnalysisService = Depends(
        get_capa_recurrence_analysis_service
    ),
) -> Optional[CAPARecurrenceRecord]:
    _ensure_not_patient(current_user)
    return capa_service.get_recurrence_by_finding(current_user, finding_id)


# =============================================================================
# 6. MANAGEMENT REVIEW & GOVERNANCE REPORTING
# =============================================================================

@router.post(
    "/management-reports/generate",
    response_model=ManagementReportRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a reproducible management review preparation report",
)
def generate_management_report(
    payload: GenerateManagementReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: ManagementReviewReportingService = Depends(
        get_management_review_reporting_service
    ),
) -> ManagementReportRecord:
    _ensure_not_patient(current_user)
    return report_service.generate_report(current_user, payload)


@router.get(
    "/management-reports",
    response_model=List[ManagementReportRecord],
    summary="List management review preparation reports",
)
def list_management_reports(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: ManagementReviewReportingService = Depends(
        get_management_review_reporting_service
    ),
) -> List[ManagementReportRecord]:
    _ensure_not_patient(current_user)
    return report_service.list_reports(
        current_user, facility_id=facility_id, limit=limit, offset=offset
    )


@router.get(
    "/management-reports/{report_id}",
    response_model=ManagementReportRecord,
    summary="Get management review report details",
)
def get_management_report(
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: ManagementReviewReportingService = Depends(
        get_management_review_reporting_service
    ),
) -> ManagementReportRecord:
    _ensure_not_patient(current_user)
    return report_service.get_report(current_user, report_id)


@router.post(
    "/management-reports/{report_id}/approve",
    response_model=ManagementReportRecord,
    summary="Formally approve a management review report",
)
def approve_management_report(
    report_id: str,
    payload: ApproveManagementReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: ManagementReviewReportingService = Depends(
        get_management_review_reporting_service
    ),
) -> ManagementReportRecord:
    _ensure_not_patient(current_user)
    return report_service.approve_report(current_user, report_id, payload)


@router.get(
    "/management-reports/{report_id}/export",
    response_model=Dict[str, Any],
    summary="Export structured, audited management report package",
)
def export_management_report(
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: ManagementReviewReportingService = Depends(
        get_management_review_reporting_service
    ),
) -> Dict[str, Any]:
    _ensure_not_patient(current_user)
    return report_service.export_report(current_user, report_id)


# =============================================================================
# 7. ANALYTICAL CONFIGURATION & VERSIONING
# =============================================================================

@router.post(
    "/configurations",
    response_model=AnalyticsConfigRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new draft analytical configuration version",
)
def create_analytics_configuration(
    payload: CreateAnalyticsConfigRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    config_service: AuditAnalyticsConfigService = Depends(
        get_audit_analytics_config_service
    ),
) -> AnalyticsConfigRecord:
    _ensure_not_patient(current_user)
    return config_service.create_config(current_user, payload)


@router.get(
    "/configurations",
    response_model=List[AnalyticsConfigRecord],
    summary="List analytical configuration versions",
)
def list_analytics_configurations(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    config_service: AuditAnalyticsConfigService = Depends(
        get_audit_analytics_config_service
    ),
) -> List[AnalyticsConfigRecord]:
    _ensure_not_patient(current_user)
    return config_service.list_configs(current_user)


@router.get(
    "/configurations/{configuration_id}",
    response_model=AnalyticsConfigRecord,
    summary="Get analytical configuration version details",
)
def get_analytics_configuration(
    configuration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    config_service: AuditAnalyticsConfigService = Depends(
        get_audit_analytics_config_service
    ),
) -> AnalyticsConfigRecord:
    _ensure_not_patient(current_user)
    return config_service.get_config(current_user, configuration_id)


@router.post(
    "/configurations/{configuration_id}/approve",
    response_model=AnalyticsConfigRecord,
    summary="Approve and activate an analytical configuration version",
)
def approve_analytics_configuration(
    configuration_id: str,
    payload: ApproveAnalyticsConfigRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    config_service: AuditAnalyticsConfigService = Depends(
        get_audit_analytics_config_service
    ),
) -> AnalyticsConfigRecord:
    _ensure_not_patient(current_user)
    return config_service.approve_config(current_user, configuration_id, payload)


@router.post(
    "/configurations/{configuration_id}/deprecate",
    response_model=AnalyticsConfigRecord,
    summary="Deprecate an analytical configuration version",
)
def deprecate_analytics_configuration(
    configuration_id: str,
    payload: DeprecateAnalyticsConfigRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    config_service: AuditAnalyticsConfigService = Depends(
        get_audit_analytics_config_service
    ),
) -> AnalyticsConfigRecord:
    _ensure_not_patient(current_user)
    return config_service.deprecate_config(current_user, configuration_id, payload)

"""Phase 74: Governance Change Adoption Reporting & Analytics Service.

Coordinates:
- Initiative-level adoption summaries
- Sustainability summaries with strict clinical safety notices
- Historical timeline of monitoring events
- Organization-wide adoption and operational drift reports
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_adoption_repository import (
    GovernanceChangeAdoptionRepository,
    get_governance_change_adoption_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.adoption_evidence_indicators import (
    EvidenceVerificationStatus,
    IndicatorOutcome,
)
from app.schemas.drift_sustainability_consequences import (
    AdoptionExceptionStatus,
    DriftDisposition,
    DriftSignalStatus,
    SustainabilityAssessmentStatus,
    SustainabilityDisposition,
)
from app.schemas.adoption_reporting import (
    AdoptionSummaryResponse,
    MonitoringHistoryResponse,
    OperationalDriftReportResponse,
    OrganizationAdoptionReportResponse,
    SustainabilitySummaryResponse,
)


class AdoptionReportingService:
    """Service governing adoption summaries, analytics, and executive reports."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def get_adoption_summary(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> AdoptionSummaryResponse:
        """Generates a structured adoption summary for an initiative."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        indicators = self.repo.list_indicators_for_registration(registration_id, current_user.tenant_id)
        evidence = self.repo.list_evidence_for_registration(registration_id, current_user.tenant_id, limit=1000)
        exceptions = self.repo.list_exceptions_for_registration(registration_id, current_user.tenant_id)
        drift = self.repo.list_drift_signals_for_registration(registration_id, current_user.tenant_id)

        achieved = sum(1 for i in indicators if i.outcome == IndicatorOutcome.ACHIEVED)
        in_progress = sum(1 for i in indicators if i.outcome == IndicatorOutcome.IN_PROGRESS)
        not_achieved = sum(1 for i in indicators if i.outcome == IndicatorOutcome.NOT_ACHIEVED)
        unable_to_det = sum(
            1 for i in indicators
            if i.outcome in [IndicatorOutcome.UNABLE_TO_DETERMINE, IndicatorOutcome.REQUIRES_REVIEW]
        )

        verified_evi = sum(1 for e in evidence if e.verification_status == EvidenceVerificationStatus.VERIFIED)
        pending_evi = sum(
            1 for e in evidence
            if e.verification_status in [EvidenceVerificationStatus.SUBMITTED, EvidenceVerificationStatus.PENDING_VERIFICATION]
        )
        rejected_evi = sum(1 for e in evidence if e.verification_status == EvidenceVerificationStatus.REJECTED)
        expired_evi = sum(1 for e in evidence if e.verification_status == EvidenceVerificationStatus.EXPIRED)

        active_exceptions = sum(1 for x in exceptions if x.status == AdoptionExceptionStatus.ACTIVE)
        open_drift = sum(1 for d in drift if d.status in [DriftSignalStatus.OPEN, DriftSignalStatus.UNDER_REVIEW])

        total_milestones = len(reg.adoption_milestones)
        completed_milestones = sum(1 for m in reg.adoption_milestones if m.completed)
        milestone_pct = (completed_milestones / total_milestones * 100.0) if total_milestones > 0 else 0.0

        return AdoptionSummaryResponse(
            registration_id=reg.registration_id,
            tenant_id=reg.tenant_id,
            title=reg.title,
            status=reg.status.value,
            current_baseline_version=reg.current_baseline_version,
            total_indicators=len(indicators),
            achieved_indicators=achieved,
            in_progress_indicators=in_progress,
            not_achieved_indicators=not_achieved,
            unable_to_determine_indicators=unable_to_det,
            total_evidence_items=len(evidence),
            verified_evidence_items=verified_evi,
            pending_evidence_items=pending_evi,
            rejected_evidence_items=rejected_evi,
            expired_evidence_items=expired_evi,
            active_exceptions_count=active_exceptions,
            open_drift_signals_count=open_drift,
            milestone_progress_pct=round(milestone_pct, 1),
            disclosures_and_limitations=reg.limitations_disclosed,
        )

    def get_sustainability_summary(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> SustainabilitySummaryResponse:
        """Generates a sustainability summary for an initiative."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        assessments = self.repo.list_sustainability_assessments_for_registration(
            registration_id, current_user.tenant_id
        )
        latest = assessments[0] if assessments else None

        concerns_count = 0
        if latest:
            if latest.disposition in [
                SustainabilityDisposition.SUSTAINABILITY_CONCERN,
                SustainabilityDisposition.NOT_SUSTAINED,
                SustainabilityDisposition.REQUIRES_ESCALATION,
            ]:
                concerns_count = 1

        return SustainabilitySummaryResponse(
            registration_id=reg.registration_id,
            tenant_id=reg.tenant_id,
            latest_assessment_id=latest.assessment_id if latest else None,
            latest_disposition=latest.disposition.value if latest else None,
            assessment_status=latest.status.value if latest else None,
            evaluated_dimensions=latest.dimension_scores if latest else {},
            active_concerns_count=concerns_count,
        )

    def get_monitoring_history(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> MonitoringHistoryResponse:
        """Retrieves the complete historical timeline of monitoring events."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        events = self.repo.get_timeline_events(registration_id)
        return MonitoringHistoryResponse(
            registration_id=reg.registration_id,
            tenant_id=reg.tenant_id,
            events_count=len(events),
            events=events,
        )

    def get_organization_adoption_report(
        self, current_user: AuthenticatedUserContext
    ) -> OrganizationAdoptionReportResponse:
        """Generates cross-initiative adoption reporting for executive oversight."""
        now_iso = datetime.now(timezone.utc).isoformat()
        registrations = self.repo.list_registrations(tenant_id=current_user.tenant_id, limit=1000)

        active_count = sum(1 for r in registrations if r.status.value == "ACTIVE_MONITORING")
        concluded_count = sum(1 for r in registrations if r.status.value == "CONCLUDED")

        unresolved_drift_count = 0
        sustainability_concerns_count = 0

        for r in registrations:
            drift = self.repo.list_drift_signals_for_registration(r.registration_id, current_user.tenant_id)
            if any(d.status in [DriftSignalStatus.OPEN, DriftSignalStatus.UNDER_REVIEW] for d in drift):
                unresolved_drift_count += 1

            assessments = self.repo.list_sustainability_assessments_for_registration(
                r.registration_id, current_user.tenant_id
            )
            if assessments and assessments[0].disposition in [
                SustainabilityDisposition.SUSTAINABILITY_CONCERN,
                SustainabilityDisposition.NOT_SUSTAINED,
                SustainabilityDisposition.REQUIRES_ESCALATION,
            ]:
                sustainability_concerns_count += 1

        return OrganizationAdoptionReportResponse(
            tenant_id=current_user.tenant_id,
            report_generated_at=now_iso,
            total_registered_initiatives=len(registrations),
            active_monitoring_count=active_count,
            concluded_count=concluded_count,
            initiatives_with_unresolved_drift=unresolved_drift_count,
            initiatives_with_sustainability_concerns=sustainability_concerns_count,
            department_adoption_rates={},
            facility_adoption_rates={},
        )

    def get_operational_drift_report(
        self, current_user: AuthenticatedUserContext
    ) -> OperationalDriftReportResponse:
        """Generates organization-wide drift signals report."""
        now_iso = datetime.now(timezone.utc).isoformat()
        all_signals = self.repo.list_all_drift_signals(tenant_id=current_user.tenant_id)

        open_signals = sum(1 for s in all_signals if s.status == DriftSignalStatus.OPEN)
        under_review = sum(1 for s in all_signals if s.status == DriftSignalStatus.UNDER_REVIEW)
        confirmed = sum(1 for s in all_signals if s.disposition == DriftDisposition.CONFIRMED_DEVIATION)
        false_alarms = sum(1 for s in all_signals if s.disposition == DriftDisposition.FALSE_ALARM)
        approved_exc = sum(1 for s in all_signals if s.disposition == DriftDisposition.APPROVED_EXCEPTION)

        class_counts: Dict[str, int] = {}
        for s in all_signals:
            c = s.classification.value
            class_counts[c] = class_counts.get(c, 0) + 1

        return OperationalDriftReportResponse(
            tenant_id=current_user.tenant_id,
            report_generated_at=now_iso,
            total_drift_signals=len(all_signals),
            open_signals=open_signals,
            under_review_signals=under_review,
            confirmed_deviations=confirmed,
            false_alarms=false_alarms,
            approved_exceptions=approved_exc,
            signals_by_classification=class_counts,
        )

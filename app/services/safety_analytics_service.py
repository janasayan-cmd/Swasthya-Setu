"""Phase 61: Safety Analytics Service Orchestrator.

Main service orchestrating longitudinal surveillance analytics, temporal aggregation,
signal recurrence, trend evaluation, concentration analysis, cross-signal correlation,
pattern detection, governed risk intelligence, human review, and authoritative routing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_analytics_repository import (
    SafetyAnalyticsRepository,
    get_safety_analytics_repository,
)
from app.schemas.safety_analytics import (
    AnalysisHistoryEntry,
    AnalysisLifecycleState,
    AnalysisScope,
    AnalysisType,
    AnalyticalEvidenceReference,
    AnalyticalUncertaintyState,
    AnalyticsRoutingDestination,
    CreateAnalysisRequest,
    HumanAnalyticsReviewDecision,
    ObservationWindow,
    SafetyAnalysisRecord,
)
from app.services.safety_analytics_concentration_service import (
    SafetyAnalyticsConcentrationService,
    get_safety_analytics_concentration_service,
)
from app.services.safety_analytics_correlation_service import (
    SafetyAnalyticsCorrelationService,
    get_safety_analytics_correlation_service,
)
from app.services.safety_analytics_distribution_service import (
    SafetyAnalyticsDistributionService,
    get_safety_analytics_distribution_service,
)
from app.services.safety_analytics_input_service import (
    SafetyAnalyticsInputService,
    get_safety_analytics_input_service,
)
from app.services.safety_analytics_pattern_service import (
    SafetyAnalyticsPatternService,
    get_safety_analytics_pattern_service,
)
from app.services.safety_analytics_recurrence_service import (
    SafetyAnalyticsRecurrenceService,
    get_safety_analytics_recurrence_service,
)
from app.services.safety_analytics_review_service import (
    SafetyAnalyticsReviewService,
    get_safety_analytics_review_service,
)
from app.services.safety_analytics_routing_service import (
    SafetyAnalyticsRoutingService,
    get_safety_analytics_routing_service,
)
from app.services.safety_analytics_trend_service import (
    SafetyAnalyticsTrendService,
    get_safety_analytics_trend_service,
)
from app.services.safety_risk_indicator_service import (
    SafetyRiskIndicatorService,
    get_safety_risk_indicator_service,
)


class SafetyAnalyticsService:
    """End-to-end coordinator for Phase 61 safety surveillance analytics."""

    def __init__(
        self,
        repository: Optional[SafetyAnalyticsRepository] = None,
        input_service: Optional[SafetyAnalyticsInputService] = None,
        recurrence_service: Optional[SafetyAnalyticsRecurrenceService] = None,
        trend_service: Optional[SafetyAnalyticsTrendService] = None,
        distribution_service: Optional[SafetyAnalyticsDistributionService] = None,
        concentration_service: Optional[SafetyAnalyticsConcentrationService] = None,
        correlation_service: Optional[SafetyAnalyticsCorrelationService] = None,
        pattern_service: Optional[SafetyAnalyticsPatternService] = None,
        risk_indicator_service: Optional[SafetyRiskIndicatorService] = None,
        review_service: Optional[SafetyAnalyticsReviewService] = None,
        routing_service: Optional[SafetyAnalyticsRoutingService] = None,
    ) -> None:
        self.repo = repository or get_safety_analytics_repository()
        self.input_svc = input_service or get_safety_analytics_input_service()
        self.recurrence_svc = recurrence_service or get_safety_analytics_recurrence_service()
        self.trend_svc = trend_service or get_safety_analytics_trend_service()
        self.distribution_svc = distribution_service or get_safety_analytics_distribution_service()
        self.concentration_svc = concentration_service or get_safety_analytics_concentration_service()
        self.correlation_svc = correlation_service or get_safety_analytics_correlation_service()
        self.pattern_svc = pattern_service or get_safety_analytics_pattern_service()
        self.risk_indicator_svc = risk_indicator_service or get_safety_risk_indicator_service()
        self.review_svc = review_service or get_safety_analytics_review_service()
        self.routing_svc = routing_service or get_safety_analytics_routing_service()

    def create_analysis(
        self,
        request: CreateAnalysisRequest,
        organization_id: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyAnalysisRecord:
        """Create and initialize a new safety analytics context."""
        # 1. Idempotency Check
        if request.idempotency_key:
            existing = self.repo.check_idempotency(request.idempotency_key, organization_id)
            if existing:
                return existing

        scope = request.scope or AnalysisScope(organization_id=organization_id)
        if scope.organization_id != organization_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Cannot create surveillance analysis for another organization scope",
                status_code=403,
            )

        window = request.observation_window or ObservationWindow()
        anl_id = request.analysis_id or f"anl-{uuid.uuid4().hex[:10]}"

        # Validate input signals if provided at creation
        raw_sigs = request.signals or []
        eligible, excluded = self.input_svc.filter_and_validate_signals(
            raw_signals=raw_sigs, scope=scope, window=window
        )

        record = SafetyAnalysisRecord(
            analysis_id=anl_id,
            organization_id=organization_id,
            scope=scope,
            observation_window=window,
            lifecycle_state=AnalysisLifecycleState.CREATED,
            analysis_types=request.analysis_types or [AnalysisType.FULL],
            eligible_signals=eligible,
            excluded_signals=excluded,
            idempotency_key=request.idempotency_key,
            version=request.version,
        )

        # Audit history entry
        record.history.append(
            AnalysisHistoryEntry(
                action="ANALYSIS_CREATED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=AnalysisLifecycleState.CREATED.value,
                details={"purpose": request.purpose, "initial_signals_count": len(raw_sigs)},
            )
        )

        self.repo.save(record)
        return record

    def execute_analysis(
        self,
        analysis_id: str,
        actor_id: str,
        actor_role: str,
        analysis_types: Optional[List[AnalysisType]] = None,
    ) -> SafetyAnalysisRecord:
        """Execute the multi-stage surveillance analytics pipeline on an analysis record."""
        record = self.repo.get(analysis_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
                message=f"Safety analysis {analysis_id} not found",
                status_code=404,
            )

        if record.lifecycle_state == AnalysisLifecycleState.IN_PROGRESS:
            raise AppException(
                code=ErrorCode.ANALYSIS_ALREADY_RUNNING,
                message=f"Analysis {analysis_id} is already executing",
                status_code=409,
            )

        record.lifecycle_state = AnalysisLifecycleState.IN_PROGRESS

        # 1. Pipeline Execution
        signals = record.eligible_signals
        window = record.observation_window

        # Recurrence
        record.recurrence_findings = self.recurrence_svc.evaluate_recurrence(signals)

        # Trends
        record.trend_findings = self.trend_svc.evaluate_trends(signals, window)

        # Distribution
        record.distribution_findings = self.distribution_svc.evaluate_distribution(signals)

        # Concentration
        record.concentration_findings = self.concentration_svc.evaluate_concentration(signals)

        # Correlation
        record.correlation_findings = self.correlation_svc.evaluate_correlations(signals)

        # Pattern Detection
        record.pattern_findings = self.pattern_svc.detect_patterns(signals, window)

        # Emerging Risk Indicators
        record.risk_indicators = self.risk_indicator_svc.evaluate_risk_indicators(
            patterns=record.pattern_findings,
            trends=record.trend_findings,
            recurrences=record.recurrence_findings,
            concentrations=record.concentration_findings,
        )

        # 2. Uncertainty Quantification
        if len(signals) == 0:
            record.overall_uncertainty = AnalyticalUncertaintyState.INSUFFICIENT_DATA
        elif any(s.uncertainty == "HIGH_UNCERTAINTY" for s in signals):
            record.overall_uncertainty = AnalyticalUncertaintyState.HIGH_UNCERTAINTY
        elif len(signals) < 3:
            record.overall_uncertainty = AnalyticalUncertaintyState.MODERATE_UNCERTAINTY
        else:
            record.overall_uncertainty = AnalyticalUncertaintyState.LOW_UNCERTAINTY

        # 3. Evidence Attachment
        record.evidence_references.append(
            AnalyticalEvidenceReference(
                evidence_type="ANALYTICAL_EXECUTION_RUN",
                reference_uri=f"run://{record.analysis_id}/{datetime.now(timezone.utc).isoformat()}",
                description=f"Generated findings: {len(record.pattern_findings)} patterns, {len(record.risk_indicators)} risk indicators.",
            )
        )

        # 4. Review & Escalation Flags
        has_risk_indicators = len(record.risk_indicators) > 0
        has_patterns = len(record.pattern_findings) > 0
        record.requires_human_review = has_risk_indicators or has_patterns
        record.requires_escalation = any(
            ind.governed_severity == "CRITICAL" for ind in record.risk_indicators
        )

        if record.requires_escalation:
            record.lifecycle_state = AnalysisLifecycleState.ESCALATION_REQUIRED
        elif record.requires_human_review:
            record.lifecycle_state = AnalysisLifecycleState.REVIEW_REQUIRED
        else:
            record.lifecycle_state = AnalysisLifecycleState.COMPLETED

        record.completed_at = datetime.now(timezone.utc)

        # History
        record.history.append(
            AnalysisHistoryEntry(
                action="ANALYSIS_EXECUTED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=record.lifecycle_state.value,
                details={
                    "eligible_count": len(signals),
                    "patterns_count": len(record.pattern_findings),
                    "risk_indicators_count": len(record.risk_indicators),
                },
            )
        )

        return self.repo.save(record)

    def reanalyze(
        self,
        analysis_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
        updated_version: Optional[str] = None,
    ) -> SafetyAnalysisRecord:
        """Re-run analysis under versioned conditions and mark previous findings updated."""
        record = self.repo.get(analysis_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
                message=f"Analysis {analysis_id} not found",
                status_code=404,
            )

        if updated_version:
            record.version = updated_version
            record.scope.version = updated_version

        record.history.append(
            AnalysisHistoryEntry(
                action="REANALYSIS_REQUESTED",
                actor_id=actor_id,
                actor_role=actor_role,
                previous_state=record.lifecycle_state.value,
                new_state=AnalysisLifecycleState.IN_PROGRESS.value,
                details={"reason": reason, "updated_version": updated_version},
            )
        )

        return self.execute_analysis(
            analysis_id=analysis_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )

    def submit_review(
        self,
        analysis_id: str,
        reviewer_id: str,
        reviewer_role: str,
        decision: HumanAnalyticsReviewDecision,
        reason: str,
        resulting_routes: Optional[List[AnalyticsRoutingDestination]] = None,
        is_ai: bool = False,
    ) -> SafetyAnalysisRecord:
        """Submit human review decision on an analytical record."""
        record = self.repo.get(analysis_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
                message=f"Analysis {analysis_id} not found",
                status_code=404,
            )

        review_rec = self.review_svc.submit_review(
            analysis=record,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            reason=reason,
            resulting_routes=resulting_routes,
            is_ai=is_ai,
        )

        record.history.append(
            AnalysisHistoryEntry(
                action="REVIEW_SUBMITTED",
                actor_id=reviewer_id,
                actor_role=reviewer_role,
                new_state=record.lifecycle_state.value,
                details={
                    "decision": decision.value,
                    "reason": reason,
                    "review_id": review_rec.review_id,
                },
            )
        )

        return self.repo.save(record)

    def route_findings(
        self,
        analysis_id: str,
        destinations: List[AnalyticsRoutingDestination],
        actor_id: str,
        actor_role: str,
        reason: str,
        target_reference: Optional[str] = None,
    ) -> SafetyAnalysisRecord:
        """Route analytical findings to authoritative downstream destinations."""
        record = self.repo.get(analysis_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
                message=f"Analysis {analysis_id} not found",
                status_code=404,
            )

        routing_recs = self.routing_svc.execute_routing(
            analysis=record,
            destinations=destinations,
            actor_id=actor_id,
            reason=reason,
            target_reference=target_reference,
        )

        record.history.append(
            AnalysisHistoryEntry(
                action="FINDINGS_ROUTED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=record.lifecycle_state.value,
                details={
                    "destinations": [d.value for d in destinations],
                    "routing_count": len(routing_recs),
                },
            )
        )

        return self.repo.save(record)

    def request_reassessment(
        self,
        analysis_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
        signal_ids: Optional[List[str]] = None,
    ) -> SafetyAnalysisRecord:
        """Request Phase 60 reassessment for signals analyzed in this run."""
        record = self.repo.get(analysis_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
                message=f"Analysis {analysis_id} not found",
                status_code=404,
            )

        record.lifecycle_state = AnalysisLifecycleState.REASSESSMENT_REQUIRED
        record.requires_reassessment = True

        record.history.append(
            AnalysisHistoryEntry(
                action="REASSESSMENT_REQUESTED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=AnalysisLifecycleState.REASSESSMENT_REQUIRED.value,
                details={"reason": reason, "target_signals": signal_ids or []},
            )
        )

        return self.repo.save(record)


_safety_analytics_service: Optional[SafetyAnalyticsService] = None


def get_safety_analytics_service() -> SafetyAnalyticsService:
    global _safety_analytics_service
    if _safety_analytics_service is None:
        _safety_analytics_service = SafetyAnalyticsService()
    return _safety_analytics_service

"""Phase 50: Safety Learning Orchestration Service.

Coordinates safety learning jobs, source retrieval (Phase 49 incidents,
Phase 48 safety gates, Phase 47 decision traces), trend metrics calculation,
pattern candidate detection, and candidate recommendation generation.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import (
    SafetyLearningAccessDeniedException,
    SafetyLearningIdempotencyConflictException,
    SafetyLearningInvalidScopeException,
    SafetyLearningInvalidTimeWindowException,
    SafetyLearningNotFoundException,
)
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.repositories.safety_learning_repository import (
    SafetyLearningRepository,
    safety_learning_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.safety_analysis import (
    AnalysisScopeType,
    AnalysisStatus,
    AnalysisType,
    SafetyAnalysisCreateRequest,
    SafetyAnalysisJob,
    SafetyAnalysisResult,
    TrendMetric,
)
from app.schemas.safety_recommendation import RecommendationType
from app.services.audit_service import AuditService, audit_service
from app.services.safety_pattern_service import (
    SafetyPatternService,
    safety_pattern_service,
)
from app.services.safety_recommendation_service import (
    SafetyRecommendationService,
    safety_recommendation_service,
)
from app.services.safety_trend_service import (
    SafetyTrendService,
    safety_trend_service,
)

logger = logging.getLogger("app.safety_learning_service")


class SafetyLearningService:
    """Master orchestration service for Phase 50 Safety Learning."""

    def __init__(
        self,
        learning_repo: Optional[SafetyLearningRepository] = None,
        incident_repo: Optional[SafetyIncidentRepository] = None,
        trend_svc: Optional[SafetyTrendService] = None,
        pattern_svc: Optional[SafetyPatternService] = None,
        rec_svc: Optional[SafetyRecommendationService] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.learning_repo = learning_repo or safety_learning_repository
        self.incident_repo = incident_repo or safety_incident_repository
        self.trend_service = trend_svc or safety_trend_service
        self.pattern_service = pattern_svc or safety_pattern_service
        self.recommendation_service = rec_svc or safety_recommendation_service
        self.audit_service = audit_svc or audit_service

    def _resolve_time_window(self, request: SafetyAnalysisCreateRequest) -> tuple[datetime, datetime]:
        """Resolve absolute start and end times from request or relative window."""
        now = datetime.now(timezone.utc)
        if request.start_time and request.end_time:
            if request.start_time >= request.end_time:
                raise SafetyLearningInvalidTimeWindowException("start_time must be strictly before end_time.")
            return request.start_time, request.end_time

        rel = (request.relative_window or "LAST_30_DAYS").upper()
        if rel == "LAST_24_HOURS":
            start = now - timedelta(hours=24)
        elif rel == "LAST_7_DAYS":
            start = now - timedelta(days=7)
        elif rel == "LAST_90_DAYS":
            start = now - timedelta(days=90)
        else:  # LAST_30_DAYS default
            start = now - timedelta(days=30)

        return start, now

    async def request_analysis(
        self,
        request: SafetyAnalysisCreateRequest,
        requested_by_id: str,
        requested_by_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SafetyAnalysisJob:
        """Create and execute or queue a safety learning analysis."""
        # 1. Idempotency check
        if request.idempotency_key:
            existing = self.learning_repo.find_job_by_idempotency_key(request.idempotency_key)
            if existing:
                return existing

        start_time, end_time = self._resolve_time_window(request)

        job = SafetyAnalysisJob(
            analysis_type=request.analysis_type,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            start_time=start_time,
            end_time=end_time,
            requested_by_id=requested_by_id,
            requested_by_role=requested_by_role,
            organization_id=organization_id,
            status=AnalysisStatus.RUNNING,
            filters=request.filters,
            idempotency_key=request.idempotency_key,
        )
        self.learning_repo.save_job(job)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.SAFETY_LEARNING_ANALYSIS_REQUESTED,
                    outcome="ALLOW",
                    actor_id=requested_by_id,
                    action=f"safety_learning:request:{request.analysis_type.value}",
                    resource_type="safety_learning_job",
                    resource_id=job.id,
                    metadata={
                        "job_id": job.id,
                        "analysis_type": request.analysis_type.value,
                        "scope_type": request.scope_type.value,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for analysis request %s: %s", job.id, ex)

        # 2. Execute analysis synchronously for fast in-memory execution
        try:
            result = self._execute_analysis_job(job)
            job.status = AnalysisStatus.COMPLETED
            job.result = result
            job.updated_at = datetime.now(timezone.utc)
            self.learning_repo.save_job(job)

            if self.audit_service:
                try:
                    await self.audit_service.record(
                        event_type=AuditEventType.SAFETY_LEARNING_ANALYSIS_COMPLETED,
                        outcome="ALLOW",
                        actor_id=requested_by_id,
                        action=f"safety_learning:completed:{request.analysis_type.value}",
                        resource_type="safety_learning_result",
                        resource_id=result.id,
                        metadata={
                            "job_id": job.id,
                            "result_id": result.id,
                            "patterns_found": len(result.detected_pattern_ids),
                        },
                        request_id=request_id,
                    )
                except Exception as ex:
                    logger.warning("Audit recording failed for analysis completion %s: %s", job.id, ex)

        except Exception as e:
            logger.exception("Analysis execution failed for job %s: %s", job.id, e)
            job.status = AnalysisStatus.FAILED
            job.error_message = str(e)
            job.updated_at = datetime.now(timezone.utc)
            self.learning_repo.save_job(job)

        return job

    def _execute_analysis_job(self, job: SafetyAnalysisJob) -> SafetyAnalysisResult:
        """Execute analytical queries across Phase 49 incidents and Phase 48 safety gates."""
        incidents = self.incident_repo.list_incidents()
        window_incidents = [
            i for i in incidents
            if job.start_time <= i.occurred_at <= job.end_time
        ]

        # Calculate incident trend metric
        total_count = len(window_incidents)
        trend_metric = self.trend_service.calculate_trend_metric(
            metric_name="incident_count",
            count=total_count,
            time_window_label=f"{job.start_time.date()} to {job.end_time.date()}",
        )

        metrics: List[TrendMetric] = [trend_metric]

        # Candidate pattern detection
        detected_patterns = self.pattern_service.detect_patterns(
            start_time=job.start_time,
            end_time=job.end_time,
        )
        pattern_ids = [p.id for p in detected_patterns]

        # Generate candidate recommendations if patterns detected
        rec_ids: List[str] = []
        for pat in detected_patterns:
            rec = self.recommendation_service.create_recommendation(
                recommendation_type=RecommendationType.ADD_VALIDATION_RULE,
                title=f"Preventive validation for {pat.affected_subsystem}",
                description=f"Automated candidate recommendation following detection of pattern '{pat.title}'.",
                rationale_summary=f"Historical analysis identified {pat.occurrence_count} incidents of type {pat.affected_subsystem}.",
                affected_subsystem=pat.affected_subsystem,
                analysis_id=job.id,
                pattern_id=pat.id,
                evidence_references=pat.evidence_references,
            )
            rec_ids.append(rec.id)

        result = SafetyAnalysisResult(
            analysis_id=job.id,
            analysis_type=job.analysis_type,
            scope_type=job.scope_type,
            scope_id=job.scope_id,
            status=AnalysisStatus.COMPLETED,
            metrics=metrics,
            detected_pattern_ids=pattern_ids,
            generated_recommendation_ids=rec_ids,
            evidence_count=total_count,
            sources_included=["clinical_safety_incidents", "safety_signals"],
            sources_unavailable=[],
            is_complete=True,
            limitations=[
                "Analytical correlation does not imply clinical causation.",
                "Observations restricted to reported incidents and safety signals.",
            ],
            generated_at=datetime.now(timezone.utc),
        )
        return self.learning_repo.save_result(result)

    def get_job(self, job_id: str) -> SafetyAnalysisJob:
        """Retrieve analysis job or raise SafetyLearningNotFoundException."""
        job = self.learning_repo.get_job(job_id)
        if not job:
            raise SafetyLearningNotFoundException(f"Safety learning analysis job '{job_id}' not found.")
        return job

    def get_result(self, analysis_id: str) -> SafetyAnalysisResult:
        """Retrieve analysis result for job."""
        res = self.learning_repo.get_result_by_analysis_id(analysis_id)
        if not res:
            raise SafetyLearningNotFoundException(f"Result for analysis '{analysis_id}' not found.")
        return res


# Global singleton
safety_learning_service = SafetyLearningService()

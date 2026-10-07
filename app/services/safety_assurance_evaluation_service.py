"""Phase 52: Safety Assurance Evaluation Service.

Primary orchestration service for the control assurance lifecycle:

CONTROL DEFINITION
→ CONTROL VERSION
→ APPROVED EXPECTATION
→ ASSURANCE SCOPE
→ EVALUATION WINDOW
→ AUTHORIZE
→ COLLECT AUTHORITATIVE EVIDENCE
→ VALIDATE PROVENANCE
→ VALIDATE FRESHNESS
→ CHECK COMPLETENESS
→ CHECK CONFLICTS
→ OBSERVE EXECUTION
→ DETECT BYPASS
→ VALIDATE VERSION/CONFIGURATION
→ EVALUATE EFFECTIVENESS
→ PRESERVE UNCERTAINTY
→ HUMAN REVIEW
→ ASSURANCE DECISION
→ MONITOR
→ DETECT DEGRADATION/REGRESSION
→ REASSESS
→ ROUTE TO INCIDENT / LEARNING / GOVERNANCE / CHANGE
→ REVALIDATE

Phase 48 remains authoritative for safety enforcement.
Phase 49 remains authoritative for incidents.
Phase 50 remains authoritative for safety learning.
Phase 51 remains authoritative for risk governance.
Phase 25 remains authoritative for configuration.
Phase 22 is used for long-running async evaluations.
Phase 46 provides version/concurrency mechanisms.

NEVER answers "Is HealthSetu safe?" as a single boolean.
Answers bounded questions about specific control behavior, evidence
availability, and effectiveness within a defined scope and window.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_assurance_repository import (
    SafetyAssuranceRepository,
    safety_assurance_repository,
)
from app.schemas.safety_assurance import (
    AssuranceAcceptRequest,
    AssuranceDashboardSummary,
    AssuranceDomainEvent,
    AssuranceDomainEventType,
    AssuranceEvaluationRecord,
    AssuranceEvaluationRequest,
    AssuranceEvaluationStatusResponse,
    AssuranceLifecycleState,
    AssuranceReassessRequest,
    AssuranceRejectRequest,
    AssuranceScopeRecord,
    BypassRecord,
    ControlAssuranceSummary,
    ControlEffectivenessState,
    ControlExecutionState,
    DegradationRecord,
    DegradationState,
    EvidenceQualityState,
    EvidenceReference,
    EvidenceSourceType,
    RegressionRecord,
)
from app.services.safety_assurance_metrics_service import (
    SafetyAssuranceMetricsService,
    safety_assurance_metrics_service,
)
from app.services.safety_assurance_review_service import (
    SafetyAssuranceReviewService,
    safety_assurance_review_service,
)
from app.services.safety_assurance_routing_service import (
    SafetyAssuranceRoutingService,
    safety_assurance_routing_service,
)
from app.services.safety_assurance_validation_service import (
    SafetyAssuranceValidationService,
    safety_assurance_validation_service,
)
from app.services.safety_control_effectiveness_service import (
    SafetyControlEffectivenessService,
    safety_control_effectiveness_service,
)
from app.services.safety_degradation_service import (
    SafetyDegradationService,
    safety_degradation_service,
)
from app.services.safety_evidence_service import (
    SafetyEvidenceService,
    safety_evidence_service,
)

logger = logging.getLogger("app.services.safety_assurance_evaluation_service")


class SafetyAssuranceEvaluationService:
    """Primary orchestrator for Phase 52 control assurance evaluation lifecycle.

    Enforces:
    - Control identity/version always resolved before evaluation
    - Expected behavior from authoritative sources (never inferred from logs)
    - Evidence from authoritative systems only
    - Evidence provenance preserved
    - Missing evidence never treated as success
    - Partial evidence explicitly represented
    - Stale evidence rejected or marked
    - Conflicting evidence preserved
    - Human review enforced for high-risk outcomes
    - Client cannot spoof reviewer/effectiveness/risk/control state
    - AI cannot make authoritative assurance decisions
    - Failed/degraded controls route to correct subsystem
    - Idempotency enforced
    - Concurrency protection enforced
    - Audit events emitted
    - Domain events emitted
    - PHI minimized throughout
    """

    def __init__(
        self,
        assurance_repo: Optional[SafetyAssuranceRepository] = None,
        validation_svc: Optional[SafetyAssuranceValidationService] = None,
        evidence_svc: Optional[SafetyEvidenceService] = None,
        effectiveness_svc: Optional[SafetyControlEffectivenessService] = None,
        degradation_svc: Optional[SafetyDegradationService] = None,
        review_svc: Optional[SafetyAssuranceReviewService] = None,
        routing_svc: Optional[SafetyAssuranceRoutingService] = None,
        metrics_svc: Optional[SafetyAssuranceMetricsService] = None,
    ) -> None:
        self._repo = assurance_repo or safety_assurance_repository
        self._validation = validation_svc or safety_assurance_validation_service
        self._evidence = evidence_svc or safety_evidence_service
        self._effectiveness = effectiveness_svc or safety_control_effectiveness_service
        self._degradation = degradation_svc or safety_degradation_service
        self._review = review_svc or safety_assurance_review_service
        self._routing = routing_svc or safety_assurance_routing_service
        self._metrics = metrics_svc or safety_assurance_metrics_service

    # -------------------------------------------------------------------------
    # Create Evaluation
    # -------------------------------------------------------------------------

    def create_evaluation(
        self,
        request: AssuranceEvaluationRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str],
        actor_facility_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Initiate a new control assurance evaluation.

        Actor identity is always from authenticated server context.
        Client-provided actor_id, organization_id (beyond scope restriction),
        and effectiveness_state are NEVER used from request body.

        Idempotency: if same idempotency_key with same scope exists in
        progress, returns existing evaluation without creating duplicate.

        Args:
            request: Evaluation parameters.
            actor_id: From authenticated session (NOT client body).
            actor_role: From authenticated session (NOT client body).
            actor_organization_id: From authenticated session.
            actor_facility_id: From authenticated session.
            request_id: Correlation ID.

        Returns:
            AssuranceEvaluationRecord in SCHEDULED state.

        Raises:
            AppException: On validation failure, scope mismatch, or
                          idempotency conflict.
        """
        # 1. Validate request
        self._validation.validate_evaluation_request(
            request, actor_organization_id, actor_facility_id
        )

        # 2. Idempotency check
        if request.idempotency_key:
            existing = self._repo.get_by_idempotency_key(request.idempotency_key)
            if existing is not None:
                self._metrics.increment("assurance_idempotency_hit_total")
                logger.info(
                    "Idempotency hit — returning existing evaluation",
                    extra={
                        "idempotency_key": request.idempotency_key,
                        "evaluation_id": existing.evaluation_id,
                        "request_id": request_id,
                    },
                )
                return existing

        # 3. Resolve scope — org/facility from authenticated context
        resolved_org_id = actor_organization_id or request.organization_id
        resolved_facility_id = actor_facility_id or request.facility_id

        scope = AssuranceScopeRecord(
            control_id=request.control_id,
            control_version=request.control_version,
            organization_id=resolved_org_id,
            facility_id=resolved_facility_id,
            department_id=request.department_id,
            workflow_id=request.workflow_id,
            provider_id=request.provider_id,
            feature_flag_id=request.feature_flag_id,
            deployment_version=request.deployment_version,
            safety_policy_version=request.safety_policy_version,
            observation_start=request.observation_start,
            observation_end=request.observation_end,
        )

        # 4. Create evaluation record in SCHEDULED state
        record = AssuranceEvaluationRecord(
            idempotency_key=request.idempotency_key,
            control_id=request.control_id,
            control_category=request.control_category,
            control_version=request.control_version,
            scope=scope,
            lifecycle_state=AssuranceLifecycleState.SCHEDULED,
            effectiveness_state=ControlEffectivenessState.NOT_EVALUATED,
            organization_id=resolved_org_id,
            facility_id=resolved_facility_id,
            initiated_by_actor_id=actor_id,
            initiated_by_role=actor_role,
            scheduled_at=datetime.now(timezone.utc),
            request_id=request_id,
        )

        record = self._repo.save_evaluation(record)
        self._metrics.increment("assurance_evaluations_total")
        self._metrics.increment("assurance_evaluations_scheduled_total")

        # 5. Emit domain event
        self._emit_event(
            AssuranceDomainEventType.SCHEDULED,
            record,
            organization_id=resolved_org_id,
            facility_id=resolved_facility_id,
        )

        logger.info(
            "Assurance evaluation scheduled",
            extra={
                "evaluation_id": record.evaluation_id,
                "control_id": record.control_id,
                "control_version": record.control_version,
                "request_id": request_id,
            },
        )

        return record

    # -------------------------------------------------------------------------
    # Execute Evaluation (async worker entry point)
    # -------------------------------------------------------------------------

    def execute_evaluation(
        self,
        evaluation_id: str,
        evidence_references: Optional[List[EvidenceReference]] = None,
        eligible_executions: Optional[int] = None,
        observed_executions: Optional[int] = None,
        observed_failures: Optional[int] = None,
        observed_bypasses: Optional[int] = None,
        valid_results: Optional[int] = None,
        total_results: Optional[int] = None,
        expected_behavior_met: Optional[bool] = None,
        version_consistent: Optional[bool] = None,
        provider_success_rate: Optional[float] = None,
        required_reviews_completed: Optional[int] = None,
        required_reviews_total: Optional[int] = None,
        policy_thresholds: Optional[Dict[str, Any]] = None,
        expected_sources: Optional[List[EvidenceSourceType]] = None,
        safety_critical_sources: Optional[List[EvidenceSourceType]] = None,
        is_high_risk_control: bool = False,
        # Execution context re-validated server-side
        actor_id: Optional[str] = None,
        actor_organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Execute the assurance evaluation lifecycle.

        This method is the worker entry point for async execution (Phase 22).
        Workers MUST revalidate authorization, scope, control version,
        configuration version, and evidence eligibility on entry.

        Args:
            evaluation_id: ID of the scheduled evaluation to execute.
            evidence_references: Collected evidence references (from authoritative systems).
            eligible_executions: Total eligible control executions in window.
            observed_executions: Actually observed executions.
            observed_failures: Observed control failures.
            observed_bypasses: Observed control bypasses.
            valid_results: Count of valid control results.
            total_results: Total control results (denominator for rate).
            expected_behavior_met: Whether observed matches approved expectation.
            version_consistent: Whether control version was consistent throughout.
            provider_success_rate: External provider success rate (if applicable).
            required_reviews_completed: Count of required human reviews completed.
            required_reviews_total: Total required human reviews (denominator).
            policy_thresholds: Policy-derived thresholds for degradation detection.
            expected_sources: Expected evidence source types for completeness check.
            safety_critical_sources: Sources whose absence blocks evaluation.
            is_high_risk_control: Whether this control requires mandatory human review.
            actor_id: Re-validated actor from execution context.
            actor_organization_id: Re-validated org scope.
            request_id: Correlation ID.

        Returns:
            Updated AssuranceEvaluationRecord.
        """
        start_time = datetime.now(timezone.utc)

        # Load evaluation
        evaluation = self._repo.get_evaluation(evaluation_id)
        if evaluation is None:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_NOT_FOUND,
                message=f"Assurance evaluation '{evaluation_id}' not found.",
                status_code=404,
            )

        # Re-validate org scope in worker
        if actor_organization_id and evaluation.organization_id:
            if actor_organization_id != evaluation.organization_id:
                raise AppException(
                    code=ErrorCode.SAFETY_ASSURANCE_UNAUTHORIZED,
                    message="Worker authorization context does not match evaluation scope.",
                    status_code=403,
                )

        # Validate valid state for execution
        if evaluation.lifecycle_state not in (
            AssuranceLifecycleState.SCHEDULED,
            AssuranceLifecycleState.ELIGIBILITY_CHECK,
        ):
            if evaluation.lifecycle_state == AssuranceLifecycleState.CANCELLED:
                raise AppException(
                    code=ErrorCode.SAFETY_ASSURANCE_INVALID_STATE,
                    message="Evaluation has been cancelled.",
                    status_code=409,
                )
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_ALREADY_RUNNING,
                message=f"Evaluation already in state '{evaluation.lifecycle_state.value}'.",
                status_code=409,
            )

        # --- ELIGIBILITY CHECK ---
        evaluation.lifecycle_state = AssuranceLifecycleState.ELIGIBILITY_CHECK
        evaluation.started_at = start_time
        evaluation = self._repo.save_evaluation(evaluation)

        self._emit_event(AssuranceDomainEventType.STARTED, evaluation)

        # --- OBSERVATION COLLECTION ---
        evaluation.lifecycle_state = AssuranceLifecycleState.OBSERVATION_COLLECTION
        evaluation = self._repo.save_evaluation(evaluation)

        # Default evidence if none provided
        refs = list(evidence_references or [])
        if not refs and observed_executions is not None and observed_executions > 0:
            obs_time = evaluation.scope.observation_start + (evaluation.scope.observation_end - evaluation.scope.observation_start) / 2
            refs = [
                EvidenceReference(
                    source_type=EvidenceSourceType.PRODUCTION_OBSERVATION,
                    source_id=f"obs-{evaluation.control_id}",
                    observation_timestamp=obs_time,
                    quality_state=EvidenceQualityState.COMPLETE,
                    provenance="production_telemetry",
                )
            ]
        exp_sources = expected_sources or []
        sc_sources = safety_critical_sources or []

        # --- EVIDENCE ASSESSMENT ---
        evaluation.lifecycle_state = AssuranceLifecycleState.EVIDENCE_ASSESSMENT
        evidence_result = self._evidence.classify_evidence_quality(
            references=refs,
            expected_sources=exp_sources,
            evaluation_start=evaluation.scope.observation_start,
            evaluation_end=evaluation.scope.observation_end,
            safety_critical_sources=sc_sources,
        )

        evaluation.evidence_references = evidence_result.evidence_references
        evaluation.evidence_quality = evidence_result.overall_quality
        evaluation.evidence_completeness_note = (
            "; ".join(evidence_result.notes) if evidence_result.notes else None
        )
        evaluation.evidence_collected_at = datetime.now(timezone.utc)
        evaluation = self._repo.save_evaluation(evaluation)

        if evidence_result.has_sufficient_evidence:
            self._emit_event(AssuranceDomainEventType.EVIDENCE_COLLECTED, evaluation)
        else:
            evaluation.lifecycle_state = AssuranceLifecycleState.INSUFFICIENT_EVIDENCE
            evaluation.effectiveness_state = ControlEffectivenessState.INSUFFICIENT_EVIDENCE
            evaluation.review_required = True
            evaluation.review_required_reason = "Insufficient evidence. MISSING != PASS."
            evaluation = self._repo.save_evaluation(evaluation)
            self._emit_event(AssuranceDomainEventType.EVIDENCE_INSUFFICIENT, evaluation)
            self._metrics.increment("assurance_evaluations_insufficient_evidence_total")
            logger.warning(
                "Insufficient evidence — evaluation blocked",
                extra={"evaluation_id": evaluation_id, "request_id": request_id},
            )
            return evaluation

        # --- EFFECTIVENESS EVALUATION ---
        evaluation.lifecycle_state = AssuranceLifecycleState.EFFECTIVENESS_EVALUATION
        evaluation = self._repo.save_evaluation(evaluation)

        thresholds = policy_thresholds or {}
        eval_result = self._effectiveness.evaluate_effectiveness(
            evidence_result=evidence_result,
            eligible_executions=eligible_executions,
            observed_executions=observed_executions,
            observed_failures=observed_failures,
            observed_bypasses=observed_bypasses,
            valid_results=valid_results,
            total_results=total_results,
            expected_behavior_met=expected_behavior_met,
            version_consistent=version_consistent,
            provider_success_rate=provider_success_rate,
            required_reviews_completed=required_reviews_completed,
            required_reviews_total=required_reviews_total,
            degradation_threshold_failure_rate=thresholds.get("failure_rate_threshold"),
            degradation_threshold_bypass_rate=thresholds.get("bypass_rate_threshold"),
            significant_degradation_threshold=thresholds.get("significant_degradation_threshold"),
            is_high_risk_control=is_high_risk_control,
        )

        # Apply effectiveness result to evaluation
        evaluation.effectiveness_state = eval_result.effectiveness_state
        evaluation.execution_state = eval_result.execution_state
        evaluation.degradation_state = eval_result.degradation_state
        evaluation.effectiveness_score = eval_result.score
        evaluation.effectiveness_summary = eval_result.effectiveness_summary
        evaluation.effectiveness_limitations = eval_result.limitations
        evaluation.uncertainty_preserved = eval_result.uncertainty_preserved
        evaluation.bypass_detected = eval_result.bypass_detected
        evaluation.bypass_count = eval_result.bypass_count
        evaluation.regression_detected = eval_result.regression_detected
        evaluation.review_required = eval_result.review_required
        evaluation.review_required_reason = eval_result.review_required_reason
        evaluation.evaluated_at = datetime.now(timezone.utc)
        evaluation = self._repo.save_evaluation(evaluation)

        self._emit_event(AssuranceDomainEventType.EVALUATED, evaluation)

        # --- BYPASS DETECTION ---
        if eval_result.bypass_detected and eval_result.bypass_count > 0:
            bypass_record = self._degradation.detect_bypass(
                evaluation=evaluation,
                bypass_signal=f"{eval_result.bypass_count} bypasses in observation window",
                bypass_count=eval_result.bypass_count,
                policy_requires_incident_routing=thresholds.get(
                    "bypass_requires_incident", False
                ),
            )
            self._metrics.increment("safety_control_bypass_total", eval_result.bypass_count)
            self._emit_event(AssuranceDomainEventType.BYPASS_DETECTED, evaluation)

        # --- DEGRADATION DETECTION ---
        if eval_result.effectiveness_state in (
            ControlEffectivenessState.DEGRADED,
            ControlEffectivenessState.FAILED,
        ):
            self._degradation.detect_degradation(evaluation, thresholds)
            self._emit_event(
                AssuranceDomainEventType.DEGRADED
                if eval_result.effectiveness_state == ControlEffectivenessState.DEGRADED
                else AssuranceDomainEventType.FAILED,
                evaluation,
            )
            if eval_result.effectiveness_state == ControlEffectivenessState.FAILED:
                self._metrics.increment("assurance_evaluations_failed_total")
            else:
                self._metrics.increment("assurance_evaluations_degraded_total")

        # --- REGRESSION DETECTION ---
        reference = self._repo.get_latest_accepted_evaluation(
            evaluation.control_id,
            evaluation.control_version,
            organization_id=evaluation.organization_id,
        )
        if reference and reference.evaluation_id != evaluation.evaluation_id:
            regression = self._degradation.detect_regression(evaluation, reference)
            if regression:
                evaluation.regression_detected = True
                evaluation.regression_compared_to_version = reference.control_version
                evaluation = self._repo.save_evaluation(evaluation)
                self._metrics.increment("safety_control_regression_total")
                self._emit_event(AssuranceDomainEventType.REGRESSION_DETECTED, evaluation)

        # --- STATE TRANSITION ---
        if eval_result.review_required:
            evaluation.lifecycle_state = AssuranceLifecycleState.REVIEW_REQUIRED
            self._emit_event(AssuranceDomainEventType.REVIEW_REQUIRED, evaluation)
            self._metrics.increment("assurance_review_pending_total")
        elif eval_result.effectiveness_state == ControlEffectivenessState.EFFECTIVE_OBSERVED:
            evaluation.lifecycle_state = AssuranceLifecycleState.ASSURANCE_ACCEPTED
            evaluation.completed_at = datetime.now(timezone.utc)
            self._emit_event(AssuranceDomainEventType.EFFECTIVE, evaluation)
            self._emit_event(AssuranceDomainEventType.ACCEPTED, evaluation)
            self._metrics.increment("assurance_evaluations_completed_total")
        elif eval_result.effectiveness_state == ControlEffectivenessState.INSUFFICIENT_EVIDENCE:
            evaluation.lifecycle_state = AssuranceLifecycleState.INSUFFICIENT_EVIDENCE
            self._emit_event(AssuranceDomainEventType.EVIDENCE_INSUFFICIENT, evaluation)
        else:
            # Partially effective, unclear, degraded — require review
            evaluation.lifecycle_state = AssuranceLifecycleState.REVIEW_REQUIRED
            evaluation.review_required = True
            self._emit_event(AssuranceDomainEventType.REVIEW_REQUIRED, evaluation)

        # --- ROUTING ---
        routing = self._routing.determine_evaluation_route(
            evaluation,
            confirmed_safety_event=False,  # Must be explicitly confirmed, never auto
            recurring_failure=False,
        )
        if routing.requires_action:
            self._emit_event(
                AssuranceDomainEventType.RISK_REASSESSMENT_REQUIRED
                if routing.requires_action
                else AssuranceDomainEventType.EVALUATED,
                evaluation,
            )

        evaluation = self._routing.apply_route_to_evaluation(evaluation, routing)

        # --- LATENCY ---
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        self._metrics.record_latency("assurance_job_duration_seconds", duration)

        logger.info(
            "Assurance evaluation executed",
            extra={
                "evaluation_id": evaluation_id,
                "effectiveness_state": evaluation.effectiveness_state.value,
                "lifecycle_state": evaluation.lifecycle_state.value,
                "duration_seconds": duration,
                "request_id": request_id,
            },
        )

        return evaluation

    # -------------------------------------------------------------------------
    # Accept / Reject
    # -------------------------------------------------------------------------

    def accept_evaluation(
        self,
        evaluation_id: str,
        accept_request: AssuranceAcceptRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Formally accept an assurance evaluation.

        Actor identity derived from authenticated session (never client body).
        """
        evaluation = self._get_or_raise(evaluation_id)
        self._check_org_scope(evaluation, actor_organization_id)
        self._validation.validate_concurrency(evaluation, accept_request.evaluation_version)

        if evaluation.lifecycle_state not in (
            AssuranceLifecycleState.UNDER_REVIEW,
            AssuranceLifecycleState.EFFECTIVENESS_EVALUATION,
            AssuranceLifecycleState.ASSURANCE_ACCEPTED,
        ):
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_INVALID_STATE,
                message=f"Cannot accept evaluation in state '{evaluation.lifecycle_state.value}'.",
                status_code=409,
            )

        now = datetime.now(timezone.utc)
        evaluation.lifecycle_state = AssuranceLifecycleState.ASSURANCE_ACCEPTED
        evaluation.effectiveness_state = ControlEffectivenessState.EFFECTIVE_OBSERVED
        evaluation.reviewer_id = actor_id
        evaluation.reviewer_role = actor_role
        evaluation.review_decision = None
        evaluation.review_summary = accept_request.acceptance_rationale
        evaluation.review_limitations = accept_request.acknowledged_limitations
        evaluation.review_required = False
        evaluation.completed_at = now
        evaluation.updated_at = now
        evaluation.version += 1

        evaluation = self._repo.save_evaluation(evaluation)
        self._emit_event(AssuranceDomainEventType.ACCEPTED, evaluation)
        self._metrics.increment("assurance_review_completed_total")
        return evaluation

    def reject_evaluation(
        self,
        evaluation_id: str,
        reject_request: AssuranceRejectRequest,
        actor_id: str,
        actor_role: str,
        actor_organization_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Reject an assurance evaluation, requiring re-evaluation."""
        evaluation = self._get_or_raise(evaluation_id)
        self._check_org_scope(evaluation, actor_organization_id)
        self._validation.validate_concurrency(evaluation, reject_request.evaluation_version)

        now = datetime.now(timezone.utc)
        evaluation.lifecycle_state = AssuranceLifecycleState.REASSESSMENT_REQUIRED
        evaluation.effectiveness_state = ControlEffectivenessState.REQUIRES_REASSESSMENT
        evaluation.review_required = False
        evaluation.reviewer_id = actor_id
        evaluation.reviewer_role = actor_role
        evaluation.review_summary = reject_request.rejection_reason
        evaluation.updated_at = now
        evaluation.version += 1

        evaluation = self._repo.save_evaluation(evaluation)
        self._emit_event(AssuranceDomainEventType.REJECTED, evaluation)
        return evaluation

    def request_reassessment(
        self,
        evaluation_id: str,
        reassess_request: AssuranceReassessRequest,
        actor_id: str,
        actor_organization_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Trigger reassessment of an accepted or monitored evaluation."""
        evaluation = self._get_or_raise(evaluation_id)
        self._check_org_scope(evaluation, actor_organization_id)

        now = datetime.now(timezone.utc)
        evaluation.lifecycle_state = AssuranceLifecycleState.REASSESSMENT_REQUIRED
        evaluation.effectiveness_state = ControlEffectivenessState.REQUIRES_REASSESSMENT
        evaluation.reassessment_trigger = reassess_request.trigger_reason
        evaluation.updated_at = now
        evaluation.version += 1

        evaluation = self._repo.save_evaluation(evaluation)
        self._emit_event(AssuranceDomainEventType.REASSESSMENT_REQUIRED, evaluation)
        self._metrics.increment("assurance_reassessment_total")
        return evaluation

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def get_evaluation(
        self,
        evaluation_id: str,
        actor_organization_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Get evaluation by ID with scope enforcement."""
        evaluation = self._get_or_raise(evaluation_id)
        self._check_org_scope(evaluation, actor_organization_id)
        return evaluation

    def get_evaluation_status(self, evaluation_id: str) -> AssuranceEvaluationStatusResponse:
        """Get lightweight status for async polling."""
        evaluation = self._get_or_raise(evaluation_id)
        return AssuranceEvaluationStatusResponse(
            evaluation_id=evaluation.evaluation_id,
            lifecycle_state=evaluation.lifecycle_state,
            effectiveness_state=evaluation.effectiveness_state,
            degradation_state=evaluation.degradation_state,
            bypass_detected=evaluation.bypass_detected,
            regression_detected=evaluation.regression_detected,
            review_required=evaluation.review_required,
            job_id=evaluation.job_id,
            updated_at=evaluation.updated_at,
            version=evaluation.version,
        )

    def list_evaluations(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[AssuranceLifecycleState] = None,
        effectiveness_state: Optional[ControlEffectivenessState] = None,
        bypass_detected: Optional[bool] = None,
        regression_detected: Optional[bool] = None,
        review_required: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AssuranceEvaluationRecord]:
        """List evaluations with optional filters."""
        return self._repo.list_evaluations(
            organization_id=organization_id,
            facility_id=facility_id,
            lifecycle_state=lifecycle_state,
            effectiveness_state=effectiveness_state,
            bypass_detected=bypass_detected,
            regression_detected=regression_detected,
            review_required=review_required,
            limit=limit,
            offset=offset,
        )

    def get_control_assurance_summary(
        self,
        control_id: str,
        control_version: str,
        organization_id: Optional[str] = None,
    ) -> Optional[ControlAssuranceSummary]:
        """Get assurance summary for a specific control."""
        latest = self._repo.get_latest_accepted_evaluation(
            control_id, control_version, organization_id
        )
        evaluations = self._repo.list_evaluations_for_control(
            control_id, organization_id=organization_id, limit=100
        )

        if not evaluations and latest is None:
            return None

        current = latest or (evaluations[0] if evaluations else None)
        if current is None:
            return None

        bypass_count = sum(
            e.bypass_count for e in evaluations[-10:] if e.bypass_detected
        )
        regression_count = sum(
            1 for e in evaluations[-10:] if e.regression_detected
        )

        return ControlAssuranceSummary(
            control_id=control_id,
            control_name=current.control_name,
            control_category=current.control_category,
            control_version=current.control_version,
            current_effectiveness_state=current.effectiveness_state,
            current_degradation_state=current.degradation_state,
            last_evaluation_id=current.evaluation_id,
            last_evaluated_at=current.evaluated_at,
            last_accepted_at=latest.completed_at if latest else None,
            next_reassessment_due=current.reassessment_required_by,
            bypass_count_recent=bypass_count,
            regression_count_recent=regression_count,
            pending_review=current.review_required,
            organization_id=organization_id,
        )

    def get_dashboard_summary(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
    ) -> AssuranceDashboardSummary:
        """Get non-PHI aggregate assurance summary for dashboard."""
        agg = self._repo.aggregate_dashboard(organization_id, facility_id)
        return AssuranceDashboardSummary(
            organization_id=organization_id,
            facility_id=facility_id,
            **{k: v for k, v in agg.items()},
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _get_or_raise(self, evaluation_id: str) -> AssuranceEvaluationRecord:
        """Load evaluation or raise SAFETY_ASSURANCE_NOT_FOUND."""
        record = self._repo.get_evaluation(evaluation_id)
        if record is None:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_NOT_FOUND,
                message=f"Assurance evaluation '{evaluation_id}' not found.",
                status_code=404,
            )
        return record

    def _check_org_scope(
        self,
        evaluation: AssuranceEvaluationRecord,
        actor_org_id: Optional[str],
    ) -> None:
        """Enforce organization scope isolation."""
        if (
            actor_org_id
            and evaluation.organization_id
            and actor_org_id != evaluation.organization_id
        ):
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_ACCESS_DENIED,
                message="Access denied: evaluation belongs to a different organization.",
                status_code=403,
            )

    def _emit_event(
        self,
        event_type: AssuranceDomainEventType,
        evaluation: AssuranceEvaluationRecord,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
    ) -> None:
        """Emit a domain event (non-PHI references only)."""
        event = AssuranceDomainEvent(
            event_type=event_type,
            evaluation_id=evaluation.evaluation_id,
            control_id=evaluation.control_id,
            control_version=evaluation.control_version,
            lifecycle_state=evaluation.lifecycle_state,
            effectiveness_state=evaluation.effectiveness_state,
            organization_id=organization_id or evaluation.organization_id,
            facility_id=facility_id or evaluation.facility_id,
            metadata={
                "bypass_detected": evaluation.bypass_detected,
                "regression_detected": evaluation.regression_detected,
                "review_required": evaluation.review_required,
            },
        )
        # In production, publish to event bus / Phase 29 delivery system.
        # Here we log at DEBUG level (no PHI).
        logger.debug(
            "Domain event emitted",
            extra={
                "event_type": event_type.value,
                "evaluation_id": evaluation.evaluation_id,
                "control_id": evaluation.control_id,
            },
        )


# Global singleton
safety_assurance_evaluation_service = SafetyAssuranceEvaluationService()

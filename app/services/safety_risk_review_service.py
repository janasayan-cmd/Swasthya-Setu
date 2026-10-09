"""Phase 63: Clinical Safety Risk Review Service Orchestrator.

Coordinates governed risk reviews, decision-readiness validation, evidence tracking,
unresolved questions, human review actions, risk dispositions, controlled routing,
reassessment, and reopening.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_risk_assessment_repository import (
    get_safety_risk_assessment_repository,
)
from app.repositories.safety_risk_review_repository import (
    SafetyRiskReviewRepository,
    get_safety_risk_review_repository,
)
from app.schemas.safety_review_evidence import (
    EvidenceReference,
    RequestEvidenceRequest,
    SubmitEvidenceRequest,
)
from app.schemas.safety_review_package import SafetyReviewPackage
from app.schemas.safety_review_question import (
    CreateQuestionRequest,
    QuestionCategory,
    ResolveQuestionRequest,
    UnresolvedQuestionRecord,
)
from app.schemas.safety_risk_disposition import (
    RecordDispositionRequest,
    RiskDispositionRecord,
    RiskDispositionType,
)
from app.schemas.safety_risk_readiness import (
    DecisionReadinessEvaluation,
    DecisionReadinessState,
)
from app.schemas.safety_risk_review import (
    CreateSafetyRiskReviewRequest,
    ReanalyzeReviewRequest,
    ReassessReviewRequest,
    ReopenReviewRequest,
    ReviewHistoryEntry,
    ReviewLifecycleState,
    SafetyRiskReviewRecord,
    SafetyRiskReviewStatusResponse,
)
from app.schemas.safety_risk_review_action import (
    PerformReviewActionRequest,
    ReviewActionRecord,
    ReviewerActionType,
)
from app.schemas.safety_routing import (
    RiskRoutingRecord,
    RouteReviewRequest,
    RoutingDestination,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_review_evidence_service import SafetyReviewEvidenceService
from app.services.safety_review_package_service import SafetyReviewPackageService
from app.services.safety_review_question_service import SafetyReviewQuestionService
from app.services.safety_risk_disposition_service import SafetyRiskDispositionService
from app.services.safety_risk_readiness_service import SafetyRiskReadinessService
from app.services.safety_risk_reassessment_service import SafetyRiskReassessmentService
from app.services.safety_risk_reopen_service import SafetyRiskReopenService
from app.services.safety_risk_review_authorization_service import (
    SafetyRiskReviewAuthorizationService,
)
from app.services.safety_risk_review_concurrency_service import (
    SafetyRiskReviewConcurrencyService,
)
from app.services.safety_risk_review_idempotency_service import (
    SafetyRiskReviewIdempotencyService,
    get_safety_risk_review_idempotency_service,
)
from app.services.safety_risk_review_privacy_service import (
    SafetyRiskReviewPrivacyService,
)
from app.services.safety_risk_routing_service import (
    SafetyRiskRoutingService,
    get_safety_risk_routing_service,
)
from app.services.safety_risk_separation_service import (
    SafetyRiskSeparationService,
)

logger = logging.getLogger(__name__)


class SafetyRiskReviewService:
    """Primary orchestrator for Phase 63 clinical safety risk reviews."""

    def __init__(
        self,
        repository: Optional[SafetyRiskReviewRepository] = None,
        idempotency_service: Optional[SafetyRiskReviewIdempotencyService] = None,
        routing_service: Optional[SafetyRiskRoutingService] = None,
    ) -> None:
        self.repository = repository or get_safety_risk_review_repository()
        self.idempotency_svc = idempotency_service or get_safety_risk_review_idempotency_service()
        self.routing_svc = routing_service or get_safety_risk_routing_service()

    def create_review(
        self,
        request: CreateSafetyRiskReviewRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Create a new governed risk review consuming Phase 62 risk context."""
        org_id = request.organization_id or user.organization_id
        fac_id = request.facility_id or user.facility_id or "fac-default"

        # 1. Privacy & Scope checks
        SafetyRiskReviewPrivacyService.validate_tenant_access(user, org_id, fac_id)
        SafetyRiskReviewPrivacyService.validate_purpose(request.purpose)

        # 2. Idempotency check
        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key,
            "create_review",
            request.model_dump(),
        )
        if cached:
            existing = self.repository.get(cached)
            if existing:
                return existing

        # 3. Load & validate Phase 62 risk context
        phase62_repo = get_safety_risk_assessment_repository()
        assessment = phase62_repo.get(request.assessment_id)
        if not assessment:
            raise AppException(
                code=ErrorCode.RISK_CONTEXT_NOT_FOUND,
                message=f"Phase 62 Risk Assessment '{request.assessment_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # 4. Scope and Version validation
        if assessment.organization_id != org_id:
            raise AppException(
                code=ErrorCode.SCOPE_CONFLICT,
                message=f"Risk context organization '{assessment.organization_id}' differs from requested organization '{org_id}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if request.risk_context_version and assessment.version != request.risk_context_version:
            raise AppException(
                code=ErrorCode.VERSION_CONFLICT,
                message=f"Risk context version mismatch: request specifies '{request.risk_context_version}', source assessment is '{assessment.version}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Initialize Review Record
        clean_scope = SafetyRiskReviewPrivacyService.sanitize_payload(request.scope or {})
        review = SafetyRiskReviewRecord(
            assessment_id=request.assessment_id,
            organization_id=org_id,
            facility_id=fac_id,
            scope=clean_scope,
            application_version=request.application_version or "v1.0.0",
            configuration_version=request.configuration_version or "v1.0.0",
            safety_control_version=request.safety_control_version or "v1.0.0",
            risk_context_version=assessment.version,
            provenance="PHASE_62_GOVERNED_RISK_ASSESSMENT",
            created_by=user.user_id,
            idempotency_key=request.idempotency_key,
            state=ReviewLifecycleState.CREATED,
        )

        # Extract initial evidence items if any findings have evidence references
        source_evidence = getattr(assessment, "evidence_items", []) or getattr(assessment, "reconciled_evidence", [])
        if source_evidence:
            for rev_dict in source_evidence:
                edata = rev_dict if isinstance(rev_dict, dict) else rev_dict.model_dump()
                review.evidence_items.append(
                    EvidenceReference(
                        source=edata.get("source_domain") or edata.get("source_phase") or "PHASE_62_ASSESSMENT",
                        provenance=edata.get("reconciliation_id") or edata.get("evidence_id") or "PHASE_62",
                        is_counter_evidence=edata.get("is_counter_evidence", False),
                        limitations=edata.get("limitations", []),
                    )
                )

        # Evaluate initial evidence sufficiency
        sufficiency, _, _ = SafetyReviewEvidenceService.evaluate_evidence_sufficiency(review.evidence_items)
        review.evidence_sufficiency = sufficiency

        # Evaluate readiness
        readiness = SafetyRiskReadinessService.evaluate_readiness(review)
        review.readiness = readiness
        if readiness.is_ready_for_review:
            review.state = ReviewLifecycleState.READY
        elif readiness.state == DecisionReadinessState.EVIDENCE_REQUIRED:
            review.state = ReviewLifecycleState.EVIDENCE_REQUESTED
        elif readiness.state == DecisionReadinessState.CONFLICTED:
            review.state = ReviewLifecycleState.CONFLICT_REVIEW
        else:
            review.state = ReviewLifecycleState.NOT_READY

        # Assemble review package
        SafetyReviewPackageService.assemble_package(review, assessment)

        # Record history
        entry = ReviewHistoryEntry(
            from_state=ReviewLifecycleState.CREATED,
            to_state=review.state,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="CREATE_REVIEW",
            details={"assessment_id": request.assessment_id, "initial_state": review.state.value},
        )
        review.history.append(entry)

        # Persist
        saved = self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key,
                "create_review",
                request.model_dump(),
                saved.review_id,
            )

        return saved

    def get_review(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Fetch review record with tenant boundary enforcement."""
        review = self.repository.get(review_id)
        if not review:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_REVIEW_NOT_FOUND,
                message=f"Safety risk review '{review_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyRiskReviewPrivacyService.validate_tenant_access(
            user, review.organization_id, review.facility_id
        )
        return review

    def get_status(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewStatusResponse:
        """Get summary lifecycle status for a review."""
        review = self.get_review(review_id, user)
        open_q_count = sum(1 for q in review.questions if q.status.value in ("OPEN", "ASSIGNED", "REOPENED"))
        return SafetyRiskReviewStatusResponse(
            review_id=review.review_id,
            state=review.state,
            readiness_state=review.readiness.state if review.readiness else None,
            is_ready_for_review=review.readiness.is_ready_for_review if review.readiness else False,
            open_questions_count=open_q_count,
            evidence_count=len(review.evidence_items),
            current_disposition=review.current_disposition,
            updated_at=review.updated_at,
        )

    def get_readiness(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> DecisionReadinessEvaluation:
        """Get or re-evaluate decision readiness state."""
        review = self.get_review(review_id, user)
        readiness = SafetyRiskReadinessService.evaluate_readiness(review)
        review.readiness = readiness
        self.repository.save(review)
        return readiness

    def get_evidence(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> List[EvidenceReference]:
        """Fetch authorized evidence references."""
        review = self.get_review(review_id, user)
        return review.evidence_items

    def get_questions(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> List[UnresolvedQuestionRecord]:
        """Fetch unresolved questions."""
        review = self.get_review(review_id, user)
        return review.questions

    def get_package(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> SafetyReviewPackage:
        """Fetch review package, re-assembling if necessary."""
        review = self.get_review(review_id, user)
        if not review.review_package:
            phase62_repo = get_safety_risk_assessment_repository()
            assessment = phase62_repo.get(review.assessment_id)
            SafetyReviewPackageService.assemble_package(review, assessment)
            self.repository.save(review)
        return review.review_package

    def get_history(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> List[ReviewHistoryEntry]:
        """Fetch immutable review history audit trail."""
        review = self.get_review(review_id, user)
        return review.history

    def validate_context(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> DecisionReadinessEvaluation:
        """Validate review context and update lifecycle state accordingly."""
        review = self.get_review(review_id, user)
        readiness = SafetyRiskReadinessService.evaluate_readiness(review)
        prev_state = review.state
        review.readiness = readiness

        if readiness.is_ready_for_review:
            if review.state in (ReviewLifecycleState.NOT_READY, ReviewLifecycleState.READINESS_CHECK, ReviewLifecycleState.CREATED):
                review.state = ReviewLifecycleState.READY
        elif readiness.state == DecisionReadinessState.EVIDENCE_REQUIRED:
            review.state = ReviewLifecycleState.EVIDENCE_REQUESTED
        elif readiness.state == DecisionReadinessState.CONFLICTED:
            review.state = ReviewLifecycleState.CONFLICT_REVIEW
        elif readiness.state == DecisionReadinessState.BLOCKED:
            review.state = ReviewLifecycleState.BLOCKED
        elif readiness.state == DecisionReadinessState.STALE:
            review.state = ReviewLifecycleState.STALE

        if prev_state != review.state:
            entry = ReviewHistoryEntry(
                from_state=prev_state,
                to_state=review.state,
                actor_id=user.user_id,
                actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
                action="VALIDATE_CONTEXT",
                details={"readiness_state": readiness.state.value},
            )
            review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        self.repository.save(review)
        return readiness

    def request_evidence(
        self,
        review_id: str,
        request: RequestEvidenceRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Request additional evidence and record an explicit question."""
        review = self.get_review(review_id, user)
        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "request_evidence", request.model_dump()
        )
        if cached:
            return review

        # Add explicit unresolved question
        q_req = CreateQuestionRequest(
            category=QuestionCategory.MISSING_EVIDENCE,
            question_text=f"Requested evidence from '{request.target_source}': {request.reason}",
            assigned_to=None,
        )
        SafetyReviewQuestionService.create_question(review, q_req, user)

        prev_state = review.state
        review.state = ReviewLifecycleState.EVIDENCE_REQUESTED

        entry = ReviewHistoryEntry(
            from_state=prev_state,
            to_state=ReviewLifecycleState.EVIDENCE_REQUESTED,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="REQUEST_EVIDENCE",
            details={
                "target_source": request.target_source,
                "reason": request.reason,
                "evidence_types": request.evidence_types,
            },
        )
        review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        saved = self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "request_evidence", request.model_dump(), True
            )
        return saved

    def submit_evidence(
        self,
        review_id: str,
        request: SubmitEvidenceRequest,
        user: AuthenticatedUserContext,
    ) -> EvidenceReference:
        """Submit evidence to a review and update readiness."""
        review = self.get_review(review_id, user)
        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "submit_evidence", request.model_dump()
        )
        if cached:
            for ev in review.evidence_items:
                if ev.evidence_id == cached:
                    return ev

        ev_ref = SafetyReviewEvidenceService.attach_evidence(review, request, user)

        # Resolve associated question if provided
        if request.question_id:
            try:
                SafetyReviewQuestionService.resolve_question(
                    review,
                    request.question_id,
                    ResolveQuestionRequest(
                        resolution_summary=f"Resolved via evidence '{ev_ref.evidence_id}' from source '{request.source}'.",
                        evidence_references=[ev_ref.evidence_id],
                    ),
                    user,
                )
            except Exception as e:
                logger.warning("Could not auto-resolve question %s: %s", request.question_id, e)

        prev_state = review.state
        review.state = ReviewLifecycleState.EVIDENCE_RECEIVED

        # Re-evaluate readiness
        readiness = SafetyRiskReadinessService.evaluate_readiness(review)
        review.readiness = readiness
        if readiness.is_ready_for_review:
            review.state = ReviewLifecycleState.READY

        entry = ReviewHistoryEntry(
            from_state=prev_state,
            to_state=review.state,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="SUBMIT_EVIDENCE",
            details={"evidence_id": ev_ref.evidence_id, "source": request.source},
        )
        review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "submit_evidence", request.model_dump(), ev_ref.evidence_id
            )
        return ev_ref

    def start_review(
        self,
        review_id: str,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Initiate authorized human review session with SoD validation."""
        review = self.get_review(review_id, user)

        # 1. Authorize reviewer credentials
        SafetyRiskReviewAuthorizationService.validate_reviewer_authority(user, review)

        # 2. Enforce Separation of Duties
        SafetyRiskSeparationService.validate_separation_of_duties(user, review, attempted_role="RISK_REVIEWER")

        # 3. State verification
        allowed_states = {
            ReviewLifecycleState.READY,
            ReviewLifecycleState.REVIEW_PENDING,
            ReviewLifecycleState.EVIDENCE_RECEIVED,
            ReviewLifecycleState.NOT_READY,
        }
        if review.state not in allowed_states and review.state != ReviewLifecycleState.REVIEW_IN_PROGRESS:
            raise AppException(
                code=ErrorCode.INVALID_REVIEW_STATE,
                message=f"Review in state '{review.state.value}' cannot be transitioned to active human review.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        prev_state = review.state
        review.state = ReviewLifecycleState.REVIEW_IN_PROGRESS
        review.current_reviewer_id = user.user_id
        review.current_reviewer_role = user.role.value if hasattr(user.role, "value") else str(user.role)
        review.started_at = datetime.now(timezone.utc)

        entry = ReviewHistoryEntry(
            from_state=prev_state,
            to_state=ReviewLifecycleState.REVIEW_IN_PROGRESS,
            actor_id=user.user_id,
            actor_role=review.current_reviewer_role,
            action="START_REVIEW",
            details={"reviewer_id": user.user_id},
        )
        review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        return self.repository.save(review)

    def perform_review_action(
        self,
        review_id: str,
        request: PerformReviewActionRequest,
        user: AuthenticatedUserContext,
    ) -> ReviewActionRecord:
        """Record human reviewer action/outcome enforcing strict AI governance boundaries."""
        review = self.get_review(review_id, user)

        # AI cannot perform governed human review actions autonomously
        if request.is_ai:
            raise AppException(
                code=ErrorCode.REVIEWER_NOT_AUTHORIZED,
                message="AI cannot autonomously perform governed review actions or approve reviews. Human authorization mandatory.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Authorize & SoD check
        SafetyRiskReviewAuthorizationService.validate_reviewer_authority(user, review)
        SafetyRiskSeparationService.validate_separation_of_duties(user, review, attempted_role="RISK_REVIEWER")

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "perform_action", request.model_dump()
        )
        if cached:
            for act in review.actions:
                if act.action_id == cached:
                    return act

        action_rec = ReviewActionRecord(
            review_id=review.review_id,
            action_type=request.action_type,
            reviewer_id=user.user_id,
            reviewer_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            rationale=request.rationale,
            is_ai_assisted=request.is_ai,
            ai_metadata=request.ai_metadata,
            metadata=request.metadata or {},
        )
        review.actions.append(action_rec)

        # State transition based on action
        prev_state = review.state
        act_type = request.action_type

        if act_type == ReviewerActionType.ESCALATE:
            review.requires_escalation = True
            review.state = ReviewLifecycleState.DECISION_PENDING
        elif act_type == ReviewerActionType.REQUEST_REASSESSMENT:
            review.requires_reassessment = True
            review.state = ReviewLifecycleState.REASSESSMENT_REQUIRED
        elif act_type == ReviewerActionType.REQUEST_MORE_EVIDENCE:
            review.state = ReviewLifecycleState.EVIDENCE_REQUESTED
        elif act_type == ReviewerActionType.CLOSE_REVIEW:
            review.state = ReviewLifecycleState.COMPLETED
            review.completed_at = datetime.now(timezone.utc)
        elif act_type in (
            ReviewerActionType.ROUTE_TO_INCIDENT,
            ReviewerActionType.ROUTE_TO_ASSURANCE,
            ReviewerActionType.ROUTE_TO_GOVERNANCE,
            ReviewerActionType.ROUTE_TO_EFFECTIVENESS,
            ReviewerActionType.ROUTE_TO_CONTROLLED_ACTION,
            ReviewerActionType.ROUTE_TO_LEARNING,
            ReviewerActionType.ROUTE_TO_IMPROVEMENT,
        ):
            review.state = ReviewLifecycleState.DECISION_PENDING
        else:
            review.state = ReviewLifecycleState.DECISION_PENDING

        entry = ReviewHistoryEntry(
            from_state=prev_state,
            to_state=review.state,
            actor_id=user.user_id,
            actor_role=action_rec.reviewer_role,
            action=f"REVIEW_ACTION:{act_type.value}",
            details={"rationale": request.rationale, "action_id": action_rec.action_id},
        )
        review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "perform_action", request.model_dump(), action_rec.action_id
            )
        return action_rec

    def record_disposition(
        self,
        review_id: str,
        request: RecordDispositionRequest,
        user: AuthenticatedUserContext,
    ) -> RiskDispositionRecord:
        """Record governed risk disposition with SoD and boundary enforcement."""
        review = self.get_review(review_id, user)

        # Authorize & SoD
        SafetyRiskReviewAuthorizationService.validate_reviewer_authority(user, review)
        SafetyRiskSeparationService.validate_separation_of_duties(user, review, attempted_role="RISK_REVIEWER")

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "record_disposition", request.model_dump()
        )
        if cached:
            for disp in review.dispositions:
                if disp.disposition_id == cached:
                    return disp

        disp_record = SafetyRiskDispositionService.record_disposition(review, request, user)

        entry = ReviewHistoryEntry(
            from_state=ReviewLifecycleState.DECISION_PENDING,
            to_state=review.state,
            actor_id=user.user_id,
            actor_role=disp_record.authorizer_role,
            action=f"RECORD_DISPOSITION:{disp_record.disposition_type.value}",
            details={"reasoning": disp_record.reasoning, "disposition_id": disp_record.disposition_id},
        )
        review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "record_disposition", request.model_dump(), disp_record.disposition_id
            )
        return disp_record

    def route_review(
        self,
        review_id: str,
        request: RouteReviewRequest,
        user: AuthenticatedUserContext,
    ) -> List[RiskRoutingRecord]:
        """Dispatch reviewed risk disposition to authoritative downstream phases."""
        review = self.get_review(review_id, user)
        SafetyRiskReviewAuthorizationService.validate_reviewer_authority(user, review)

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "route_review", request.model_dump()
        )
        if cached:
            return [r for r in review.routings if r.routing_id in cached]

        routes = self.routing_svc.route_review(
            review=review,
            destinations=request.destinations,
            actor_id=user.user_id,
            reason=request.reason,
            target_reference=request.target_reference,
        )

        entry = ReviewHistoryEntry(
            from_state=ReviewLifecycleState.ROUTING_REQUIRED,
            to_state=review.state,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="ROUTE_REVIEW",
            details={"destinations": [d.value for d in request.destinations], "reason": request.reason},
        )
        review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "route_review", request.model_dump(), [r.routing_id for r in routes]
            )
        return routes

    def reassess_review(
        self,
        review_id: str,
        request: ReassessReviewRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Trigger review reassessment workflow."""
        review = self.get_review(review_id, user)
        SafetyRiskReviewAuthorizationService.validate_reviewer_authority(user, review)

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "reassess_review", request.model_dump()
        )
        if cached:
            return review

        SafetyRiskReassessmentService.request_reassessment(review, request.reason, user)
        SafetyRiskReviewConcurrencyService.increment_version(review)
        saved = self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "reassess_review", request.model_dump(), True
            )
        return saved

    def reopen_review(
        self,
        review_id: str,
        request: ReopenReviewRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Reopen a completed review under governed policy."""
        review = self.get_review(review_id, user)
        SafetyRiskReviewAuthorizationService.validate_reviewer_authority(user, review)

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "reopen_review", request.model_dump()
        )
        if cached:
            return review

        SafetyRiskReopenService.reopen_review(
            review, request.reason, user, request.new_evidence_reference
        )
        SafetyRiskReviewConcurrencyService.increment_version(review)
        saved = self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "reopen_review", request.model_dump(), True
            )
        return saved

    def reanalyze_review(
        self,
        review_id: str,
        request: ReanalyzeReviewRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Request Phase 61 longitudinal reanalysis."""
        review = self.get_review(review_id, user)
        SafetyRiskReviewAuthorizationService.validate_reviewer_authority(user, review)

        cached = self.idempotency_svc.check_or_record(
            request.idempotency_key, "reanalyze_review", request.model_dump()
        )
        if cached:
            return review

        if not request.reason or len(request.reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_EVIDENCE,
                message="Substantive reasoning is required to trigger reanalysis.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        prev_state = review.state
        review.state = ReviewLifecycleState.READINESS_CHECK

        entry = ReviewHistoryEntry(
            from_state=prev_state,
            to_state=ReviewLifecycleState.READINESS_CHECK,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="REQUEST_REANALYSIS",
            details={"reason": request.reason},
        )
        review.history.append(entry)

        SafetyRiskReviewConcurrencyService.increment_version(review)
        saved = self.repository.save(review)
        if request.idempotency_key:
            self.idempotency_svc.store_result(
                request.idempotency_key, "reanalyze_review", request.model_dump(), True
            )
        return saved

    def list_reviews(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        state: Optional[ReviewLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews with tenant boundaries and pagination."""
        return self.repository.list_reviews(
            organization_id=user.organization_id,
            facility_id=facility_id,
            state=state,
            limit=limit,
            offset=offset,
        )

    def list_pending(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List pending reviews."""
        return self.repository.list_pending(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_review_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews requiring human review."""
        return self.repository.list_review_required(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_evidence_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews requiring additional evidence."""
        return self.repository.list_evidence_required(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_escalation_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews requiring critical escalation."""
        return self.repository.list_escalation_required(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def list_reassessment_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews requiring reassessment."""
        return self.repository.list_reassessment_required(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def submit_review(
        self,
        assessment: Any,
        reviewer_id: str,
        reviewer_role: str,
        decision: Any,
        reason: str,
        resulting_routes: Optional[List[Any]] = None,
        is_ai: bool = False,
    ) -> Any:
        """Phase 62 compatibility: Record human review decision on a Phase 62 risk assessment."""
        from app.schemas.safety_risk_assessment import (
            AssessmentLifecycleState,
            HumanRiskReviewDecision,
            RiskAssessmentReviewRecord,
            RiskRoutingDestination,
        )

        if is_ai:
            raise AppException(
                code=ErrorCode.CLINICAL_ACTION_RESTRICTED,
                message="AI agents cannot approve safety risk assessments, resolve evidence conflicts, or declare system safety autonomously.",
                status_code=403,
            )

        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_EVIDENCE,
                message="A substantive clinical safety justification is required for risk assessment review.",
                status_code=400,
            )

        routes = list(resulting_routes) if resulting_routes else []

        if decision == HumanRiskReviewDecision.ROUTE_TO_INCIDENT:
            routes.append(RiskRoutingDestination.PHASE_49_INCIDENT_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_ASSURANCE:
            routes.append(RiskRoutingDestination.PHASE_52_ASSURANCE_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_EFFECTIVENESS:
            routes.append(RiskRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_GOVERNANCE:
            routes.append(RiskRoutingDestination.PHASE_51_GOVERNANCE_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_ACTION:
            routes.append(RiskRoutingDestination.PHASE_54_CONTROLLED_ACTION_REVIEW)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_LEARNING:
            routes.append(RiskRoutingDestination.PHASE_50_SAFETY_LEARNING)
        elif decision == HumanRiskReviewDecision.ROUTE_TO_IMPROVEMENT:
            routes.append(RiskRoutingDestination.PHASE_56_SAFETY_IMPROVEMENT)
        elif decision == HumanRiskReviewDecision.REASSESS:
            routes.append(RiskRoutingDestination.PHASE_60_REASSESSMENT)
        elif decision == HumanRiskReviewDecision.CONTINUE_MONITORING:
            routes.append(RiskRoutingDestination.CONTINUE_MONITORING)

        review_rec = RiskAssessmentReviewRecord(
            reviewed_by=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            reason=reason,
            resulting_routes=list(set(routes)),
            reviewed_at=datetime.now(timezone.utc),
            is_ai_agent=False,
        )

        assessment.reviews.append(review_rec)
        assessment.requires_human_review = False

        if decision == HumanRiskReviewDecision.REJECT_RISK_CHARACTERIZATION:
            assessment.lifecycle_state = AssessmentLifecycleState.FAILED
        elif decision == HumanRiskReviewDecision.ESCALATE:
            assessment.lifecycle_state = AssessmentLifecycleState.ESCALATION_REQUIRED
            assessment.requires_escalation = True
        elif decision == HumanRiskReviewDecision.REASSESS:
            assessment.lifecycle_state = AssessmentLifecycleState.REASSESSMENT_REQUIRED
            assessment.requires_reassessment = True
        else:
            if routes:
                assessment.lifecycle_state = AssessmentLifecycleState.ROUTED
            else:
                assessment.lifecycle_state = AssessmentLifecycleState.RESOLVED

        return review_rec


_review_service_instance: Optional[SafetyRiskReviewService] = None


def get_safety_risk_review_service() -> SafetyRiskReviewService:
    global _review_service_instance
    if _review_service_instance is None:
        _review_service_instance = SafetyRiskReviewService()
    return _review_service_instance

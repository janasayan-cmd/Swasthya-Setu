"""Phase 65: Primary Safety Workflow Completion Service.

Orchestrates Phase 65 clinical safety completion governance, cross-phase outcome verification,
and controlled follow-up closure.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_risk_handoff_repository import (
    SafetyRiskHandoffRepository,
    get_safety_risk_handoff_repository,
)
from app.repositories.safety_risk_review_repository import (
    SafetyRiskReviewRepository,
    get_safety_risk_review_repository,
)
from app.repositories.safety_workflow_completion_repository import (
    SafetyWorkflowCompletionRepository,
    get_safety_workflow_completion_repository,
)
from app.schemas.auth import UserRole
from app.schemas.safety_completion_action import (
    AuthorizeCompletionRequest,
    CloseCompletionWorkflowRequest,
    CompletionAuthorizationRecord,
    CompletionClosureRecord,
    CompletionReopenRecord,
    ReassessCompletionWorkflowRequest,
    ReconcileCompletionWorkflowRequest,
    ReopenCompletionWorkflowRequest,
)
from app.schemas.safety_completion_history import (
    CompletionHistoryEntry,
    CompletionStatusResponse,
)
from app.schemas.safety_completion_package import CompletionPackageRecord
from app.schemas.safety_completion_readiness import (
    EvaluateReadinessRequest,
    ReadinessEvaluationRecord,
)
from app.schemas.safety_completion_requirement import CompletionRequirementRecord
from app.schemas.safety_completion_review import (
    CompletionReviewRecord,
    SubmitCompletionReviewRequest,
)
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    CreateSafetyWorkflowCompletionRequest,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_completion_authorization_service import (
    SafetyCompletionAuthorizationService,
)
from app.services.safety_completion_closure_service import SafetyCompletionClosureService
from app.services.safety_completion_followup_service import SafetyCompletionFollowUpService
from app.services.safety_completion_idempotency_service import (
    SafetyCompletionIdempotencyService,
)
from app.services.safety_completion_outcome_service import SafetyCompletionOutcomeService
from app.services.safety_completion_package_service import SafetyCompletionPackageService
from app.services.safety_completion_privacy_service import SafetyCompletionPrivacyService
from app.services.safety_completion_readiness_service import SafetyCompletionReadinessService
from app.services.safety_completion_reconciliation_service import (
    SafetyCompletionReconciliationService,
)
from app.services.safety_completion_reopen_service import SafetyCompletionReopenService
from app.services.safety_completion_requirement_service import (
    SafetyCompletionRequirementService,
)
from app.services.safety_completion_review_service import SafetyCompletionReviewService


class SafetyWorkflowCompletionService:
    """Core domain service for Phase 65 completion governance."""

    def __init__(
        self,
        completion_repo: Optional[SafetyWorkflowCompletionRepository] = None,
        handoff_repo: Optional[SafetyRiskHandoffRepository] = None,
        review_repo: Optional[SafetyRiskReviewRepository] = None,
    ) -> None:
        self.completion_repo = completion_repo or get_safety_workflow_completion_repository()
        self.handoff_repo = handoff_repo or get_safety_risk_handoff_repository()
        self.review_repo = review_repo or get_safety_risk_review_repository()
        self.idempotency_service = SafetyCompletionIdempotencyService(self.completion_repo)

    def create_completion(
        self,
        request: CreateSafetyWorkflowCompletionRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyWorkflowCompletionRecord:
        """Initialize a new completion coordination workflow from Phase 63 disposition."""
        # 1. Idempotency Check
        if request.idempotency_key:
            existing = self.idempotency_service.check_or_store(
                idempotency_key=request.idempotency_key,
                organization_id=user.organization_id,
                incoming_disposition_id=request.disposition_id,
            )
            if existing:
                SafetyCompletionPrivacyService.validate_caller_access(
                    user, existing.organization_id, existing.facility_id
                )
                return existing

        # 2. Fetch authoritative Phase 63 review & disposition
        review = self.review_repo.get(request.review_id)
        if not review:
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_NOT_FOUND,
                message=f"Source review '{request.review_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        SafetyCompletionPrivacyService.validate_caller_access(
            user, review.organization_id, review.facility_id
        )

        matched_disp = next((d for d in review.dispositions if d.disposition_id == request.disposition_id), None)
        if not matched_disp:
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_NOT_FOUND,
                message=f"Disposition '{request.disposition_id}' not found on review '{request.review_id}'.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        disposition = matched_disp

        # 3. Fetch associated Phase 64 handoffs
        handoffs = self.handoff_repo.get_by_disposition_id(request.disposition_id)
        if not handoffs:
            # Also check by review id as fallback
            handoffs = self.handoff_repo.get_by_review_id(request.review_id)

        # 4. Construct completion record
        record = SafetyWorkflowCompletionRecord(
            source_review_id=request.review_id,
            source_disposition_id=request.disposition_id,
            source_risk_context_id=request.risk_context_id or review.assessment_id,
            source_revision="v1.0.0",
            organization_id=review.organization_id,
            facility_id=review.facility_id,
            state=CompletionLifecycleState.CREATED,
            authorized_scope=request.authorized_scope or getattr(review, "authorized_scope", None) or getattr(review, "scope", {}),
            contract_version=request.contract_version or "v1.0.0",
            applicable_policy_version=request.applicable_policy_version or "v1.0.0",
            idempotency_key=request.idempotency_key,
            created_by=user.user_id,
        )

        # 5. Reconcile initial requirements, outcomes, follow-ups, and readiness
        record = SafetyCompletionReconciliationService.reconcile(
            completion=record,
            disposition=disposition,
            handoffs=handoffs,
        )

        record.history.append({
            "action": "COMPLETION_WORKFLOW_INITIALIZED",
            "actor_id": user.user_id,
            "disposition_id": request.disposition_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return self.completion_repo.save(record)

    def get_completion(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> SafetyWorkflowCompletionRecord:
        """Retrieve completion record by ID with access control."""
        record = self.completion_repo.get(completion_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Safety workflow completion '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyCompletionPrivacyService.validate_caller_access(
            user, record.organization_id, record.facility_id
        )
        return record

    def get_status(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> CompletionStatusResponse:
        """Retrieve enriched lifecycle status."""
        record = self.get_completion(completion_id, user)
        pkg = record.completion_package or {}
        req_summary = pkg.get("requirement_register_summary", {})
        handoff_summary = pkg.get("handoff_status_summary", {})

        return CompletionStatusResponse(
            completion_id=record.completion_id,
            coordination_id=record.coordination_id,
            state=record.state,
            readiness_state=record.readiness_state,
            is_ready_for_review=record.readiness_state in ("READY", "READY_WITH_LIMITATIONS"),
            is_ready_for_closure=record.state == CompletionLifecycleState.CLOSURE_PENDING,
            total_requirements=req_summary.get("total", len(record.requirements)),
            satisfied_requirements=req_summary.get("satisfied", 0),
            pending_requirements=req_summary.get("pending", 0),
            blocked_requirements=req_summary.get("blocked", 0),
            total_handoffs=handoff_summary.get("total", 0),
            completed_handoffs=handoff_summary.get("completed", 0),
            total_follow_ups=len(record.follow_ups),
            satisfied_follow_ups=sum(1 for f in record.follow_ups if f.get("status") in ("SATISFIED", "WAIVED_BY_AUTHORIZED_POLICY")),
            blockers=record.blockers,
            limitations=record.limitations,
            updated_at=record.updated_at,
        )

    def get_readiness(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> ReadinessEvaluationRecord:
        """Retrieve the latest readiness evaluation."""
        record = self.get_completion(completion_id, user)
        # Load disposition and handoffs to evaluate fresh or return cached package evaluation
        review = self.review_repo.get(record.source_review_id)
        disposition = next((d for d in review.dispositions if d.disposition_id == record.source_disposition_id), None) if review else None
        handoffs = self.handoff_repo.get_by_disposition_id(record.source_disposition_id)

        reqs = [CompletionRequirementRecord(**r) for r in record.requirements]
        outcomes = [r for r in record.outcomes]
        fups = [r for r in record.follow_ups]

        if not disposition:
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_NOT_FOUND,
                message=f"Authoritative source disposition '{record.source_disposition_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return SafetyCompletionReadinessService.evaluate(
            completion_id=record.completion_id,
            disposition=disposition,
            handoffs=handoffs,
            requirements=reqs,
            outcomes=SafetyCompletionOutcomeService.verify_handoff_outcomes(record.completion_id, handoffs),
            follow_ups=SafetyCompletionFollowUpService.aggregate_follow_ups(record.completion_id, disposition, handoffs),
            source_revision=record.source_revision,
            policy_version=record.applicable_policy_version,
        )

    def evaluate_readiness(
        self,
        completion_id: str,
        request: EvaluateReadinessRequest,
        user: AuthenticatedUserContext,
    ) -> ReadinessEvaluationRecord:
        """Trigger an on-demand readiness re-evaluation."""
        record = self.get_completion(completion_id, user)
        review = self.review_repo.get(record.source_review_id)
        disposition = next((d for d in review.dispositions if d.disposition_id == record.source_disposition_id), None) if review else None
        if not review or not disposition:
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_NOT_FOUND,
                message="Source review or disposition not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        handoffs = self.handoff_repo.get_by_disposition_id(record.source_disposition_id)

        # Execute reconciliation
        record = SafetyCompletionReconciliationService.reconcile(
            completion=record,
            disposition=disposition,
            handoffs=handoffs,
        )
        self.completion_repo.save(record)
        return self.get_readiness(completion_id, user)

    def get_requirements(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> List[Dict[str, Any]]:
        """Retrieve requirement register."""
        record = self.get_completion(completion_id, user)
        return record.requirements

    def get_outcomes(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> List[Dict[str, Any]]:
        """Retrieve destination outcome references."""
        record = self.get_completion(completion_id, user)
        return record.outcomes

    def get_follow_ups(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> List[Dict[str, Any]]:
        """Retrieve follow-up obligations."""
        record = self.get_completion(completion_id, user)
        return record.follow_ups

    def get_package(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> Dict[str, Any]:
        """Retrieve completion package."""
        record = self.get_completion(completion_id, user)
        if not record.completion_package:
            raise AppException(
                code=ErrorCode.COMPLETION_NOT_READY,
                message="Completion package has not yet been assembled.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record.completion_package

    def get_history(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> List[Dict[str, Any]]:
        """Retrieve completion audit history."""
        record = self.get_completion(completion_id, user)
        return record.history

    def submit_review(
        self,
        completion_id: str,
        request: SubmitCompletionReviewRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionReviewRecord:
        """Submit an authorized completion review."""
        record = self.get_completion(completion_id, user)
        review_record = SafetyCompletionReviewService.process_review(record, request, user)
        self.completion_repo.save(record)
        return review_record

    def authorize_completion(
        self,
        completion_id: str,
        request: AuthorizeCompletionRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionAuthorizationRecord:
        """Record completion authorization."""
        record = self.get_completion(completion_id, user)
        auth_record = SafetyCompletionAuthorizationService.process_authorization(record, request, user)
        self.completion_repo.save(record)
        return auth_record

    def close_workflow(
        self,
        completion_id: str,
        request: CloseCompletionWorkflowRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionClosureRecord:
        """Request controlled workflow closure."""
        record = self.get_completion(completion_id, user)
        closure_record = SafetyCompletionClosureService.process_closure(record, request, user)
        self.completion_repo.save(record)
        return closure_record

    def reconcile_workflow(
        self,
        completion_id: str,
        request: ReconcileCompletionWorkflowRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyWorkflowCompletionRecord:
        """Reconcile updated destination outcomes or follow-up references."""
        record = self.get_completion(completion_id, user)
        review = self.review_repo.get(record.source_review_id)
        disposition = next((d for d in review.dispositions if d.disposition_id == record.source_disposition_id), None) if review else None
        if not review or not disposition:
            raise AppException(
                code=ErrorCode.SOURCE_DISPOSITION_NOT_FOUND,
                message="Source review or disposition not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        handoffs = self.handoff_repo.get_by_disposition_id(record.source_disposition_id)
        record = SafetyCompletionReconciliationService.reconcile(record, disposition, handoffs)
        return self.completion_repo.save(record)

    def reopen_workflow(
        self,
        completion_id: str,
        request: ReopenCompletionWorkflowRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionReopenRecord:
        """Request reopening under configured policy."""
        record = self.get_completion(completion_id, user)
        reopen_record = SafetyCompletionReopenService.process_reopen(record, request, user)
        self.completion_repo.save(record)
        return reopen_record

    def reassess_workflow(
        self,
        completion_id: str,
        request: ReassessCompletionWorkflowRequest,
        user: AuthenticatedUserContext,
    ) -> SafetyWorkflowCompletionRecord:
        """Request a new completion evaluation because relevant context has changed."""
        record = self.get_completion(completion_id, user)
        record.state = CompletionLifecycleState.REASSESSMENT_REQUIRED
        record.readiness_state = "REASSESSMENT_REQUIRED"
        record.history.append({
            "action": "REASSESSMENT_REQUESTED",
            "actor_id": user.user_id,
            "reason": request.reason,
            "target": request.target_authoritative_phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return self.completion_repo.save(record)

    # -----------------------------------------------------------------------
    # Listing and Filter Methods
    # -----------------------------------------------------------------------

    def list_completions(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        state: Optional[CompletionLifecycleState] = None,
        readiness_state: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List completions within tenant scope."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Patient role is not permitted to access safety governance records.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        target_facility = facility_id or user.facility_id if user.role != UserRole.ADMIN else facility_id
        return self.completion_repo.list_completions(
            organization_id=user.organization_id,
            facility_id=target_facility,
            state=state,
            readiness_state=readiness_state,
            limit=limit,
            offset=offset,
        )

    def list_pending(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List pending workflows with unresolved requirements."""
        if user.role == UserRole.PATIENT:
            raise AppException(code=ErrorCode.ACCESS_DENIED, message="Forbidden.", status_code=status.HTTP_403_FORBIDDEN)
        return self.completion_repo.list_pending(
            organization_id=user.organization_id,
            facility_id=facility_id or (user.facility_id if user.role != UserRole.ADMIN else None),
            limit=limit,
            offset=offset,
        )

    def list_blocked(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List blocked workflows."""
        if user.role == UserRole.PATIENT:
            raise AppException(code=ErrorCode.ACCESS_DENIED, message="Forbidden.", status_code=status.HTTP_403_FORBIDDEN)
        return self.completion_repo.list_blocked(
            organization_id=user.organization_id,
            facility_id=facility_id or (user.facility_id if user.role != UserRole.ADMIN else None),
            limit=limit,
            offset=offset,
        )

    def list_review_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List workflows awaiting authorized review."""
        if user.role == UserRole.PATIENT:
            raise AppException(code=ErrorCode.ACCESS_DENIED, message="Forbidden.", status_code=status.HTTP_403_FORBIDDEN)
        return self.completion_repo.list_review_required(
            organization_id=user.organization_id,
            facility_id=facility_id or (user.facility_id if user.role != UserRole.ADMIN else None),
            limit=limit,
            offset=offset,
        )

    def list_reopen_required(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List workflows requiring reopening or reassessment."""
        if user.role == UserRole.PATIENT:
            raise AppException(code=ErrorCode.ACCESS_DENIED, message="Forbidden.", status_code=status.HTTP_403_FORBIDDEN)
        return self.completion_repo.list_reopen_required(
            organization_id=user.organization_id,
            facility_id=facility_id or (user.facility_id if user.role != UserRole.ADMIN else None),
            limit=limit,
            offset=offset,
        )


# Module-level dependency provider
def get_safety_workflow_completion_service() -> SafetyWorkflowCompletionService:
    """Dependency provider for FastAPI."""
    return SafetyWorkflowCompletionService()

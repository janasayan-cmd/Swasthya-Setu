"""Phase 66: Primary Safety Post-Closure Verification Service.

Orchestrates post-closure integrity verification, upstream checks, finding management,
monitoring status, and governed lifecycle reconciliation.

Mandatory Safety Invariants:
1. Phase 65 closure does not mean that clinical risk has been eliminated.
2. A valid historical closure does not guarantee that the workflow remains valid indefinitely.
3. Post-closure verification does not independently certify clinical safety.
4. A change in an authoritative source does not automatically authorize reopening or modifying that source.
5. A detected discrepancy does not establish that a clinical error occurred.
6. A missing response from a dependency does not establish that the underlying workflow failed or succeeded.
7. A successful reconciliation does not replace clinical review, risk acceptance, assurance, or effectiveness evaluation.
8. A system-generated recommendation does not constitute an authorized governance decision.
9. A historical closure must remain auditable even when its current status becomes stale, conflicted, or reopened.
10. Phase 66 must never silently rewrite a previous closure decision to make it appear that the original decision never occurred.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_post_closure_verification_repository import (
    SafetyPostClosureVerificationRepository,
    get_safety_post_closure_verification_repository,
)
from app.repositories.safety_workflow_completion_repository import (
    SafetyWorkflowCompletionRepository,
    get_safety_workflow_completion_repository,
)
from app.schemas.auth import UserRole
from app.schemas.safety_integrity_finding import (
    FindingCategory,
    FindingLifecycleState,
    IntegrityFindingRecord,
    ResolveFindingRequest,
    ReviewFindingRequest,
)
from app.schemas.safety_post_closure_monitoring import (
    MonitoringPolicyConfig,
    PostClosureHistoryResponse,
    PostClosureMonitoringStatus,
    ReassessmentRecord,
    ReassessmentRequest,
    ReopeningCoordinationRecord,
    ReopeningCoordinationRequest,
)
from app.schemas.safety_post_closure_verification import (
    PostClosureVerificationRecord,
    TriggerPostClosureVerificationRequest,
    VerificationLifecycleState,
    VerificationRetryRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_completion_privacy_service import SafetyCompletionPrivacyService
from app.services.safety_integrity_check_service import SafetyIntegrityCheckService
from app.services.safety_lifecycle_reconciliation_service import (
    SafetyLifecycleReconciliationService,
)
from app.services.safety_materiality_evaluation_service import (
    SafetyMaterialityEvaluationService,
)
from app.services.safety_post_closure_monitoring_service import (
    SafetyPostClosureMonitoringService,
)


class SafetyPostClosureVerificationService:
    """Primary domain orchestrator for Phase 66 post-closure verification."""

    def __init__(
        self,
        verification_repo: Optional[SafetyPostClosureVerificationRepository] = None,
        completion_repo: Optional[SafetyWorkflowCompletionRepository] = None,
    ) -> None:
        self.verification_repo = verification_repo or get_safety_post_closure_verification_repository()
        self.completion_repo = completion_repo or get_safety_workflow_completion_repository()
        self.check_service = SafetyIntegrityCheckService()
        self.materiality_service = SafetyMaterialityEvaluationService()
        self.reconciliation_service = SafetyLifecycleReconciliationService(
            self.verification_repo, self.completion_repo
        )
        self.monitoring_service = SafetyPostClosureMonitoringService(
            self.verification_repo, self.completion_repo
        )

    # -------------------------------------------------------------------------
    # Verification Runs
    # -------------------------------------------------------------------------

    def trigger_verification(
        self,
        completion_id: str,
        request: TriggerPostClosureVerificationRequest,
        user: AuthenticatedUserContext,
    ) -> PostClosureVerificationRecord:
        """Trigger and execute an authoritative post-closure verification run."""
        # 1. Fetch completion
        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion workflow '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # 2. Access control check
        SafetyCompletionPrivacyService.validate_caller_access(
            user, completion.organization_id, completion.facility_id
        )

        # 3. Idempotency check
        if request.idempotency_key:
            existing = self.verification_repo.get_by_idempotency_key(
                request.idempotency_key, user.organization_id
            )
            if existing:
                return existing

        # 4. Initialize verification record
        policy = MonitoringPolicyConfig(policy_version=request.policy_version or "v1.0.0")
        hist_state = completion.state.value if hasattr(completion.state, "value") else str(completion.state)

        verif_record = PostClosureVerificationRecord(
            completion_id=completion_id,
            organization_id=completion.organization_id,
            facility_id=completion.facility_id,
            state=VerificationLifecycleState.RUNNING,
            historical_completion_state="CLOSED" if completion.closure else hist_state,
            current_coordination_state=hist_state,
            policy_version=policy.policy_version,
            idempotency_key=request.idempotency_key,
            correlation_id=request.correlation_id or verif_record_corr_id(),
            triggered_by=user.user_id,
            triggered_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            history=[
                {
                    "action": "VERIFICATION_INITIATED",
                    "actor_id": user.user_id,
                    "reason": request.reverification_reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        )
        self.verification_repo.save_verification(verif_record)

        # 5. Run integrity checks across Categories A-G
        findings, evaluated_checks, limitations = self.check_service.run_all_checks(
            completion=completion,
            verification_id=verif_record.verification_id,
            policy=policy,
        )

        # 6. Persist generated findings
        for f in findings:
            self.verification_repo.save_finding(f)

        # 7. Evaluate findings and compute authoritative result
        state, reassess_req, reopen_rec, rationale = self.materiality_service.evaluate(
            findings=findings,
            evaluated_checks=evaluated_checks,
            limitations=limitations,
            policy=policy,
        )

        # 8. Finalize verification run
        verif_record.state = state
        verif_record.reassessment_required = reassess_req
        verif_record.reopen_recommended = reopen_rec
        verif_record.findings_count = len(findings)
        verif_record.material_findings_count = sum(1 for f in findings if f.is_material)
        verif_record.limitations = limitations
        verif_record.rationale = rationale
        verif_record.evaluated_checks = evaluated_checks
        verif_record.completed_at = datetime.now(timezone.utc)
        verif_record.history.append({
            "action": "VERIFICATION_COMPLETED",
            "state": state.value,
            "reassessment_required": reassess_req,
            "reopen_recommended": reopen_rec,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self.verification_repo.save_verification(verif_record)

        # 9. Update monitoring status
        mon_status = self.monitoring_service.get_or_initialize_monitoring_status(
            completion_id=completion_id,
            organization_id=completion.organization_id,
            facility_id=completion.facility_id,
            policy=policy,
        )
        mon_status.last_verification_id = verif_record.verification_id
        mon_status.last_verification_state = state.value
        mon_status.last_verified_at = verif_record.completed_at
        mon_status.open_findings_count = len(findings)
        mon_status.critical_findings_count = sum(1 for f in findings if f.severity.value == "CRITICAL")
        mon_status.reassessment_required = reassess_req
        mon_status.reopen_recommended = reopen_rec
        self.verification_repo.save_monitoring_status(mon_status)

        return verif_record

    def retry_verification(
        self,
        completion_id: str,
        verification_id: str,
        request: VerificationRetryRequest,
        user: AuthenticatedUserContext,
    ) -> PostClosureVerificationRecord:
        """Retry an incomplete, failed, or dependency-interrupted verification run."""
        verification = self.verification_repo.get_verification(verification_id)
        if not verification or verification.completion_id != completion_id:
            raise AppException(
                code=ErrorCode.POST_CLOSURE_VERIFICATION_NOT_FOUND,
                message=f"Verification run '{verification_id}' not found for completion '{completion_id}'.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        SafetyCompletionPrivacyService.validate_caller_access(
            user, verification.organization_id, verification.facility_id
        )

        if verification.state == VerificationLifecycleState.VERIFIED:
            raise AppException(
                code=ErrorCode.VERIFICATION_RETRY_NOT_ALLOWED,
                message="Cannot retry a verification that is already VERIFIED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if verification.retry_count >= verification.max_retries:
            raise AppException(
                code=ErrorCode.VERIFICATION_RETRY_NOT_ALLOWED,
                message=f"Maximum retry limit ({verification.max_retries}) reached for verification '{verification_id}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Increment retry count and rerun
        verification.retry_count += 1
        verification.history.append({
            "action": "RETRY_ATTEMPTED",
            "retry_count": verification.retry_count,
            "reason": request.reason,
            "actor_id": user.user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion workflow '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        policy = MonitoringPolicyConfig(policy_version=verification.policy_version)
        findings, evaluated_checks, limitations = self.check_service.run_all_checks(
            completion=completion,
            verification_id=verification.verification_id,
            policy=policy,
        )

        for f in findings:
            self.verification_repo.save_finding(f)

        state, reassess_req, reopen_rec, rationale = self.materiality_service.evaluate(
            findings=findings,
            evaluated_checks=evaluated_checks,
            limitations=limitations,
            policy=policy,
        )

        verification.state = state
        verification.reassessment_required = reassess_req
        verification.reopen_recommended = reopen_rec
        verification.findings_count = len(findings)
        verification.material_findings_count = sum(1 for f in findings if f.is_material)
        verification.limitations = limitations
        verification.rationale = rationale
        verification.evaluated_checks = evaluated_checks
        verification.completed_at = datetime.now(timezone.utc)

        return self.verification_repo.save_verification(verification)

    def get_verification(
        self,
        completion_id: str,
        verification_id: str,
        user: AuthenticatedUserContext,
    ) -> PostClosureVerificationRecord:
        """Retrieve a specific verification execution by ID."""
        verification = self.verification_repo.get_verification(verification_id)
        if not verification or verification.completion_id != completion_id:
            raise AppException(
                code=ErrorCode.POST_CLOSURE_VERIFICATION_NOT_FOUND,
                message=f"Verification run '{verification_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyCompletionPrivacyService.validate_caller_access(
            user, verification.organization_id, verification.facility_id
        )
        return verification

    def list_verifications(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PostClosureVerificationRecord]:
        """List verification executions for a completion workflow."""
        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyCompletionPrivacyService.validate_caller_access(
            user, completion.organization_id, completion.facility_id
        )
        return self.verification_repo.list_verifications(
            completion_id=completion_id,
            organization_id=user.organization_id,
            limit=limit,
            offset=offset,
        )

    def list_pending_verifications(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PostClosureVerificationRecord]:
        """List active pending/scheduled verification runs for the tenant."""
        if user.role == UserRole.PATIENT:
            raise AppException(code=ErrorCode.ACCESS_DENIED, message="Forbidden.", status_code=status.HTTP_403_FORBIDDEN)
        return self.verification_repo.list_pending_verifications(
            organization_id=user.organization_id,
            facility_id=facility_id or (user.facility_id if user.role != UserRole.ADMIN else None),
            limit=limit,
            offset=offset,
        )

    def list_failed_verifications(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PostClosureVerificationRecord]:
        """List failed or interrupted verification runs for the tenant."""
        if user.role == UserRole.PATIENT:
            raise AppException(code=ErrorCode.ACCESS_DENIED, message="Forbidden.", status_code=status.HTTP_403_FORBIDDEN)
        return self.verification_repo.list_failed_verifications(
            organization_id=user.organization_id,
            facility_id=facility_id or (user.facility_id if user.role != UserRole.ADMIN else None),
            limit=limit,
            offset=offset,
        )

    # -------------------------------------------------------------------------
    # Integrity Findings
    # -------------------------------------------------------------------------

    def list_findings(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
        verification_id: Optional[str] = None,
        lifecycle_state: Optional[FindingLifecycleState] = None,
        category: Optional[FindingCategory] = None,
        is_material: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntegrityFindingRecord]:
        """List integrity findings for a completion workflow with optional filters."""
        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyCompletionPrivacyService.validate_caller_access(
            user, completion.organization_id, completion.facility_id
        )
        return self.verification_repo.list_findings(
            completion_id=completion_id,
            verification_id=verification_id,
            organization_id=user.organization_id,
            lifecycle_state=lifecycle_state,
            category=category,
            is_material=is_material,
            limit=limit,
            offset=offset,
        )

    def get_finding(
        self,
        completion_id: str,
        finding_id: str,
        user: AuthenticatedUserContext,
    ) -> IntegrityFindingRecord:
        """Retrieve an integrity finding by ID."""
        finding = self.verification_repo.get_finding(finding_id)
        if not finding or finding.completion_id != completion_id:
            raise AppException(
                code=ErrorCode.INTEGRITY_FINDING_NOT_FOUND,
                message=f"Finding '{finding_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyCompletionPrivacyService.validate_caller_access(
            user, finding.organization_id, finding.facility_id
        )
        return finding

    def review_finding(
        self,
        completion_id: str,
        finding_id: str,
        request: ReviewFindingRequest,
        user: AuthenticatedUserContext,
    ) -> IntegrityFindingRecord:
        """Review an integrity finding."""
        finding = self.get_finding(completion_id, finding_id, user)
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Patients cannot review clinical safety findings.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        finding.review_notes = request.notes
        finding.reviewed_by = user.user_id
        finding.reviewed_by_role = user.role.value if hasattr(user.role, "value") else str(user.role)
        finding.reviewed_at = datetime.now(timezone.utc)

        if request.action == "DISMISS":
            if not request.dismissal_rationale:
                raise AppException(
                    code=ErrorCode.INVALID_FINDING_STATE,
                    message="Dismissing an integrity finding requires an explicit dismissal rationale.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            finding.dismissal_rationale = request.dismissal_rationale
            finding.lifecycle_state = FindingLifecycleState.DISMISSED_WITH_RATIONALE
        elif request.action == "REQUEST_REASSESSMENT":
            finding.lifecycle_state = FindingLifecycleState.REASSESSMENT_REQUESTED
        elif request.action == "REQUEST_REOPEN":
            finding.lifecycle_state = FindingLifecycleState.REOPEN_REQUESTED
        else:
            finding.lifecycle_state = FindingLifecycleState.REVIEWED

        return self.verification_repo.save_finding(finding)

    def resolve_finding(
        self,
        completion_id: str,
        finding_id: str,
        request: ResolveFindingRequest,
        user: AuthenticatedUserContext,
    ) -> IntegrityFindingRecord:
        """Resolve an integrity finding while strictly preserving finding history."""
        finding = self.get_finding(completion_id, finding_id, user)
        if user.role not in (UserRole.ADMIN, UserRole.DOCTOR):
            raise AppException(
                code=ErrorCode.FINDING_RESOLUTION_UNAUTHORIZED,
                message="Only administrators or clinicians may resolve integrity findings.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        finding.resolution_evidence = request.resolution_evidence
        finding.resolution_notes = request.resolution_notes
        finding.resolved_by = user.user_id
        finding.resolved_by_role = user.role.value if hasattr(user.role, "value") else str(user.role)
        finding.resolved_at = datetime.now(timezone.utc)
        finding.lifecycle_state = FindingLifecycleState.RESOLVED

        return self.verification_repo.save_finding(finding)

    def list_review_required_findings(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntegrityFindingRecord]:
        """List findings awaiting review or resolution for the tenant."""
        if user.role == UserRole.PATIENT:
            raise AppException(code=ErrorCode.ACCESS_DENIED, message="Forbidden.", status_code=status.HTTP_403_FORBIDDEN)
        return self.verification_repo.list_review_required_findings(
            organization_id=user.organization_id,
            facility_id=facility_id or (user.facility_id if user.role != UserRole.ADMIN else None),
            limit=limit,
            offset=offset,
        )

    # -------------------------------------------------------------------------
    # Monitoring, Reassessment, Reopening & History
    # -------------------------------------------------------------------------

    def get_monitoring_status(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> PostClosureMonitoringStatus:
        """Get post-closure monitoring operational status."""
        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyCompletionPrivacyService.validate_caller_access(
            user, completion.organization_id, completion.facility_id
        )
        return self.monitoring_service.get_or_initialize_monitoring_status(
            completion_id=completion_id,
            organization_id=completion.organization_id,
            facility_id=completion.facility_id,
        )

    def request_reassessment(
        self,
        completion_id: str,
        request: ReassessmentRequest,
        user: AuthenticatedUserContext,
    ) -> ReassessmentRecord:
        """Submit a policy-controlled workflow reassessment request."""
        return self.reconciliation_service.request_reassessment(completion_id, request, user)

    def request_reopening(
        self,
        completion_id: str,
        request: ReopeningCoordinationRequest,
        user: AuthenticatedUserContext,
    ) -> ReopeningCoordinationRecord:
        """Submit a governed workflow reopening coordination request."""
        return self.reconciliation_service.request_reopening(completion_id, request, user)

    def get_post_closure_history(
        self,
        completion_id: str,
        user: AuthenticatedUserContext,
    ) -> PostClosureHistoryResponse:
        """Aggregate all post-closure verification history and preserve closure evidence."""
        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        SafetyCompletionPrivacyService.validate_caller_access(
            user, completion.organization_id, completion.facility_id
        )

        verifications = [
            v.model_dump()
            for v in self.verification_repo.list_verifications(completion_id, user.organization_id)
        ]
        findings = [
            f.model_dump()
            for f in self.verification_repo.list_findings(completion_id, organization_id=user.organization_id)
        ]
        reassessments = [
            r.model_dump()
            for r in self.verification_repo.list_reassessments(completion_id)
        ]
        reopenings = [
            c.model_dump()
            for c in self.verification_repo.list_reopening_coordinations(completion_id)
        ]

        return PostClosureHistoryResponse(
            completion_id=completion_id,
            organization_id=completion.organization_id,
            facility_id=completion.facility_id,
            verifications=verifications,
            findings=findings,
            reassessments=reassessments,
            reopenings=reopenings,
            closure_preserved=completion.closure,
        )


def verif_record_corr_id() -> str:
    import uuid
    return f"corr-{uuid.uuid4().hex[:12]}"


# Module-level dependency provider
def get_safety_post_closure_verification_service() -> SafetyPostClosureVerificationService:
    """Dependency provider for FastAPI."""
    return SafetyPostClosureVerificationService()

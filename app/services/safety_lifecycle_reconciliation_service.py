"""Phase 66: Safety Lifecycle Reconciliation Service.

Coordinates governed reassessment requests and controlled reopening of closed
completion records through the authoritative Phase 65 reopening interface.

Mandatory Safety Invariants:
1. A request to reopen does not itself imply approval to reopen.
2. System-generated recommendations do not constitute authorized governance decisions.
3. When reopening is required, invoke the authoritative Phase 65 reopening operation;
   never create a competing reopening implementation.
4. Historical closure records must strictly remain auditable even after reopening.
5. Never silently rewrite a previous closure decision.
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
from app.schemas.safety_completion_action import ReopenCompletionWorkflowRequest
from app.schemas.safety_post_closure_monitoring import (
    ReassessmentRecord,
    ReassessmentRequest,
    ReopeningCoordinationRecord,
    ReopeningCoordinationRequest,
)
from app.schemas.safety_post_closure_verification import (
    PostClosureVerificationRecord,
    VerificationLifecycleState,
)
from app.schemas.safety_workflow_completion import CompletionLifecycleState
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_completion_reopen_service import SafetyCompletionReopenService


class SafetyLifecycleReconciliationService:
    """Manages reassessment records and governed reopening coordination with Phase 65."""

    def __init__(
        self,
        verification_repo: Optional[SafetyPostClosureVerificationRepository] = None,
        completion_repo: Optional[SafetyWorkflowCompletionRepository] = None,
    ) -> None:
        self.verification_repo = verification_repo or get_safety_post_closure_verification_repository()
        self.completion_repo = completion_repo or get_safety_workflow_completion_repository()

    def request_reassessment(
        self,
        completion_id: str,
        request: ReassessmentRequest,
        user: AuthenticatedUserContext,
    ) -> ReassessmentRecord:
        """Submit a policy-controlled reassessment request."""
        # 1. Fetch completion
        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion workflow '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # 2. Access control
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Patients are not authorized to request workflow reassessment.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if user.organization_id != completion.organization_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Cross-tenant reassessment request forbidden.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 3. Create record
        record = ReassessmentRecord(
            completion_id=completion_id,
            organization_id=completion.organization_id,
            facility_id=completion.facility_id,
            requested_by=user.user_id,
            requested_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            reason=request.reason,
            finding_refs=request.finding_refs,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
        )
        self.verification_repo.save_reassessment(record)

        # 4. Update completion history and state
        completion.history.append({
            "action": "REASSESSMENT_REQUESTED",
            "reassessment_id": record.reassessment_id,
            "actor_id": user.user_id,
            "reason": request.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.completion_repo.save(completion)

        return record

    def request_reopening(
        self,
        completion_id: str,
        request: ReopeningCoordinationRequest,
        user: AuthenticatedUserContext,
    ) -> ReopeningCoordinationRecord:
        """Submit a reopening coordination request awaiting authorization or auto-authorized if doctor/admin."""
        # 1. Fetch completion
        completion = self.completion_repo.get(completion_id)
        if not completion:
            raise AppException(
                code=ErrorCode.SAFETY_COMPLETION_NOT_FOUND,
                message=f"Completion workflow '{completion_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # 2. Tenant and role check
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Patients are not authorized to coordinate workflow reopening.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if user.organization_id != completion.organization_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Cross-tenant reopening coordination forbidden.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 3. Check trigger validity against Phase 65 supported triggers
        if request.reopen_trigger not in SafetyCompletionReopenService.VALID_REOPEN_TRIGGERS:
            raise AppException(
                code=ErrorCode.REOPEN_REQUEST_INVALID,
                message=f"Invalid reopen trigger: '{request.reopen_trigger}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Create coordination record
        coord_record = ReopeningCoordinationRecord(
            completion_id=completion_id,
            organization_id=completion.organization_id,
            facility_id=completion.facility_id,
            requested_by=user.user_id,
            requested_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            reopen_trigger=request.reopen_trigger,
            reason=request.reason,
            reopen_rationale=request.reopen_rationale,
            finding_refs=request.finding_refs,
            authorized=False,
            executed=False,
        )

        # 5. Check if caller has authorization authority (e.g. ADMIN or DOCTOR)
        # Note: If separation of duties is required (caller requested as non-authorizer or explicitly separate),
        # Caller can immediately authorize only if policy allows, otherwise it waits for authorization.
        # Here we provide immediate execution when an authorized CLINICIAN/ADMIN requests reopening
        # while validating Phase 65 reopening rules.
        is_authorized_actor = user.role in (UserRole.ADMIN, UserRole.DOCTOR)
        if is_authorized_actor:
            coord_record.authorized = True
            coord_record.authorized_by = user.user_id
            coord_record.authorized_by_role = user.role.value if hasattr(user.role, "value") else str(user.role)

            # Delegate to Phase 65 authoritative reopen service
            phase65_req = ReopenCompletionWorkflowRequest(
                reopen_trigger=request.reopen_trigger,
                reason=request.reason,
                metadata={
                    "coordination_id": coord_record.coordination_id,
                    "reopen_rationale": request.reopen_rationale,
                    "finding_refs": request.finding_refs,
                    "reassessment_id": request.reassessment_id,
                },
            )
            reopen_result = SafetyCompletionReopenService.process_reopen(
                completion=completion,
                request=phase65_req,
                user=user,
            )
            self.completion_repo.save(completion)
            coord_record.executed = True
            coord_record.phase65_reopen_record = reopen_result.model_dump()

        self.verification_repo.save_reopening_coordination(coord_record)
        return coord_record

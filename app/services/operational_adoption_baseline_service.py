"""Phase 74: Operational Adoption Baseline Service.

Coordinates:
- Version-controlled operational baselines
- Draft, update, submission, and approval lifecycle
- Strict separation of duties (author cannot approve baseline)
- Automatic supersession of prior baselines and activation of monitoring
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_adoption_repository import (
    GovernanceChangeAdoptionRepository,
    get_governance_change_adoption_repository,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_change_adoption_registration import (
    AdoptionRegistrationStatus,
)
from app.schemas.operational_adoption_baseline import (
    ApproveBaselineRequest,
    BaselineApprovalStatus,
    CreateBaselineRequest,
    OperationalAdoptionBaselineRecord,
    SubmitBaselineRequest,
    UpdateBaselineRequest,
)


class OperationalAdoptionBaselineService:
    """Service governing version-controlled operational adoption baselines."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def create_baseline(
        self,
        registration_id: str,
        request: CreateBaselineRequest,
        current_user: AuthenticatedUserContext,
    ) -> OperationalAdoptionBaselineRecord:
        """Creates a new version-controlled operational baseline."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Check for duplicate version in this registration
        existing_baselines = self.repo.list_baselines_for_registration(registration_id, current_user.tenant_id)
        for b in existing_baselines:
            if b.version == request.version:
                raise AppException(
                    code=ErrorCode.INVALID_OPERATIONAL_BASELINE_STATE,
                    message=f"Baseline version '{request.version}' already exists for registration '{registration_id}'.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        now = datetime.now(timezone.utc).isoformat()
        baseline_id = f"oab_{uuid.uuid4().hex[:12]}"

        record = OperationalAdoptionBaselineRecord(
            baseline_id=baseline_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            version=request.version,
            previous_version_id=request.previous_version_id,
            change_reason=request.change_reason,
            intended_operational_process=request.intended_operational_process,
            expected_workflow_behavior=request.expected_workflow_behavior,
            required_operational_practices=request.required_operational_practices,
            operational_scope=request.operational_scope,
            responsible_roles=request.responsible_roles,
            required_training_programmes=request.required_training_programmes,
            required_procedural_docs=request.required_procedural_docs,
            operational_readiness_criteria=request.operational_readiness_criteria,
            required_evidence_types=request.required_evidence_types,
            monitoring_frequency=request.monitoring_frequency,
            known_limitations=request.known_limitations,
            system_dependencies=request.system_dependencies,
            approved_exceptions_summary=request.approved_exceptions_summary,
            status=BaselineApprovalStatus.DRAFT,
            author_id=current_user.user_id,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_baseline(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.baseline_created",
            actor_id=current_user.user_id,
            summary=f"Operational baseline version {saved.version} created (Draft).",
            details={"baseline_id": saved.baseline_id, "version": saved.version},
        )
        return saved

    def get_baseline(
        self, baseline_id: str, current_user: AuthenticatedUserContext
    ) -> OperationalAdoptionBaselineRecord:
        """Retrieves a baseline by ID with tenant isolation."""
        baseline = self.repo.get_baseline(baseline_id)
        if not baseline or baseline.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.OPERATIONAL_BASELINE_NOT_FOUND,
                message=f"Operational baseline '{baseline_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return baseline

    def list_baselines_for_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> List[OperationalAdoptionBaselineRecord]:
        """Lists all baselines for an adoption registration."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_baselines_for_registration(registration_id, current_user.tenant_id)

    def submit_baseline(
        self,
        baseline_id: str,
        request: SubmitBaselineRequest,
        current_user: AuthenticatedUserContext,
    ) -> OperationalAdoptionBaselineRecord:
        """Submits a baseline draft for authoritative governance approval."""
        baseline = self.get_baseline(baseline_id, current_user)
        if baseline.status != BaselineApprovalStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_OPERATIONAL_BASELINE_STATE,
                message=f"Baseline cannot be submitted from status '{baseline.status.value}'. Must be DRAFT.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        updated_dict = baseline.model_dump()
        updated_dict["status"] = BaselineApprovalStatus.SUBMITTED
        updated_dict["submitted_by"] = current_user.user_id
        updated_dict["submitted_at"] = datetime.now(timezone.utc).isoformat()
        updated_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

        updated_rec = OperationalAdoptionBaselineRecord(**updated_dict)
        saved = self.repo.save_baseline(updated_rec)

        self.repo.log_timeline_event(
            registration_id=baseline.registration_id,
            event_type="governance_change_adoption.baseline_submitted",
            actor_id=current_user.user_id,
            summary=f"Operational baseline version {saved.version} submitted for approval.",
            details={"submission_notes": request.submission_notes},
        )
        return saved

    def approve_baseline(
        self,
        baseline_id: str,
        request: ApproveBaselineRequest,
        current_user: AuthenticatedUserContext,
    ) -> OperationalAdoptionBaselineRecord:
        """Approves a submitted operational baseline.
        
        Strictly enforces Separation of Duties: The author cannot approve their own baseline.
        """
        baseline = self.get_baseline(baseline_id, current_user)
        if baseline.status != BaselineApprovalStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_OPERATIONAL_BASELINE_STATE,
                message=f"Baseline cannot be approved from status '{baseline.status.value}'. Must be SUBMITTED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce separation of duties: author cannot approve
        if current_user.user_id == baseline.author_id:
            raise AppException(
                code=ErrorCode.ADOPTION_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: baseline author cannot approve their own baseline.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        now = datetime.now(timezone.utc).isoformat()

        # Supersede any currently approved baselines for this registration
        all_baselines = self.repo.list_baselines_for_registration(
            baseline.registration_id, current_user.tenant_id
        )
        for prior in all_baselines:
            if prior.status == BaselineApprovalStatus.APPROVED and prior.baseline_id != baseline.baseline_id:
                p_dict = prior.model_dump()
                p_dict["status"] = BaselineApprovalStatus.SUPERSEDED
                p_dict["updated_at"] = now
                self.repo.save_baseline(OperationalAdoptionBaselineRecord(**p_dict))

        # Approve this baseline
        updated_dict = baseline.model_dump()
        updated_dict["status"] = BaselineApprovalStatus.APPROVED
        updated_dict["approved_by"] = current_user.user_id
        updated_dict["approved_at"] = now
        updated_dict["approval_authority_role"] = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        updated_dict["effective_date"] = request.effective_date
        updated_dict["updated_at"] = now

        approved_rec = OperationalAdoptionBaselineRecord(**updated_dict)
        saved = self.repo.save_baseline(approved_rec)

        # Update registration active baseline & transition from PENDING_BASELINE to ACTIVE_MONITORING
        reg = self.repo.get_registration(baseline.registration_id)
        if reg:
            reg_dict = reg.model_dump()
            reg_dict["active_baseline_id"] = saved.baseline_id
            reg_dict["current_baseline_version"] = saved.version
            if reg.status == AdoptionRegistrationStatus.PENDING_BASELINE:
                reg_dict["status"] = AdoptionRegistrationStatus.ACTIVE_MONITORING
            reg_dict["updated_at"] = now
            self.repo.save_registration(type(reg)(**reg_dict))

        self.repo.log_timeline_event(
            registration_id=baseline.registration_id,
            event_type="governance_change_adoption.baseline_approved",
            actor_id=current_user.user_id,
            summary=f"Operational baseline version {saved.version} approved by {current_user.user_id}.",
            details={"effective_date": request.effective_date, "comments": request.approval_comments},
        )
        return saved

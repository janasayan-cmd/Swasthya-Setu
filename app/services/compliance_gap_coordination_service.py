"""Phase 69: Compliance Gap & Corrective Action Coordination Service.

Coordinates:
- Governed human specialist reviews on compliance gaps/findings
- Finding resolution with traceable evidence
- Routing corrective action requests through Phase 54 controlled governance action orchestration
- Integrating with Phase 55 effectiveness evaluation where policy requires
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_compliance_repository import (
    GovernanceComplianceRepository,
    get_governance_compliance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.compliance_finding import (
    ComplianceFindingRecord,
    ResolveFindingRequest,
    ReviewFindingRequest,
)
from app.schemas.compliance_package_report import (
    ComplianceCorrectiveActionRequestRecord,
    CorrectiveActionStatus,
    SubmitCorrectiveActionRequest,
)
from app.schemas.user import AuthenticatedUserContext


class ComplianceGapCoordinationService:
    """Service managing compliance finding reviews, resolutions, and Phase 54 action requests."""

    def __init__(self, repository: Optional[GovernanceComplianceRepository] = None) -> None:
        self.repository = repository or get_governance_compliance_repository()

    def get_finding(
        self, user: AuthenticatedUserContext, finding_id: str
    ) -> ComplianceFindingRecord:
        """Retrieve finding and ensure tenant boundary integrity."""
        finding = self.repository.get_finding(finding_id)
        if not finding:
            raise AppException(
                code=ErrorCode.COMPLIANCE_FINDING_NOT_FOUND,
                message=f"Compliance finding {finding_id} not found.",
                status_code=404,
            )
        req = self.repository.get_requirement(finding.requirement_id)
        if req and req.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access finding across tenant boundaries.",
                status_code=403,
            )
        return finding

    def review_finding(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: ReviewFindingRequest,
    ) -> ComplianceFindingRecord:
        """Conduct formal human governance review on a compliance gap."""
        finding = self.get_finding(user, finding_id)

        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot conduct compliance reviews.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        finding.review_outcome = payload.review_outcome
        finding.review_rationale = payload.review_rationale
        finding.recommended_action = payload.recommended_action
        finding.reviewed_by = user.user_id
        finding.reviewed_at = now

        return self.repository.save_finding(finding)

    def resolve_finding(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: ResolveFindingRequest,
    ) -> ComplianceFindingRecord:
        """Resolve a compliance finding with documented governance justification."""
        finding = self.get_finding(user, finding_id)

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can resolve findings.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        finding.is_resolved = True
        finding.resolution_rationale = payload.resolution_rationale
        finding.resolved_by = user.user_id
        finding.resolved_at = now
        finding.evidence_refs.extend(payload.supporting_evidence_refs or [])

        return self.repository.save_finding(finding)

    def submit_corrective_action(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: SubmitCorrectiveActionRequest,
    ) -> ComplianceCorrectiveActionRequestRecord:
        """Submit a formal corrective action request directed to Phase 54 orchestration."""
        finding = self.get_finding(user, finding_id)

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can request corrective actions.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        action_record = ComplianceCorrectiveActionRequestRecord(
            finding_id=finding.finding_id,
            requirement_id=finding.requirement_id,
            target_phase="PHASE_54_CONTROLLED_ACTION",
            target_action_id=payload.phase54_action_ref or f"p54-act-{finding_id[-6:]}",
            status=CorrectiveActionStatus.SUBMITTED,
            reason=payload.reason,
            required_outcome=payload.required_outcome,
            requested_by=user.user_id,
            requested_at=now,
            phase54_action_ref=payload.phase54_action_ref,
            phase55_eval_ref=f"p55-eval-{finding_id[-6:]}" if payload.phase55_effectiveness_required else None,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_corrective_action(action_record)

    def list_corrective_actions(
        self, user: AuthenticatedUserContext, finding_id: str
    ) -> List[ComplianceCorrectiveActionRequestRecord]:
        """List corrective action requests recorded for a finding."""
        self.get_finding(user, finding_id)
        return self.repository.list_corrective_actions_for_finding(finding_id)


# Global singleton
_global_gap_service = ComplianceGapCoordinationService()


def get_compliance_gap_coordination_service() -> ComplianceGapCoordinationService:
    """Dependency provider for compliance gap coordination service."""
    return _global_gap_service

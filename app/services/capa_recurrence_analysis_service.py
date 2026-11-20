"""Phase 71: Corrective Action Recurrence Analysis Service.

Coordinates:
- Integration with Phase 54 action references and Phase 55 effectiveness reviews
- Detection of recurring findings following corrective action implementation
- Preservation of authoritative Phase 54/55 ownership (does not infer action failure without verification)
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_intelligence_repository import (
    GovernanceAuditIntelligenceRepository,
    get_governance_audit_intelligence_repository,
)
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_capa_recurrence import (
    CAPARecurrenceRecord,
    CAPARecurrenceStatus,
)
from app.schemas.audit_finding_response import AuditFindingStatus
from app.schemas.user import AuthenticatedUserContext


class CAPARecurrenceAnalysisService:
    """Service evaluating whether findings recur after corrective action implementation."""

    def __init__(
        self,
        audit_repo: Optional[GovernanceAuditRepository] = None,
        intel_repo: Optional[GovernanceAuditIntelligenceRepository] = None,
    ) -> None:
        self.audit_repo = audit_repo or get_governance_audit_repository()
        self.intel_repo = intel_repo or get_governance_audit_intelligence_repository()

    def analyze_recurrence(
        self, user: AuthenticatedUserContext
    ) -> List[CAPARecurrenceRecord]:
        """Examine tenant findings linked to corrective actions and identify recurrences."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot access CAPA recurrence analytics.",
                status_code=403,
            )

        all_audits = self.audit_repo.list_audits(organization_id=user.organization_id)
        audit_map = {a.audit_id: a for a in all_audits}

        all_findings = self.audit_repo.list_findings_for_audit()
        tenant_findings = [
            f for f in all_findings
            if f.audit_id in audit_map and f.status != AuditFindingStatus.WITHDRAWN
        ]

        # Findings that have an authoritative Phase 54 corrective action reference
        capa_findings = [f for f in tenant_findings if f.corrective_action_ref]

        now = datetime.now(timezone.utc)
        results: List[CAPARecurrenceRecord] = []

        for f in capa_findings:
            # Look for subsequent findings sharing the same category or control created AFTER f
            subsequent = [
                sub for sub in tenant_findings
                if sub.finding_id != f.finding_id
                and sub.created_at > f.created_at
                and (
                    (sub.criterion_id and f.criterion_id and sub.criterion_id == f.criterion_id)
                    or (sub.category == f.category)
                )
            ]

            sub_ids = [sub.finding_id for sub in subsequent]

            # Categorize recurrence status
            if not subsequent:
                status = CAPARecurrenceStatus.NO_RECURRENCE_OBSERVED
                notes = "No subsequent findings matching this control or category detected."
            elif f.phase55_eval_ref:
                # If an effectiveness review reference is present, recurrence is classified as confirmed/suspected
                status = CAPARecurrenceStatus.RECURRENCE_CONFIRMED
                notes = (
                    f"Subsequent findings {sub_ids} detected following Phase 55 effectiveness review link "
                    f"'{f.phase55_eval_ref}'."
                )
            elif f.is_closed:
                status = CAPARecurrenceStatus.RECURRENCE_SUSPECTED
                notes = (
                    f"Initial finding was marked closed, but subsequent related findings {sub_ids} "
                    f"emerged in later audits."
                )
            else:
                status = CAPARecurrenceStatus.IMPLEMENTED_UNVERIFIED
                notes = (
                    f"Corrective action '{f.corrective_action_ref}' is linked, but initial finding remains "
                    f"open with {len(subsequent)} related observations."
                )

            record = CAPARecurrenceRecord(
                initial_finding_id=f.finding_id,
                corrective_action_ref=f.corrective_action_ref,
                phase55_eval_ref=f.phase55_eval_ref,
                action_title=f"CAPA for {f.finding_id}",
                recurrence_status=status,
                action_implementation_date=f.updated_at,
                effectiveness_outcome=None,  # Preserves Phase 55 authority
                subsequent_related_finding_ids=sub_ids,
                temporal_context=f"Initial finding created {f.created_at.date().isoformat()}",
                analytical_notes=notes,
                organization_id=user.organization_id,
                created_at=now,
            )
            saved = self.intel_repo.save_capa_recurrence(record)
            results.append(saved)

        return results

    def get_recurrence_by_finding(
        self, user: AuthenticatedUserContext, finding_id: str
    ) -> Optional[CAPARecurrenceRecord]:
        """Retrieve recurrence record for a specific finding."""
        # Ensure finding belongs to user's tenant
        finding = self.audit_repo.get_finding(finding_id)
        if not finding:
            raise AppException(
                code=ErrorCode.AUDIT_FINDING_NOT_FOUND,
                message=f"Finding {finding_id} not found.",
                status_code=404,
            )
        audit = self.audit_repo.get_audit(finding.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access finding across tenant boundaries.",
                status_code=403,
            )

        return self.intel_repo.get_capa_recurrence_by_finding(finding_id)

    def list_recurrences(
        self,
        user: AuthenticatedUserContext,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CAPARecurrenceRecord]:
        """List CAPA recurrence records within tenant scope."""
        records = self.intel_repo.list_capa_recurrences(
            organization_id=user.organization_id, status=status, limit=limit, offset=offset
        )
        if not records:
            # Trigger analysis if none yet persisted
            records = self.analyze_recurrence(user)
            if status:
                records = [r for r in records if r.recurrence_status.value == status]
            return records[offset : offset + limit]
        return records


# Global singleton
_global_capa_service = CAPARecurrenceAnalysisService()


def get_capa_recurrence_analysis_service() -> CAPARecurrenceAnalysisService:
    """Dependency provider for CAPA recurrence analysis service."""
    return _global_capa_service

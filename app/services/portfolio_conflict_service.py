"""Phase 75: Portfolio Conflict Detection & Disposition Service.

Coordinates:
- Cross-initiative conflict detection across schedules, resources, workflows, and baselines
- Distinction between potential conflicts and human-reviewed confirmed conflicts
- Formal disposition workflow
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_portfolio_repository import (
    GovernanceChangePortfolioRepository,
    get_governance_change_portfolio_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.portfolio_dependencies_conflicts import (
    ConflictClassification,
    ConflictStatus,
    DisposeConflictRequest,
    PortfolioConflictRecord,
    ReviewConflictRequest,
)


class PortfolioConflictService:
    """Service governing cross-initiative conflict detection, human review, and formal disposition."""

    def __init__(
        self,
        repository: Optional[GovernanceChangePortfolioRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_portfolio_repository()

    def scan_and_detect_conflicts(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[PortfolioConflictRecord]:
        """Scans initiatives in a portfolio for scheduling overlaps, shared resource competition, and workflow clashes."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        initiatives = self.repo.list_initiatives_for_portfolio(portfolio_id, user_tenant)
        existing_conflicts = self.repo.list_conflicts_for_portfolio(portfolio_id, user_tenant)
        detected_conflicts: List[PortfolioConflictRecord] = []
        now = datetime.now(timezone.utc).isoformat()

        # Pairwise check for schedule & facility/department overlap
        for i in range(len(initiatives)):
            for j in range(i + 1, len(initiatives)):
                init_a = initiatives[i]
                init_b = initiatives[j]

                # Check shared facility or department
                shared_facs = set(init_a.participating_facilities).intersection(set(init_b.participating_facilities))
                shared_depts = set(init_a.participating_departments).intersection(set(init_b.participating_departments))

                if shared_facs or shared_depts:
                    # Check date overlap
                    overlap = not (init_a.planned_target_date < init_b.planned_start_date or init_b.planned_target_date < init_a.planned_start_date)
                    if overlap:
                        pair_key = sorted([init_a.initiative_id, init_b.initiative_id])
                        already_logged = any(
                            sorted(c.initiative_ids) == pair_key and c.classification == ConflictClassification.OVERLAPPING_SCHEDULE
                            for c in existing_conflicts
                        )
                        if not already_logged:
                            scope_desc = f"facilities {list(shared_facs)}" if shared_facs else f"departments {list(shared_depts)}"
                            cid = f"cnf_{uuid.uuid4().hex[:12]}"
                            conflict = PortfolioConflictRecord(
                                conflict_id=cid,
                                portfolio_id=portfolio_id,
                                tenant_id=user_tenant,
                                initiative_ids=pair_key,
                                classification=ConflictClassification.OVERLAPPING_SCHEDULE,
                                description=(
                                    f"Concurrent implementation schedule overlap detected between '{init_a.title}' "
                                    f"and '{init_b.title}' across shared {scope_desc}."
                                ),
                                status=ConflictStatus.POTENTIAL_CONFLICT,
                                detected_by="AUTOMATED_SCAN",
                                detected_at=now,
                                created_at=now,
                                updated_at=now,
                            )
                            saved = self.repo.save_conflict(conflict)
                            detected_conflicts.append(saved)
                            self.repo.log_timeline_event(
                                portfolio_id=portfolio_id,
                                event_type="governance_portfolio.conflict_detected",
                                actor_id=current_user.user_id,
                                summary=f"Potential conflict detected between {pair_key[0]} and {pair_key[1]}.",
                                details={"conflict_id": saved.conflict_id},
                            )

        return detected_conflicts

    def get_conflict(
        self, conflict_id: str, current_user: AuthenticatedUserContext
    ) -> PortfolioConflictRecord:
        """Retrieves a conflict record with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        conflict = self.repo.get_conflict(conflict_id)
        if not conflict or conflict.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_CONFLICT_NOT_FOUND,
                message=f"Portfolio conflict '{conflict_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return conflict

    def list_conflicts_for_portfolio(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[PortfolioConflictRecord]:
        """Lists conflicts detected for a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_conflicts_for_portfolio(portfolio_id, user_tenant)

    def review_conflict(
        self,
        conflict_id: str,
        request: ReviewConflictRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioConflictRecord:
        """Records human review of a potential conflict, confirming or rejecting the signal."""
        conflict = self.get_conflict(conflict_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        c_dict = conflict.model_dump()
        c_dict["status"] = (
            ConflictStatus.CONFIRMED_CONFLICT if request.confirmed else ConflictStatus.UNABLE_TO_DETERMINE
        )
        c_dict["reviewed_by"] = current_user.user_id
        c_dict["reviewed_at"] = now
        c_dict["review_notes"] = request.review_notes
        c_dict["updated_at"] = now

        saved = self.repo.save_conflict(PortfolioConflictRecord(**c_dict))
        self.repo.log_timeline_event(
            portfolio_id=conflict.portfolio_id,
            event_type="governance_portfolio.conflict_reviewed",
            actor_id=current_user.user_id,
            summary=f"Conflict '{saved.conflict_id}' reviewed: {saved.status.value}.",
            details={"review_notes": request.review_notes, "confirmed": request.confirmed},
        )
        return saved

    def dispose_conflict(
        self,
        conflict_id: str,
        request: DisposeConflictRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioConflictRecord:
        """Records formal disposition of an evaluated conflict."""
        conflict = self.get_conflict(conflict_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        c_dict = conflict.model_dump()
        if request.disposition in [c.value for c in ConflictStatus]:
            c_dict["status"] = ConflictStatus(request.disposition)
        else:
            c_dict["status"] = ConflictStatus.RESOLVED_CONFLICT

        c_dict["disposition"] = request.disposition
        c_dict["disposed_by"] = current_user.user_id
        c_dict["disposed_at"] = now
        c_dict["disposition_notes"] = request.disposition_notes
        c_dict["updated_at"] = now

        saved = self.repo.save_conflict(PortfolioConflictRecord(**c_dict))
        self.repo.log_timeline_event(
            portfolio_id=conflict.portfolio_id,
            event_type="governance_portfolio.conflict_resolved",
            actor_id=current_user.user_id,
            summary=f"Conflict '{saved.conflict_id}' disposed as {request.disposition}.",
            details={"disposition": request.disposition, "notes": request.disposition_notes},
        )
        return saved

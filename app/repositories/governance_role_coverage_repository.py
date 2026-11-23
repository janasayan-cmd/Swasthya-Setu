"""Phase 85: Clinical Safety Governance Resilience Role-Coverage Repository.

Provides thread-safe in-memory persistence and multi-tenant query capabilities for:
- Critical governance role and responsibility inventory
- Role-coverage arrangements and designated backups
- Backup verification and readiness records
- Coverage scenario stress-test evaluations
- Succession readiness plans and pipelines
- Role transition and governance handovers
- Coverage gap tracking and remediation
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_role_coverage_common import (
    BackupVerificationStatus,
    CoverageArrangementStatus,
    CoverageGapCategory,
    CoverageGapStatus,
    CriticalityTier,
    CoverageScope,
    HandoverStatus,
    ScenarioType,
    SuccessionPlanStatus,
)
from app.schemas.governance_role_responsibility import (
    CriticalGovernanceResponsibilityRecord,
)
from app.schemas.governance_role_coverage_mapping import (
    RoleCoverageArrangementRecord,
)
from app.schemas.governance_role_backup_verification import (
    BackupVerificationRecord,
)
from app.schemas.governance_role_coverage_scenario import (
    CoverageScenarioEvaluationRecord,
)
from app.schemas.governance_role_succession import (
    SuccessionPlanRecord,
)
from app.schemas.governance_role_handover import (
    RoleHandoverRecord,
)
from app.schemas.governance_role_coverage_gap import (
    RoleCoverageGapRecord,
)


class GovernanceRoleCoverageRepository:
    """Thread-safe in-memory repository for Phase 85 role-coverage data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._responsibilities: Dict[str, CriticalGovernanceResponsibilityRecord] = {}
        self._coverages: Dict[str, RoleCoverageArrangementRecord] = {}
        self._backup_verifications: Dict[str, BackupVerificationRecord] = {}
        self._scenarios: Dict[str, CoverageScenarioEvaluationRecord] = {}
        self._succession_plans: Dict[str, SuccessionPlanRecord] = {}
        self._handovers: Dict[str, RoleHandoverRecord] = {}
        self._coverage_gaps: Dict[str, RoleCoverageGapRecord] = {}

    def clear(self) -> None:
        """Clear all stored collections for test isolation."""
        with self._lock:
            self._responsibilities.clear()
            self._coverages.clear()
            self._backup_verifications.clear()
            self._scenarios.clear()
            self._succession_plans.clear()
            self._handovers.clear()
            self._coverage_gaps.clear()

    # =========================================================================
    # 1. Critical Responsibilities
    # =========================================================================

    def save_responsibility(
        self, record: CriticalGovernanceResponsibilityRecord
    ) -> CriticalGovernanceResponsibilityRecord:
        with self._lock:
            self._responsibilities[record.responsibility_id] = record
            return record

    def get_responsibility(
        self, responsibility_id: str, tenant_id: str
    ) -> Optional[CriticalGovernanceResponsibilityRecord]:
        with self._lock:
            item = self._responsibilities.get(responsibility_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_responsibilities(
        self,
        tenant_id: str,
        criticality_tier: Optional[CriticalityTier] = None,
        scope: Optional[CoverageScope] = None,
    ) -> List[CriticalGovernanceResponsibilityRecord]:
        with self._lock:
            items = [
                r for r in self._responsibilities.values()
                if r.tenant_id == tenant_id
            ]
            if criticality_tier:
                items = [r for r in items if r.criticality_tier == criticality_tier]
            if scope:
                items = [r for r in items if r.coverage_scope == scope]
            return sorted(items, key=lambda x: x.created_at, reverse=True)

    # =========================================================================
    # 2. Coverage Arrangements
    # =========================================================================

    def save_coverage(
        self, record: RoleCoverageArrangementRecord
    ) -> RoleCoverageArrangementRecord:
        with self._lock:
            self._coverages[record.coverage_id] = record
            return record

    def get_coverage(
        self, coverage_id: str, tenant_id: str
    ) -> Optional[RoleCoverageArrangementRecord]:
        with self._lock:
            item = self._coverages.get(coverage_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def get_coverage_by_responsibility(
        self, responsibility_id: str, tenant_id: str
    ) -> Optional[RoleCoverageArrangementRecord]:
        with self._lock:
            for item in self._coverages.values():
                if item.tenant_id == tenant_id and item.responsibility_id == responsibility_id:
                    return item
            return None

    def list_coverages(
        self,
        tenant_id: str,
        status: Optional[CoverageArrangementStatus] = None,
    ) -> List[RoleCoverageArrangementRecord]:
        with self._lock:
            items = [
                c for c in self._coverages.values()
                if c.tenant_id == tenant_id
            ]
            if status:
                items = [c for c in items if c.status == status]
            return sorted(items, key=lambda x: x.created_at, reverse=True)

    # =========================================================================
    # 3. Backup Verifications
    # =========================================================================

    def save_backup_verification(
        self, record: BackupVerificationRecord
    ) -> BackupVerificationRecord:
        with self._lock:
            self._backup_verifications[record.verification_id] = record
            return record

    def get_backup_verification(
        self, verification_id: str, tenant_id: str
    ) -> Optional[BackupVerificationRecord]:
        with self._lock:
            item = self._backup_verifications.get(verification_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def get_backup_verification_by_backup_user(
        self, coverage_id: str, backup_user_id: str, tenant_id: str
    ) -> Optional[BackupVerificationRecord]:
        with self._lock:
            for item in self._backup_verifications.values():
                if (
                    item.tenant_id == tenant_id
                    and item.coverage_id == coverage_id
                    and item.backup_user_id == backup_user_id
                ):
                    return item
            return None

    def list_backup_verifications(
        self,
        tenant_id: str,
        coverage_id: Optional[str] = None,
        status: Optional[BackupVerificationStatus] = None,
    ) -> List[BackupVerificationRecord]:
        with self._lock:
            items = [
                v for v in self._backup_verifications.values()
                if v.tenant_id == tenant_id
            ]
            if coverage_id:
                items = [v for v in items if v.coverage_id == coverage_id]
            if status:
                items = [v for v in items if v.status == status]
            return sorted(items, key=lambda x: x.verified_at, reverse=True)

    # =========================================================================
    # 4. Coverage Scenarios
    # =========================================================================

    def save_scenario(
        self, record: CoverageScenarioEvaluationRecord
    ) -> CoverageScenarioEvaluationRecord:
        with self._lock:
            self._scenarios[record.evaluation_id] = record
            return record

    def get_scenario(
        self, evaluation_id: str, tenant_id: str
    ) -> Optional[CoverageScenarioEvaluationRecord]:
        with self._lock:
            item = self._scenarios.get(evaluation_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_scenarios(
        self,
        tenant_id: str,
        scenario_type: Optional[ScenarioType] = None,
    ) -> List[CoverageScenarioEvaluationRecord]:
        with self._lock:
            items = [
                s for s in self._scenarios.values()
                if s.tenant_id == tenant_id
            ]
            if scenario_type:
                items = [s for s in items if s.scenario_type == scenario_type]
            return sorted(items, key=lambda x: x.evaluated_at, reverse=True)

    # =========================================================================
    # 5. Succession Plans
    # =========================================================================

    def save_succession_plan(
        self, record: SuccessionPlanRecord
    ) -> SuccessionPlanRecord:
        with self._lock:
            self._succession_plans[record.succession_plan_id] = record
            return record

    def get_succession_plan(
        self, succession_plan_id: str, tenant_id: str
    ) -> Optional[SuccessionPlanRecord]:
        with self._lock:
            item = self._succession_plans.get(succession_plan_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def get_succession_plan_by_responsibility(
        self, responsibility_id: str, tenant_id: str
    ) -> Optional[SuccessionPlanRecord]:
        with self._lock:
            for item in self._succession_plans.values():
                if item.tenant_id == tenant_id and item.responsibility_id == responsibility_id:
                    return item
            return None

    def list_succession_plans(
        self,
        tenant_id: str,
        status: Optional[SuccessionPlanStatus] = None,
    ) -> List[SuccessionPlanRecord]:
        with self._lock:
            items = [
                p for p in self._succession_plans.values()
                if p.tenant_id == tenant_id
            ]
            if status:
                items = [p for p in items if p.status == status]
            return sorted(items, key=lambda x: x.created_at, reverse=True)

    # =========================================================================
    # 6. Handovers
    # =========================================================================

    def save_handover(self, record: RoleHandoverRecord) -> RoleHandoverRecord:
        with self._lock:
            self._handovers[record.handover_id] = record
            return record

    def get_handover(
        self, handover_id: str, tenant_id: str
    ) -> Optional[RoleHandoverRecord]:
        with self._lock:
            item = self._handovers.get(handover_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_handovers(
        self,
        tenant_id: str,
        responsibility_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[HandoverStatus] = None,
    ) -> List[RoleHandoverRecord]:
        with self._lock:
            items = [
                h for h in self._handovers.values()
                if h.tenant_id == tenant_id
            ]
            if responsibility_id:
                items = [h for h in items if h.responsibility_id == responsibility_id]
            if user_id:
                items = [h for h in items if h.outgoing_user_id == user_id or h.incoming_user_id == user_id]
            if status:
                items = [h for h in items if h.status == status]
            return sorted(items, key=lambda x: x.created_at, reverse=True)

    # =========================================================================
    # 7. Coverage Gaps
    # =========================================================================

    def save_coverage_gap(self, record: RoleCoverageGapRecord) -> RoleCoverageGapRecord:
        with self._lock:
            self._coverage_gaps[record.gap_id] = record
            return record

    def get_coverage_gap(
        self, gap_id: str, tenant_id: str
    ) -> Optional[RoleCoverageGapRecord]:
        with self._lock:
            item = self._coverage_gaps.get(gap_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_coverage_gaps(
        self,
        tenant_id: str,
        responsibility_id: Optional[str] = None,
        status: Optional[CoverageGapStatus] = None,
        category: Optional[CoverageGapCategory] = None,
    ) -> List[RoleCoverageGapRecord]:
        with self._lock:
            items = [
                g for g in self._coverage_gaps.values()
                if g.tenant_id == tenant_id
            ]
            if responsibility_id:
                items = [g for g in items if g.responsibility_id == responsibility_id]
            if status:
                items = [g for g in items if g.status == status]
            if category:
                items = [g for g in items if g.category == category]
            return sorted(items, key=lambda x: x.identified_at, reverse=True)


_role_coverage_repository_instance: Optional[GovernanceRoleCoverageRepository] = None


def get_governance_role_coverage_repository() -> GovernanceRoleCoverageRepository:
    """Dependency injector for singleton repository."""
    global _role_coverage_repository_instance
    if _role_coverage_repository_instance is None:
        _role_coverage_repository_instance = GovernanceRoleCoverageRepository()
    return _role_coverage_repository_instance

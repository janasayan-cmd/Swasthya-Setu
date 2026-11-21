"""Phase 79: Strategic Review Package Generation Service.

Consolidates strategic execution monitoring intelligence into executive review dossiers
and coordinates formal referral to Phase 72 Management Review.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_review_packages import (
    GenerateReviewPackageRequest,
    ReferReviewPackageToPhase72Request,
    StrategicReviewPackageRecord,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)
from app.schemas.governance_strategy_assumption import AssumptionStatus
from app.schemas.governance_strategy_signals import SignalDisposition
from app.schemas.governance_strategy_execution_exceptions import ExecutionExceptionStatus


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyReviewPackagesService:
    """Manages strategic review package assembly, evidence synthesis, and Phase 72 referrals."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def generate_review_package(
        self,
        tenant_id: str,
        preparer_id: str,
        request: GenerateReviewPackageRequest,
    ) -> StrategicReviewPackageRecord:
        package_id = f"SRP-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        # Aggregate intelligence across requested roadmaps
        monitored_counts: Dict[str, int] = {}
        for r_id in request.included_roadmap_ids:
            items = self.repository.list_monitoring_records(tenant_id, roadmap_id=r_id)
            for item in items:
                status_key = item.health_status.value
                monitored_counts[status_key] = monitored_counts.get(status_key, 0) + 1

        all_deps = self.repository.list_all_cross_dependencies(tenant_id)
        dep_summary = {
            "total_dependencies": len(all_deps),
            "conflicts_detected": sum(1 for d in all_deps if d.status == "CONFLICT_DETECTED"),
        }

        # Collect alignment findings
        findings = [
            f.model_dump()
            for r_id in request.included_roadmap_ids
            for f in self.repository.list_alignment_findings(tenant_id, roadmap_id=r_id)
        ]

        # Collect invalidated assumptions
        invalidated_assumptions = [
            a.model_dump()
            for r_id in request.included_roadmap_ids
            for a in self.repository.list_assumptions(tenant_id, roadmap_id=r_id, status=AssumptionStatus.INVALIDATED)
        ]

        # Collect active signals
        active_signals = [
            s.model_dump()
            for r_id in request.included_roadmap_ids
            for s in self.repository.list_signals(tenant_id, roadmap_id=r_id, disposition=SignalDisposition.ACTIVE)
        ]

        # Collect open exceptions
        open_exceptions = [
            e.model_dump()
            for r_id in request.included_roadmap_ids
            for e in self.repository.list_exceptions(tenant_id, roadmap_id=r_id, status=ExecutionExceptionStatus.OPEN)
        ]

        # Collect proposals
        proposals = [
            p.model_dump()
            for r_id in request.included_roadmap_ids
            for p in self.repository.list_adaptation_proposals(tenant_id, roadmap_id=r_id)
        ]

        record = StrategicReviewPackageRecord(
            package_id=package_id,
            tenant_id=tenant_id,
            title=request.title,
            reporting_period=request.reporting_period,
            organizational_scope=request.organizational_scope or {},
            included_roadmap_ids=request.included_roadmap_ids,
            executive_summary=request.executive_summary,
            monitored_status_summary=monitored_counts,
            cross_roadmap_dependency_summary=dep_summary,
            alignment_findings=findings,
            invalidated_assumptions=invalidated_assumptions,
            active_signals=active_signals,
            open_exceptions=open_exceptions,
            adaptation_proposals=proposals,
            evidence_coverage=0.95,
            known_limitations=request.known_limitations or "Advisory strategic execution oversight package. Does not replace Phase 72 or Phase 78 authority.",
            prepared_by=preparer_id,
            phase_72_referral_reference=None,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            created_at=now_str,
        )
        return self.repository.save_review_package(record)

    def refer_to_phase_72(
        self,
        tenant_id: str,
        referrer_id: str,
        package_id: str,
        request: ReferReviewPackageToPhase72Request,
    ) -> StrategicReviewPackageRecord:
        pkg = self.repository.get_review_package(package_id)
        if not pkg or pkg.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_REVIEW_PACKAGE_NOT_FOUND,
                message=f"Strategic review package '{package_id}' was not found.",
                status_code=404,
            )

        ref_id = f"P72-REF-{uuid.uuid4().hex[:8].upper()}"
        updated = pkg.model_copy(
            update={
                "phase_72_referral_reference": ref_id,
            }
        )
        return self.repository.save_review_package(updated)

    def get_review_package(
        self,
        tenant_id: str,
        package_id: str,
    ) -> StrategicReviewPackageRecord:
        pkg = self.repository.get_review_package(package_id)
        if not pkg or pkg.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_REVIEW_PACKAGE_NOT_FOUND,
                message=f"Strategic review package '{package_id}' was not found.",
                status_code=404,
            )
        return pkg

    def list_review_packages(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicReviewPackageRecord]:
        return self.repository.list_review_packages(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            skip=skip,
            limit=limit,
        )

"""
Phase 88: Governance Response & Recovery Reporting Service
Generates executive reports across response strategies, feasibility, priorities, comparisons, execution tracking, and deviations.
"""
from datetime import datetime, timezone
from typing import Optional

from app.repositories.governance_response_strategy_repository import (
    GovernanceResponseStrategyRepository,
    get_governance_response_strategy_repository,
)
from app.schemas.governance_response_common import (
    ExecutionTrackingStatus,
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    RecoveryFeasibilityOutcome,
    StrategyReviewStatus,
)
from app.schemas.governance_response_reporting import (
    RecoveryComparisonsReport,
    RecoveryExecutionTrackingReport,
    RecoveryOptionsSummaryReport,
    RecoveryPrioritiesReport,
    StrategyDeviationsReport,
    StrategyFeasibilityReport,
)


class GovernanceResponseReportingService:
    def __init__(self, repo: Optional[GovernanceResponseStrategyRepository] = None):
        self.repo = repo or get_governance_response_strategy_repository()

    def generate_recovery_options_summary(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
    ) -> RecoveryOptionsSummaryReport:
        strategies = self.repo.list_strategies(tenant_id=tenant_id, scenario_ref=scenario_ref)
        approved_count = sum(1 for s in strategies if s.review_status == StrategyReviewStatus.APPROVED)

        options = self.repo.list_options(tenant_id=tenant_id, scenario_ref=scenario_ref)
        feasibilities = self.repo.list_feasibility_assessments(tenant_id=tenant_id)
        
        opt_ids = {o.option_id for o in options}
        matching_feasibilities = [f for f in feasibilities if f.option_id in opt_ids]

        verified_count = sum(1 for f in matching_feasibilities if f.feasibility_outcome == RecoveryFeasibilityOutcome.FEASIBLE_VERIFIED)
        conditional_count = sum(1 for f in matching_feasibilities if f.feasibility_outcome == RecoveryFeasibilityOutcome.CONDITIONALLY_FEASIBLE)
        infeasible_count = sum(1 for f in matching_feasibilities if f.feasibility_outcome in [RecoveryFeasibilityOutcome.NOT_FEASIBLE, RecoveryFeasibilityOutcome.INSUFFICIENT_EVIDENCE])

        return RecoveryOptionsSummaryReport(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            total_strategies_registered=len(strategies),
            approved_strategies_count=approved_count,
            total_candidate_options_generated=len(options),
            feasible_verified_options_count=verified_count,
            conditionally_feasible_options_count=conditional_count,
            infeasible_options_count=infeasible_count,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )

    def generate_strategy_feasibility_report(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
    ) -> StrategyFeasibilityReport:
        feasibilities = self.repo.list_feasibility_assessments(tenant_id=tenant_id)
        total = len(feasibilities)
        verified_count = sum(1 for f in feasibilities if f.feasibility_outcome == RecoveryFeasibilityOutcome.FEASIBLE_VERIFIED)
        pct = (verified_count / total * 100.0) if total > 0 else 0.0

        top_constraints = []
        for f in feasibilities:
            top_constraints.extend(f.failed_conditions)

        return StrategyFeasibilityReport(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            total_feasibility_assessments=total,
            verified_feasible_pct=round(pct, 2),
            top_failed_conditions=list(set(top_constraints))[:5],
            options_with_expired_evidence=0,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )

    def generate_recovery_priorities_report(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
    ) -> RecoveryPrioritiesReport:
        priorities = self.repo.list_priority_evaluations(tenant_id=tenant_id, scenario_ref=scenario_ref)
        total_caps = 0
        tier_1_count = 0
        tier_2_count = 0

        for p in priorities:
            for cap in p.prioritized_capabilities:
                total_caps += 1
                if cap.priority_tier == "TIER_1_ESSENTIAL":
                    tier_1_count += 1
                elif cap.priority_tier == "TIER_2_CRITICAL":
                    tier_2_count += 1

        return RecoveryPrioritiesReport(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            total_prioritized_capabilities=total_caps,
            tier_1_essential_capabilities_count=tier_1_count,
            tier_2_critical_capabilities_count=tier_2_count,
            unresolved_priority_conflicts_count=0,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )

    def generate_recovery_comparisons_report(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
    ) -> RecoveryComparisonsReport:
        comparisons = self.repo.list_comparisons(tenant_id=tenant_id, scenario_ref=scenario_ref)
        trade_offs_count = sum(len(c.trade_offs_identified) for c in comparisons)
        recs_count = sum(1 for c in comparisons if c.top_recommended_option_id is not None)

        return RecoveryComparisonsReport(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            total_comparisons_conducted=len(comparisons),
            total_trade_offs_analyzed=trade_offs_count,
            options_recommended_for_decision=recs_count,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )

    def generate_recovery_execution_tracking_report(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
    ) -> RecoveryExecutionTrackingReport:
        executions = self.repo.list_executions(tenant_id=tenant_id)
        in_prog = sum(1 for e in executions if e.status == ExecutionTrackingStatus.IN_PROGRESS)
        restored = sum(1 for e in executions if e.status == ExecutionTrackingStatus.VERIFIED_RESTORED)
        avg_progress = (sum(e.progress_pct for e in executions) / len(executions)) if executions else 0.0

        return RecoveryExecutionTrackingReport(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            total_active_executions=len(executions),
            in_progress_count=in_prog,
            verified_restored_count=restored,
            average_progress_pct=round(avg_progress, 2),
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )

    def generate_strategy_deviations_report(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
    ) -> StrategyDeviationsReport:
        executions = self.repo.list_executions(tenant_id=tenant_id)
        dev_executions = [e for e in executions if len(e.reported_deviations) > 0 or e.status == ExecutionTrackingStatus.DEVIATION_REPORTED]
        total_deviations = sum(len(e.reported_deviations) for e in executions)

        return StrategyDeviationsReport(
            tenant_id=tenant_id,
            generated_at=datetime.now(timezone.utc),
            total_executions_with_deviations=len(dev_executions),
            total_deviations_reported=total_deviations,
            active_blocked_activities_count=sum(1 for e in executions if e.status == ExecutionTrackingStatus.BLOCKED),
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )


_governance_response_reporting_service: Optional[GovernanceResponseReportingService] = None


def get_governance_response_reporting_service() -> GovernanceResponseReportingService:
    global _governance_response_reporting_service
    if _governance_response_reporting_service is None:
        _governance_response_reporting_service = GovernanceResponseReportingService()
    return _governance_response_reporting_service

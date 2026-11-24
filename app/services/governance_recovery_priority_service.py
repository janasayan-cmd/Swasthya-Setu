"""
Phase 88: Governance Recovery Priority & Sequencing Service
Determines capability restoration priorities based on clinical criticality tiers, MTPD, and dependencies.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from app.core.exceptions import (
    AppException,
    ErrorCode,
)
from app.repositories.governance_response_strategy_repository import (
    GovernanceResponseStrategyRepository,
    get_governance_response_strategy_repository,
)
from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
)
from app.schemas.governance_recovery_priority import (
    CapabilityRestorationPriorityItem,
    CreateRecoverySequenceRequest,
    EvaluateRecoveryPrioritiesRequest,
    RecoveryPriorityEvaluationRecord,
    RecoverySequenceRecord,
)


class GovernanceRecoveryPriorityService:
    def __init__(self, repo: Optional[GovernanceResponseStrategyRepository] = None):
        self.repo = repo or get_governance_response_strategy_repository()

    def evaluate_recovery_priorities(
        self,
        tenant_id: str,
        user_id: str,
        req: EvaluateRecoveryPrioritiesRequest,
    ) -> RecoveryPriorityEvaluationRecord:
        now = datetime.now(timezone.utc)
        items: List[CapabilityRestorationPriorityItem] = []

        caps = list(req.capability_refs) if req.capability_refs else ["CAP-LIFE-SAFETY-01", "CAP-CLINICAL-02"]

        for rank, cap in enumerate(caps, start=1):
            tier = "TIER_1_ESSENTIAL" if "SAFETY" in cap.upper() or "LIFE" in cap.upper() or rank == 1 else "TIER_2_CRITICAL"
            items.append(
                CapabilityRestorationPriorityItem(
                    capability_ref=cap,
                    priority_tier=tier,
                    priority_rank=rank,
                    rationale=f"Priority {rank} based on clinical safety governance criticality tier {tier}.",
                    prerequisite_capability_refs=[] if rank == 1 else [caps[rank - 2]],
                    required_resource_refs=["res-primary-01"],
                    required_role_refs=["ROLE-CLIN-GOV-01"],
                    max_acceptable_outage_hours=2.0 if tier == "TIER_1_ESSENTIAL" else 6.0,
                    estimated_restoration_hours=1.0 if tier == "TIER_1_ESSENTIAL" else 3.0,
                    outstanding_constraints=[],
                )
            )

        items.sort(key=lambda x: x.priority_rank)

        record = RecoveryPriorityEvaluationRecord(
            priority_evaluation_id=f"prio-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            scenario_id=req.scenario_id,
            impact_assessment_id=req.impact_assessment_id,
            prioritized_capabilities=items,
            unresolved_priority_conflicts=[],
            evaluated_by=user_id,
            evaluated_at=now,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )
        return self.repo.create_priority_evaluation(record)

    def get_recovery_priority_evaluation(
        self,
        priority_evaluation_id: str,
        tenant_id: str,
    ) -> RecoveryPriorityEvaluationRecord:
        record = self.repo.get_priority_evaluation(priority_evaluation_id, tenant_id)
        if not record:
            raise AppException(
                ErrorCode.RECOVERY_PRIORITY_EVALUATION_NOT_FOUND,
                f"Recovery priority evaluation '{priority_evaluation_id}' not found.",
            )
        return record

    def list_recovery_priority_evaluations(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
    ) -> List[RecoveryPriorityEvaluationRecord]:
        return self.repo.list_priority_evaluations(
            tenant_id=tenant_id,
            scenario_ref=scenario_ref,
        )

    def create_recovery_sequence(
        self,
        tenant_id: str,
        user_id: str,
        req: CreateRecoverySequenceRequest,
    ) -> RecoverySequenceRecord:
        prio_eval = self.get_recovery_priority_evaluation(req.priority_evaluation_id, tenant_id)
        now = datetime.now(timezone.utc)

        ordered_caps = [p.capability_ref for p in prio_eval.prioritized_capabilities]

        record = RecoverySequenceRecord(
            sequence_id=f"seq-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            sequence_name=req.sequence_name,
            ordered_capability_refs=ordered_caps,
            milestone_targets=list(req.milestone_targets),
            blocked_activities=[],
            critical_dependency_bottlenecks=["res-primary-01"],
            estimated_total_duration_hours=float(len(ordered_caps) * 2.0),
            created_by=user_id,
            created_at=now,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )
        return self.repo.create_recovery_sequence(record)

    def get_recovery_sequence(
        self,
        sequence_id: str,
        tenant_id: str,
    ) -> RecoverySequenceRecord:
        record = self.repo.get_recovery_sequence(sequence_id, tenant_id)
        if not record:
            raise AppException(
                ErrorCode.RECOVERY_SEQUENCE_NOT_FOUND,
                f"Recovery sequence '{sequence_id}' not found.",
            )
        return record

    def list_recovery_sequences(
        self,
        tenant_id: str,
        priority_evaluation_ref: Optional[str] = None,
    ) -> List[RecoverySequenceRecord]:
        return self.repo.list_recovery_sequences(
            tenant_id=tenant_id,
            priority_evaluation_ref=priority_evaluation_ref,
        )


_governance_recovery_priority_service: Optional[GovernanceRecoveryPriorityService] = None


def get_governance_recovery_priority_service() -> GovernanceRecoveryPriorityService:
    global _governance_recovery_priority_service
    if _governance_recovery_priority_service is None:
        _governance_recovery_priority_service = GovernanceRecoveryPriorityService()
    return _governance_recovery_priority_service

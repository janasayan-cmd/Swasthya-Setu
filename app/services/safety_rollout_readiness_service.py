"""Phase 57: Safety Rollout Readiness Service.

Validates pre-rollout readiness gates, approval freshness, version integrity,
scope boundaries, dependency health, and rollback/validation plan sufficiency.
"""

from datetime import datetime, timezone
from typing import List, Tuple

from app.schemas.safety_rollout import (
    ApprovalStatus,
    DependencyStatus,
    RolloutLifecycleState,
    RolloutReadinessResponse,
    SafetyRolloutRecord,
)


class SafetyRolloutReadinessService:
    """Evaluates readiness criteria prior to initiating or advancing safety rollouts."""

    @staticmethod
    def evaluate_readiness(rollout: SafetyRolloutRecord) -> Tuple[bool, RolloutReadinessResponse, List[str]]:
        """Run all pre-rollout readiness verification checks."""
        now = datetime.now(timezone.utc)
        blockers: List[str] = []

        # 1. Approval validation
        approval_valid = True
        if rollout.approval.approval_status != ApprovalStatus.APPROVED:
            approval_valid = False
            blockers.append(f"Approval status is {rollout.approval.approval_status.value}, expected APPROVED")

        if not rollout.approval.is_valid:
            approval_valid = False
            blockers.append("Approval record is marked as invalid or revoked")

        if rollout.approval.expires_at and rollout.approval.expires_at <= now:
            approval_valid = False
            blockers.append(f"Approval expired at {rollout.approval.expires_at.isoformat()}")

        # 2. Version alignment
        version_matched = True
        if rollout.approved_version != rollout.target_version:
            version_matched = False
            blockers.append(
                f"Version mismatch: approved version is '{rollout.approved_version}', "
                f"but target deployment is '{rollout.target_version}'"
            )

        if rollout.approval.change_version != rollout.approved_version:
            version_matched = False
            blockers.append(
                f"Approval version mismatch: signed off '{rollout.approval.change_version}', "
                f"rollout configured for '{rollout.approved_version}'"
            )

        # 3. Scope validation
        if not rollout.scope.organization_id or not rollout.scope.environment:
            blockers.append("Scope must specify valid organization_id and environment")

        # 4. Dependency validation (UNKNOWN != PASS, UNAVAILABLE != PASS)
        dependencies_satisfied = True
        for dep in rollout.dependencies:
            if dep.status != DependencyStatus.AVAILABLE:
                dependencies_satisfied = False
                blockers.append(
                    f"Dependency '{dep.name}' ({dep.dependency_type}) is {dep.status.value}, "
                    f"required: AVAILABLE"
                )

        # 5. Plan sufficiency
        plans_defined = True
        if not rollout.rollback_plan or len(rollout.rollback_plan.strip()) < 10:
            plans_defined = False
            blockers.append("Rollback strategy plan is missing or insufficient (min 10 chars)")

        if not rollout.validation_plan or len(rollout.validation_plan.strip()) < 10:
            plans_defined = False
            blockers.append("Validation strategy plan is missing or insufficient (min 10 chars)")

        if not rollout.observation_plan or len(rollout.observation_plan.strip()) < 10:
            plans_defined = False
            blockers.append("Post-deployment observation plan is missing or insufficient (min 10 chars)")

        is_ready = approval_valid and version_matched and dependencies_satisfied and plans_defined and len(blockers) == 0

        response = RolloutReadinessResponse(
            rollout_id=rollout.rollout_id,
            is_ready=is_ready,
            approval_valid=approval_valid,
            version_matched=version_matched,
            dependencies_satisfied=dependencies_satisfied,
            plans_defined=plans_defined,
            blockers=blockers,
        )

        return is_ready, response, blockers

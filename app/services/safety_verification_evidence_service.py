"""Phase 58: Safety Verification Evidence Service.

Collects, consolidates, and verifies evidence across authoritative backend phases:
- Phase 51: Change Governance & Approval
- Phase 57: Controlled Rollout & Stage Checkpoints
- Phase 48: Runtime Safety Control Execution
- Phase 52: Clinical Safety Assurance Results
- Phase 55: Post-Action Outcome Effectiveness
- Phase 49: Active Clinical Safety Incidents
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.repositories.safety_rollout_repository import (
    SafetyRolloutRepository,
    get_safety_rollout_repository,
)
from app.schemas.safety_rollout import (
    ApprovalStatus,
    CheckpointStatus,
    RolloutLifecycleState,
    SafetyRolloutRecord,
)
from app.schemas.safety_verification import (
    AssuranceOutcomeStatus,
    EffectivenessOutcomeStatus,
    EvidenceCategory,
    EvidenceProvenanceType,
    EvidenceReference,
    SafetyVerificationRecord,
)


class SafetyVerificationEvidenceService:
    """Consolidates and validates evidence integrity, completeness, and consistency."""

    def __init__(self, rollout_repository: Optional[SafetyRolloutRepository] = None) -> None:
        self.rollout_repository = rollout_repository or get_safety_rollout_repository()

    def collect_evidence_from_sources(
        self, verification: SafetyVerificationRecord
    ) -> Tuple[List[EvidenceReference], AssuranceOutcomeStatus, EffectivenessOutcomeStatus, str]:
        """Harvest authoritative evidence references from linked phases."""
        now = datetime.now(timezone.utc)
        evidence_list: List[EvidenceReference] = []

        rollout = self.rollout_repository.get(verification.rollout_id)
        assurance_status = AssuranceOutcomeStatus.ASSURANCE_PENDING
        effectiveness_status = EffectivenessOutcomeStatus.EFFECTIVENESS_PENDING
        safety_control_status = "PENDING"

        if rollout:
            # 1. Approval Evidence (Phase 51)
            evidence_list.append(
                EvidenceReference(
                    source_phase="Phase 51",
                    source_record_id=rollout.change_id,
                    category=EvidenceCategory.APPROVAL_EVIDENCE,
                    provenance_type=EvidenceProvenanceType.SOURCE_EVIDENCE,
                    source_timestamp=rollout.approval.approved_at,
                    created_at=now,
                    version=rollout.approval.change_version,
                    scope=rollout.scope.model_dump(),
                    status="VALID" if rollout.approval.is_valid and rollout.approval.approval_status == ApprovalStatus.APPROVED else "CONFLICTED",
                    metadata_summary={
                        "approver_id": rollout.approval.approver_id,
                        "approver_role": rollout.approval.approver_role,
                        "approval_status": rollout.approval.approval_status.value,
                    },
                    is_verified=rollout.approval.is_valid,
                )
            )

            # 2. Version Evidence
            ver_match = rollout.approved_version == rollout.target_version
            evidence_list.append(
                EvidenceReference(
                    source_phase="Phase 57",
                    source_record_id=rollout.rollout_id,
                    category=EvidenceCategory.VERSION_EVIDENCE,
                    provenance_type=EvidenceProvenanceType.SOURCE_EVIDENCE,
                    source_timestamp=rollout.updated_at,
                    created_at=now,
                    version=rollout.target_version,
                    scope=rollout.scope.model_dump(),
                    status="VALID" if ver_match else "CONFLICTED",
                    metadata_summary={
                        "approved_version": rollout.approved_version,
                        "target_version": rollout.target_version,
                        "match": ver_match,
                    },
                    is_verified=ver_match,
                )
            )

            # 3. Rollout Stage & Deployment Evidence (Phase 57)
            rollout_ok = rollout.lifecycle_state in {
                RolloutLifecycleState.COMPLETED,
                RolloutLifecycleState.POST_DEPLOYMENT_VALIDATION,
                RolloutLifecycleState.FULL_ROLLOUT,
            }
            evidence_list.append(
                EvidenceReference(
                    source_phase="Phase 57",
                    source_record_id=rollout.rollout_id,
                    category=EvidenceCategory.ROLLOUT_STAGE_EVIDENCE,
                    provenance_type=EvidenceProvenanceType.SOURCE_EVIDENCE,
                    source_timestamp=rollout.updated_at,
                    created_at=now,
                    version=rollout.target_version,
                    scope=rollout.scope.model_dump(),
                    status="VALID" if rollout_ok else "INCOMPLETE",
                    metadata_summary={
                        "current_stage": rollout.current_stage.value,
                        "lifecycle_state": rollout.lifecycle_state.value,
                        "checkpoints_count": len(rollout.checkpoints),
                    },
                    is_verified=rollout_ok,
                )
            )

            # 4. Checkpoints Evidence
            all_checkpoints_passed = (
                len(rollout.checkpoints) > 0
                and all(cp.status == CheckpointStatus.PASSED for cp in rollout.checkpoints)
            )
            evidence_list.append(
                EvidenceReference(
                    source_phase="Phase 57",
                    source_record_id=rollout.rollout_id,
                    category=EvidenceCategory.CHECKPOINT_EVIDENCE,
                    provenance_type=EvidenceProvenanceType.DERIVED_EVIDENCE,
                    source_timestamp=rollout.updated_at,
                    created_at=now,
                    version=rollout.target_version,
                    scope=rollout.scope.model_dump(),
                    status="VALID" if all_checkpoints_passed else "INCOMPLETE",
                    metadata_summary={
                        "total_checkpoints": len(rollout.checkpoints),
                        "all_passed": all_checkpoints_passed,
                    },
                    is_verified=all_checkpoints_passed,
                )
            )

            # 5. Safety Control Evidence (Phase 48)
            controls_verified = (
                len(rollout.safety_controls_verified) > 0
                and all(c.execution_verified and c.is_active for c in rollout.safety_controls_verified)
            )
            safety_control_status = "PASSED" if controls_verified else "FAILED"
            evidence_list.append(
                EvidenceReference(
                    source_phase="Phase 48",
                    source_record_id=rollout.rollout_id,
                    category=EvidenceCategory.SAFETY_CONTROL_EVIDENCE,
                    provenance_type=EvidenceProvenanceType.SOURCE_EVIDENCE,
                    source_timestamp=rollout.updated_at,
                    created_at=now,
                    version=rollout.target_version,
                    scope=rollout.scope.model_dump(),
                    status="VALID" if controls_verified else "CONFLICTED",
                    metadata_summary={
                        "verified_controls_count": len(rollout.safety_controls_verified),
                        "controls_status": safety_control_status,
                    },
                    is_verified=controls_verified,
                )
            )

            # 6. Check downstream routings for Phase 52 & Phase 55
            has_p52_routing = any(r.destination_phase == "Phase 52" for r in rollout.routings)
            has_p55_routing = any(r.destination_phase == "Phase 55" for r in rollout.routings)

            if has_p52_routing:
                assurance_status = AssuranceOutcomeStatus.ASSURANCE_PASS
                evidence_list.append(
                    EvidenceReference(
                        source_phase="Phase 52",
                        source_record_id=rollout.rollout_id,
                        category=EvidenceCategory.ASSURANCE_EVIDENCE,
                        provenance_type=EvidenceProvenanceType.SOURCE_EVIDENCE,
                        source_timestamp=rollout.updated_at,
                        created_at=now,
                        version=rollout.target_version,
                        scope=rollout.scope.model_dump(),
                        status="VALID",
                        metadata_summary={"assurance_outcome": assurance_status.value},
                        is_verified=True,
                    )
                )

            if has_p55_routing:
                effectiveness_status = EffectivenessOutcomeStatus.EFFECTIVENESS_SUFFICIENT
                evidence_list.append(
                    EvidenceReference(
                        source_phase="Phase 55",
                        source_record_id=rollout.rollout_id,
                        category=EvidenceCategory.EFFECTIVENESS_EVIDENCE,
                        provenance_type=EvidenceProvenanceType.SOURCE_EVIDENCE,
                        source_timestamp=rollout.updated_at,
                        created_at=now,
                        version=rollout.target_version,
                        scope=rollout.scope.model_dump(),
                        status="VALID",
                        metadata_summary={"effectiveness_outcome": effectiveness_status.value},
                        is_verified=True,
                    )
                )

        return evidence_list, assurance_status, effectiveness_status, safety_control_status

    def validate_completeness(self, evidence_items: List[EvidenceReference]) -> Tuple[bool, List[str]]:
        """Verify all mandatory evidence categories are represented."""
        mandatory_categories = {
            EvidenceCategory.APPROVAL_EVIDENCE,
            EvidenceCategory.VERSION_EVIDENCE,
            EvidenceCategory.ROLLOUT_STAGE_EVIDENCE,
            EvidenceCategory.SAFETY_CONTROL_EVIDENCE,
            EvidenceCategory.CHECKPOINT_EVIDENCE,
        }

        present_categories = {item.category for item in evidence_items if item.status == "VALID"}
        missing = [cat.value for cat in mandatory_categories if cat not in present_categories]

        return len(missing) == 0, missing

    def validate_consistency(
        self, verification: SafetyVerificationRecord, evidence_items: List[EvidenceReference]
    ) -> Tuple[bool, List[str]]:
        """Check cross-source consistency between approved change and deployed rollout."""
        conflicts: List[str] = []

        # Version consistency
        if verification.approved_version != verification.deployed_version:
            conflicts.append(
                f"Version mismatch: approved version '{verification.approved_version}' "
                f"differs from deployed version '{verification.deployed_version}'"
            )

        # Evidence status conflicts
        for item in evidence_items:
            if item.status == "CONFLICTED":
                conflicts.append(
                    f"Evidence from {item.source_phase} ({item.category.value}) is marked CONFLICTED"
                )

        return len(conflicts) == 0, conflicts

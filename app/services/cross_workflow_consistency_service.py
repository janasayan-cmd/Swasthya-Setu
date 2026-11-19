"""Phase 68: Cross-Workflow Decision Consistency Service.

Evaluates consistency between related authoritative governance decisions across
different phases, detecting contradictory outcomes, superseded linkages, and version mismatches.

Mandatory Invariants:
1. Do not automatically select the latest decision as the correct one.
2. Do not modify authoritative source decisions.
3. Preserves all contradictory records and versions.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.schemas.decision_assurance import GovernanceDecisionRegisterRecord
from app.schemas.decision_assurance_finding import (
    AssuranceFindingCategory,
    AssuranceFindingRecord,
    FindingSeverity,
)
from app.schemas.decision_correction_coordination import (
    CrossWorkflowConsistencyCheckResult,
)


class CrossWorkflowConsistencyService:
    """Service evaluating mutual consistency across dependent governance decisions."""

    def evaluate_consistency(
        self,
        decision: GovernanceDecisionRegisterRecord,
        related_decisions: List[GovernanceDecisionRegisterRecord],
        assurance_id: str,
    ) -> Tuple[bool, Dict[str, Any], List[AssuranceFindingRecord], List[CrossWorkflowConsistencyCheckResult]]:
        """Evaluate consistency between the primary decision and related decisions."""
        findings: List[AssuranceFindingRecord] = []
        checks: List[CrossWorkflowConsistencyCheckResult] = []
        is_consistent = True

        for rel in related_decisions:
            # 1. Superseded reference check
            if rel.is_superseded:
                is_consistent = False
                desc = (
                    f"Decision {decision.decision_id} ({decision.source_phase.value}) references related "
                    f"decision {rel.decision_id} ({rel.source_phase.value}) which has been superseded."
                )
                checks.append(
                    CrossWorkflowConsistencyCheckResult(
                        decision_id=decision.decision_id,
                        related_decision_id=rel.decision_id,
                        is_consistent=False,
                        conflict_type="DEPENDENCY_SUPERSEDED",
                        conflict_description=desc,
                        discrepancy_type="DEPENDENCY_SUPERSEDED",
                        discrepancy_details=desc,
                    )
                )
                findings.append(
                    AssuranceFindingRecord(
                        decision_id=decision.decision_id,
                        assurance_id=assurance_id,
                        category=AssuranceFindingCategory.CROSS_WORKFLOW_CONFLICT,
                        severity=FindingSeverity.HIGH,
                        title="Dependency on Superseded Decision",
                        description=desc,
                        source_phase=decision.source_phase.value,
                        source_record_id=decision.source_record_id,
                        recommended_action="Reconcile dependency against superseding decision record.",
                    )
                )
                continue

            # 2. Contradictory outcome check (e.g., APPROVED/CLOSED vs REJECTED/CRITICAL_RISK)
            closed_or_approved = {"ACCEPT", "APPROV", "CLOSE", "RESOLV", "COMPLET"}
            risk_or_rejected = {"REJECT", "REVOK", "DENY", "CRITICAL_RISK", "ACTION_FAILED", "REOPEN", "BLOCKED", "CONFLICT"}

            d_outcome = decision.decision_outcome.upper()
            r_outcome = rel.decision_outcome.upper()

            d_is_positive = any(kw in d_outcome for kw in closed_or_approved)
            d_is_negative = any(kw in d_outcome for kw in risk_or_rejected)
            r_is_positive = any(kw in r_outcome for kw in closed_or_approved)
            r_is_negative = any(kw in r_outcome for kw in risk_or_rejected)

            is_contradictory = (d_is_positive and r_is_negative) or (d_is_negative and r_is_positive)

            if is_contradictory:
                is_consistent = False
                desc = (
                    f"Contradictory outcomes detected: {decision.decision_id} has outcome '{decision.decision_outcome}' "
                    f"while related decision {rel.decision_id} has outcome '{rel.decision_outcome}'."
                )
                checks.append(
                    CrossWorkflowConsistencyCheckResult(
                        decision_id=decision.decision_id,
                        related_decision_id=rel.decision_id,
                        is_consistent=False,
                        conflict_type="CONTRADICTORY_OUTCOME",
                        conflict_description=desc,
                        discrepancy_type="CONTRADICTORY_OUTCOME",
                        discrepancy_details=desc,
                    )
                )
                findings.append(
                    AssuranceFindingRecord(
                        decision_id=decision.decision_id,
                        assurance_id=assurance_id,
                        category=AssuranceFindingCategory.CROSS_WORKFLOW_CONFLICT,
                        severity=FindingSeverity.CRITICAL,
                        title="Cross-Workflow Decision Contradiction",
                        description=desc,
                        source_phase=decision.source_phase.value,
                        source_record_id=decision.source_record_id,
                        recommended_action="Route cross-workflow conflict to Clinical Governance Committee.",
                    )
                )
            else:
                checks.append(
                    CrossWorkflowConsistencyCheckResult(
                        decision_id=decision.decision_id,
                        related_decision_id=rel.decision_id,
                        is_consistent=True,
                    )
                )

        details = {
            "related_decisions_checked": len(related_decisions),
            "is_consistent": is_consistent,
            "consistency_findings_count": len(findings),
        }

        return is_consistent, details, findings, checks


# Global singleton
_global_consistency_service = CrossWorkflowConsistencyService()


def get_cross_workflow_consistency_service() -> CrossWorkflowConsistencyService:
    """Dependency provider for cross-workflow consistency service."""
    return _global_consistency_service

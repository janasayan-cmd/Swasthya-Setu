"""Phase 68: Policy Applicability and Versioning Verification Service.

Verifies the governing policy basis for recorded decisions, ensuring that policy
references are effective, properly scoped, and not retroactively rewritten.

Mandatory Invariants:
1. A policy change must not silently rewrite the historical policy basis of an earlier decision.
2. A historical decision is not automatically invalid merely because a newer policy version exists.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from app.schemas.decision_assurance import GovernanceDecisionRegisterRecord
from app.schemas.decision_assurance_finding import (
    AssuranceFindingCategory,
    AssuranceFindingRecord,
    FindingSeverity,
)


class PolicyApplicabilityVerificationService:
    """Service evaluating policy version validity and applicability at decision timestamp."""

    def verify_policy_applicability(
        self,
        decision: GovernanceDecisionRegisterRecord,
        assurance_id: str,
        current_eval_policy_version: str = "v1.0.0",
    ) -> Tuple[bool, Dict[str, Any], List[AssuranceFindingRecord]]:
        """Verify policy version and applicability for a recorded decision."""
        findings: List[AssuranceFindingRecord] = []

        # 1. Check policy reference existence
        if not decision.policy_reference or decision.policy_reference.strip() == "":
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.POLICY_MISMATCH,
                    severity=FindingSeverity.HIGH,
                    title="Missing Governing Policy Reference",
                    description="The decision record does not cite the governing policy under which it was executed.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Identify and link authoritative governance policy framework.",
                )
            )

        # 2. Check effective date vs decision timestamp
        if decision.policy_effective_date and decision.decided_at < decision.policy_effective_date:
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.POLICY_MISMATCH,
                    severity=FindingSeverity.HIGH,
                    title="Decision Pre-Dates Policy Effective Date",
                    description=(
                        f"Decision decided at {decision.decided_at.isoformat()} before policy "
                        f"{decision.policy_reference} became effective on {decision.policy_effective_date.isoformat()}."
                    ),
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    policy_reference=decision.policy_reference,
                    policy_version=decision.policy_version,
                    recommended_action="Reconcile policy effective window with authoritative governance committee.",
                )
            )

        # 3. Policy version comparison (Informational/Reassessment note if newer policy exists)
        has_version_mismatch = (
            decision.policy_version != current_eval_policy_version
            and not decision.policy_version.startswith(current_eval_policy_version.split(".")[0])
        )
        if has_version_mismatch:
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.POLICY_MISMATCH,
                    severity=FindingSeverity.LOW,
                    title="Policy Version Divergence",
                    description=(
                        f"Decision was rendered under policy version {decision.policy_version}; "
                        f"current assurance environment operates under {current_eval_policy_version}."
                    ),
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    policy_reference=decision.policy_reference,
                    policy_version=decision.policy_version,
                    recommended_action="Review prospective policy migration guidelines; historical decision remains auditable.",
                )
            )

        is_compliant = not any(f.severity in {FindingSeverity.CRITICAL, FindingSeverity.HIGH} for f in findings)
        details = {
            "policy_reference": decision.policy_reference,
            "recorded_policy_version": decision.policy_version,
            "current_assurance_policy_version": current_eval_policy_version,
            "policy_effective_date": decision.policy_effective_date.isoformat() if decision.policy_effective_date else None,
            "is_compliant": is_compliant,
            "policy_findings_count": len(findings),
        }

        return is_compliant, details, findings


# Global singleton
_global_policy_service = PolicyApplicabilityVerificationService()


def get_policy_applicability_verification_service() -> PolicyApplicabilityVerificationService:
    """Dependency provider for policy applicability verification service."""
    return _global_policy_service

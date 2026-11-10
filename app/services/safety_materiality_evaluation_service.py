"""Phase 66: Safety Materiality Evaluation Service.

Evaluates integrity findings against governed policy to compute verification outcomes,
lifecycle state transitions, and reassessment/reopening recommendations.

Mandatory Safety Invariants:
1. Post-closure verification does not independently certify clinical safety.
2. Missing dependency response must never be interpreted as successful verification.
3. Unknown, contradictory, unavailable, or insufficient evidence must never be interpreted as proof of continued safety.
4. AI or heuristic recommendations do not constitute authorized governance decisions.
"""

from typing import Any, Dict, List, Tuple

from app.schemas.safety_integrity_finding import (
    FindingCategory,
    FindingSeverity,
    IntegrityFindingRecord,
)
from app.schemas.safety_post_closure_monitoring import MonitoringPolicyConfig
from app.schemas.safety_post_closure_verification import VerificationLifecycleState


class SafetyMaterialityEvaluationService:
    """Evaluates integrity findings and determines authoritative verification result."""

    @staticmethod
    def evaluate(
        findings: List[IntegrityFindingRecord],
        evaluated_checks: Dict[str, Any],
        limitations: List[str],
        policy: MonitoringPolicyConfig,
    ) -> Tuple[VerificationLifecycleState, bool, bool, str]:
        """Compute the post-closure verification state, flags, and rationale.

        Returns:
            Tuple of:
            - state: VerificationLifecycleState
            - reassessment_required: bool
            - reopen_recommended: bool
            - rationale: str
        """
        # 1. Check for dependency outages or repository errors
        has_dependency_error = any(
            f.category == FindingCategory.DEPENDENCY_STATE_UNKNOWN
            for f in findings
        )
        if has_dependency_error:
            rationale = "One or more authoritative upstream repositories were inaccessible; cannot verify safety."
            return (
                VerificationLifecycleState.DEPENDENCY_UNAVAILABLE,
                False,
                False,
                rationale,
            )

        # 2. Check for invalidated required evidence
        has_invalid_evidence = any(
            f.category in (
                FindingCategory.REQUIRED_EVIDENCE_INVALIDATED,
                FindingCategory.DESTINATION_OUTCOME_INVALIDATED,
            )
            for f in findings
        )
        if has_invalid_evidence:
            rationale = "Mandatory supporting evidence or destination outcomes were invalidated; completion integrity invalid."
            return (
                VerificationLifecycleState.EVIDENCE_INVALID,
                True,
                True,
                rationale,
            )

        # 3. Check for authoritative state conflicts
        has_conflicts = any(
            f.category in (
                FindingCategory.AUTHORITATIVE_STATE_CONFLICT,
                FindingCategory.COMPLETION_PACKAGE_INCONSISTENCY,
            )
            for f in findings
        )
        if has_conflicts:
            rationale = "Direct contradictions detected between completion record and authoritative downstream states."
            return (
                VerificationLifecycleState.CONFLICTED,
                True,
                True,
                rationale,
            )

        # 4. Check for critical findings that recommend governed reopening
        critical_categories_for_reopen = {
            FindingCategory.SOURCE_DISPOSITION_CHANGED,
            FindingCategory.DESTINATION_WORKFLOW_REOPENED,
            FindingCategory.MATERIAL_SAFETY_SIGNAL_DETECTED,
            FindingCategory.FOLLOW_UP_FAILED,
        }
        critical_reopen_findings = [
            f for f in findings
            if f.is_material and (f.severity == FindingSeverity.CRITICAL or f.category in critical_categories_for_reopen)
        ]
        if critical_reopen_findings:
            categories_str = ", ".join({f.category.value for f in critical_reopen_findings})
            rationale = f"Material critical findings detected ({categories_str}); recommended for governed reopening review."
            return (
                VerificationLifecycleState.REOPEN_RECOMMENDED,
                True,
                True,
                rationale,
            )

        # 5. Check for material findings requiring reassessment
        material_findings = [f for f in findings if f.is_material]
        if material_findings:
            categories_str = ", ".join({f.category.value for f in material_findings})
            rationale = f"Material changes detected ({categories_str}) under policy '{policy.policy_version}'; reassessment required."
            return (
                VerificationLifecycleState.REASSESSMENT_REQUIRED,
                True,
                False,
                rationale,
            )

        # 6. Check for non-material findings / limitations
        if len(findings) > 0 or len(limitations) > 0:
            rationale = "Verification completed with recorded limitations and non-material observations."
            return (
                VerificationLifecycleState.VERIFIED_WITH_LIMITATIONS,
                False,
                False,
                rationale,
            )

        # 7. Clean verification
        rationale = f"All post-closure checks verified against authoritative sources under policy '{policy.policy_version}'."
        return (
            VerificationLifecycleState.VERIFIED,
            False,
            False,
            rationale,
        )

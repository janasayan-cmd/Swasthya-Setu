"""Phase 68: Decision Provenance Verification Service.

Verifies that recorded governance decisions are traceable to authoritative workflows,
possess complete metadata, verifiable versions, and uncompromised provenance.

Mandatory Invariant:
A provenance failure is a governance integrity finding, not automatic proof of
misconduct or an incorrect clinical decision.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from app.schemas.decision_assurance import GovernanceDecisionRegisterRecord
from app.schemas.decision_assurance_finding import (
    AssuranceFindingCategory,
    AssuranceFindingRecord,
    FindingSeverity,
)


class DecisionProvenanceVerificationService:
    """Service evaluating decision provenance completeness and source traceability."""

    def verify_provenance(
        self,
        decision: GovernanceDecisionRegisterRecord,
        assurance_id: str,
    ) -> Tuple[bool, Dict[str, Any], List[AssuranceFindingRecord]]:
        """Verify decision provenance and return boolean validity, details, and generated findings."""
        findings: List[AssuranceFindingRecord] = []
        now = datetime.now(timezone.utc)

        # 1. Source reference completeness
        if not decision.source_record_id or decision.source_record_id.strip() == "":
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.PROVENANCE_FAILURE,
                    severity=FindingSeverity.CRITICAL,
                    title="Missing Source Record Identifier",
                    description="The registered decision lacks an attributable source record identifier.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id or "UNKNOWN",
                    recommended_action="Route to originating workflow owner to restore source linkage.",
                )
            )

        # 2. Source version check
        if not decision.source_version or decision.source_version.strip() == "":
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.PROVENANCE_FAILURE,
                    severity=FindingSeverity.HIGH,
                    title="Missing Source Version Reference",
                    description="The registered decision does not specify the version of the originating record.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Reconcile originating record version with authoritative repository.",
                )
            )

        # 3. Decider identity attribution
        if not decision.decided_by_id or decision.decided_by_id.strip() == "":
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.PROVENANCE_FAILURE,
                    severity=FindingSeverity.CRITICAL,
                    title="Unattributable Decision Maker",
                    description="The governance decision record contains no traceable decision-maker identity.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Require authoritative owner to confirm acting decision maker.",
                )
            )

        # 4. Superseded source detection
        if decision.is_superseded:
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.SUPERSEDED_SOURCE,
                    severity=FindingSeverity.MEDIUM,
                    title="Decision Source Superseded",
                    description=f"The underlying decision has been superseded by {decision.superseded_by or 'a subsequent version'}.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Ensure dependent workflows reference the superseding decision version.",
                )
            )

        # 5. Timestamp validation
        is_future_dated = decision.decided_at > now
        if is_future_dated:
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.PROVENANCE_FAILURE,
                    severity=FindingSeverity.HIGH,
                    title="Future-Dated Decision Timestamp",
                    description="Decision timestamp occurs in the future, indicating system clock inconsistency.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Audit system clock synchronization and rectify provenance record.",
                )
            )

        is_valid = len(findings) == 0
        details = {
            "source_phase": decision.source_phase.value,
            "source_record_id": decision.source_record_id,
            "source_version": decision.source_version,
            "decided_by_id": decision.decided_by_id,
            "decided_at": decision.decided_at.isoformat(),
            "is_superseded": decision.is_superseded,
            "provenance_issues_count": len(findings),
        }

        return is_valid, details, findings


# Global singleton
_global_provenance_service = DecisionProvenanceVerificationService()


def get_decision_provenance_verification_service() -> DecisionProvenanceVerificationService:
    """Dependency provider for decision provenance verification service."""
    return _global_provenance_service

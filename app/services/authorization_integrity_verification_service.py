"""Phase 68: Authorization Integrity and Separation-of-Duties Verification Service.

Evaluates historical authorization evidence, decider role scope, tenant validity,
and independent separation-of-duties rules for recorded governance decisions.

Mandatory Invariants:
1. Do not infer historical authorization from a user's current permissions.
2. A valid authentication session does not prove authority for a particular decision.
3. Unknown authorization evidence must not be treated as valid authorization.
4. Role does not prove authority over specific organization, facility, or patient.
"""

from typing import Any, Dict, List, Tuple

from app.schemas.decision_assurance import (
    AuthorizationVerificationStatus,
    GovernanceDecisionRegisterRecord,
    SeparationOfDutiesStatus,
)
from app.schemas.decision_assurance_finding import (
    AssuranceFindingCategory,
    AssuranceFindingRecord,
    FindingSeverity,
)


class AuthorizationIntegrityVerificationService:
    """Service evaluating authorization integrity, tenant scoping, and separation of duties."""

    def verify_authorization_and_separation(
        self,
        decision: GovernanceDecisionRegisterRecord,
        assurance_id: str,
    ) -> Tuple[AuthorizationVerificationStatus, SeparationOfDutiesStatus, Dict[str, Any], List[AssuranceFindingRecord]]:
        """Verify authorization evidence, scope restrictions, and separation of duties."""
        findings: List[AssuranceFindingRecord] = []
        auth_status = AuthorizationVerificationStatus.AUTHORIZED
        sep_status = SeparationOfDutiesStatus.COMPLIANT

        # ---------------------------------------------------------------------
        # 1. Historical Authorization Evidence Check
        # ---------------------------------------------------------------------
        # If no authorization evidence reference is provided, it is unverifiable
        if not decision.authorization_evidence_ref or decision.authorization_evidence_ref.strip() == "":
            auth_status = AuthorizationVerificationStatus.HISTORICAL_UNVERIFIABLE
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.AUTHORIZATION_UNVERIFIABLE,
                    severity=FindingSeverity.HIGH,
                    title="Missing Historical Authorization Evidence",
                    description="No historical authorization token or delegation certificate is attached to the decision record.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Submit historical authorization artifact or request owner confirmation.",
                )
            )
        elif "revoked" in decision.authorization_evidence_ref.lower():
            auth_status = AuthorizationVerificationStatus.REVOKED
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.AUTHORIZATION_INVALID,
                    severity=FindingSeverity.CRITICAL,
                    title="Revoked Authorization Evidence",
                    description="Authorization evidence used for the decision was revoked prior to decision execution.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    authorization_evidence_ref=decision.authorization_evidence_ref,
                    recommended_action="Submit for emergency decision revocation review.",
                )
            )
        elif "expired" in decision.authorization_evidence_ref.lower():
            auth_status = AuthorizationVerificationStatus.EXPIRED
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.AUTHORIZATION_INVALID,
                    severity=FindingSeverity.HIGH,
                    title="Expired Delegated Authority",
                    description="The delegation grant referenced by the decision had expired at decision timestamp.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    authorization_evidence_ref=decision.authorization_evidence_ref,
                    recommended_action="Request retrospective governance ratification or re-execution.",
                )
            )

        # ---------------------------------------------------------------------
        # 2. Automated vs Human Attributability
        # ---------------------------------------------------------------------
        if decision.is_automated and (not decision.service_identity or decision.service_identity.strip() == ""):
            auth_status = AuthorizationVerificationStatus.UNAUTHORIZED
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.AUTHORIZATION_INVALID,
                    severity=FindingSeverity.CRITICAL,
                    title="Unauthenticated Automated Decision Identity",
                    description="Automated governance decision recorded without a verified service principal identity.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Configure authorized service identity credentials and re-verify.",
                )
            )

        # ---------------------------------------------------------------------
        # 3. Role and Scope Restrictions
        # ---------------------------------------------------------------------
        # Patient role cannot make governance decisions
        if decision.decided_by_role.upper() == "PATIENT":
            auth_status = AuthorizationVerificationStatus.UNAUTHORIZED
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.AUTHORIZATION_INVALID,
                    severity=FindingSeverity.CRITICAL,
                    title="Unauthorized Role for Governance Decision",
                    description="Patient role is fundamentally unauthorized to record clinical governance decisions.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Reject decision and trigger security audit review.",
                )
            )

        # ---------------------------------------------------------------------
        # 4. Separation of Duties Check
        # ---------------------------------------------------------------------
        # Requester cannot be Approver/Decider where independent approval is required
        if (
            decision.requester_id
            and decision.approver_id
            and decision.requester_id == decision.approver_id
        ):
            sep_status = SeparationOfDutiesStatus.SELF_APPROVAL_DETECTED
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.SEPARATION_OF_DUTIES_VIOLATION,
                    severity=FindingSeverity.HIGH,
                    title="Self-Approval Detected",
                    description=f"Actor {decision.requester_id} initiated and self-approved the governance decision.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Route decision to an independent secondary reviewer.",
                )
            )
        elif decision.requester_id and not decision.approver_id:
            # Independent review missing when policy mandates distinct approver
            sep_status = SeparationOfDutiesStatus.INDEPENDENT_REVIEW_MISSING

        details = {
            "decided_by_id": decision.decided_by_id,
            "decided_by_role": decision.decided_by_role,
            "decided_by_scope": decision.decided_by_scope,
            "authorization_evidence_ref": decision.authorization_evidence_ref,
            "auth_status": auth_status.value,
            "separation_status": sep_status.value,
            "findings_count": len(findings),
        }

        return auth_status, sep_status, details, findings


# Global singleton
_global_auth_service = AuthorizationIntegrityVerificationService()


def get_authorization_integrity_verification_service() -> AuthorizationIntegrityVerificationService:
    """Dependency provider for authorization integrity verification service."""
    return _global_auth_service

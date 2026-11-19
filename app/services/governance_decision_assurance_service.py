"""Phase 68: Master Governance Decision Assurance Service.

Coordinates decision provenance verification, authorization integrity evaluation,
separation of duties, policy compliance, evidence assurance, cross-workflow consistency,
and integrity finding management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_assurance_repository import (
    GovernanceDecisionAssuranceRepository,
    get_governance_decision_assurance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.decision_assurance import (
    AssuranceLifecycleState,
    AuthorizationVerificationStatus,
    DecisionAssuranceRecord,
    EvidenceAssuranceStatus,
    GovernanceDecisionRegisterRecord,
    RegisterDecisionRequest,
    SeparationOfDutiesStatus,
    TriggerDecisionAssuranceRequest,
)
from app.schemas.decision_assurance_finding import (
    AssuranceFindingCategory,
    AssuranceFindingRecord,
    FindingSeverity,
    ResolveAssuranceFindingRequest,
    ReviewAssuranceFindingRequest,
)
from app.schemas.decision_correction_coordination import (
    DecisionAssuranceReportResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.authorization_integrity_verification_service import (
    AuthorizationIntegrityVerificationService,
    get_authorization_integrity_verification_service,
)
from app.services.cross_workflow_consistency_service import (
    CrossWorkflowConsistencyService,
    get_cross_workflow_consistency_service,
)
from app.services.decision_correction_coordination_service import (
    DecisionCorrectionCoordinationService,
    get_decision_correction_coordination_service,
)
from app.services.decision_evidence_assurance_service import (
    DecisionEvidenceAssuranceService,
    get_decision_evidence_assurance_service,
)
from app.services.decision_provenance_verification_service import (
    DecisionProvenanceVerificationService,
    get_decision_provenance_verification_service,
)
from app.services.policy_applicability_verification_service import (
    PolicyApplicabilityVerificationService,
    get_policy_applicability_verification_service,
)


class GovernanceDecisionAssuranceService:
    """Master service executing and managing governance decision assurance."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionAssuranceRepository] = None,
        provenance_service: Optional[DecisionProvenanceVerificationService] = None,
        auth_service: Optional[AuthorizationIntegrityVerificationService] = None,
        policy_service: Optional[PolicyApplicabilityVerificationService] = None,
        evidence_service: Optional[DecisionEvidenceAssuranceService] = None,
        consistency_service: Optional[CrossWorkflowConsistencyService] = None,
        correction_service: Optional[DecisionCorrectionCoordinationService] = None,
    ) -> None:
        self.repository = repository or get_governance_decision_assurance_repository()
        self.provenance_service = provenance_service or get_decision_provenance_verification_service()
        self.auth_service = auth_service or get_authorization_integrity_verification_service()
        self.policy_service = policy_service or get_policy_applicability_verification_service()
        self.evidence_service = evidence_service or get_decision_evidence_assurance_service()
        self.consistency_service = consistency_service or get_cross_workflow_consistency_service()
        self.correction_service = correction_service or get_decision_correction_coordination_service()

    # -------------------------------------------------------------------------
    # Decision Registration
    # -------------------------------------------------------------------------

    def register_decision(
        self,
        user: AuthenticatedUserContext,
        payload: RegisterDecisionRequest,
    ) -> GovernanceDecisionRegisterRecord:
        """Register a reference to an authoritative governance decision."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role is not authorized to register governance decisions.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = GovernanceDecisionRegisterRecord(
            source_phase=payload.source_phase,
            source_record_id=payload.source_record_id,
            source_version=payload.source_version or "v1.0.0",
            decision_type=payload.decision_type,
            decision_title=payload.decision_title,
            decision_outcome=payload.decision_outcome,
            organization_id=user.organization_id,
            facility_id=user.facility_id or "fac-default",
            patient_id=payload.patient_id,
            decided_by_id=payload.decided_by_id,
            decided_by_role=payload.decided_by_role,
            decided_by_scope=payload.decided_by_scope or "facility",
            is_automated=payload.is_automated or False,
            service_identity=payload.service_identity,
            decided_at=payload.decided_at,
            requester_id=payload.requester_id,
            approver_id=payload.approver_id,
            authorization_evidence_ref=payload.authorization_evidence_ref,
            policy_reference=payload.policy_reference or "gov-policy-v1",
            policy_version=payload.policy_version or "v1.0.0",
            policy_effective_date=payload.policy_effective_date,
            supporting_evidence_refs=payload.supporting_evidence_refs or [],
            rationale=payload.rationale,
            related_decision_ids=payload.related_decision_ids or [],
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )

        return self.repository.save_decision_register(record)

    def get_decision(
        self, decision_id: str, user: AuthenticatedUserContext
    ) -> GovernanceDecisionRegisterRecord:
        """Retrieve a registered decision ensuring tenant scoping."""
        decision = self.repository.get_decision_register(decision_id)
        if not decision:
            raise AppException(
                code=ErrorCode.DECISION_REGISTER_NOT_FOUND,
                message=f"Registered decision {decision_id} not found.",
                status_code=404,
            )
        if decision.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access decision across tenant boundaries.",
                status_code=403,
            )
        return decision

    def list_decisions(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        source_phase: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceDecisionRegisterRecord]:
        """List registered decisions for tenant."""
        return self.repository.list_decisions(
            organization_id=user.organization_id,
            facility_id=facility_id,
            source_phase=source_phase,
            limit=limit,
            offset=offset,
        )

    # -------------------------------------------------------------------------
    # Assurance Verification Execution
    # -------------------------------------------------------------------------

    def verify_decision(
        self,
        user: AuthenticatedUserContext,
        decision_id: str,
        payload: TriggerDecisionAssuranceRequest,
    ) -> DecisionAssuranceRecord:
        """Execute a comprehensive decision assurance evaluation run."""
        decision = self.get_decision(decision_id, user)

        # Idempotency check
        if payload.idempotency_key:
            existing_id = self.repository.get_idempotent_id(payload.idempotency_key)
            if existing_id:
                existing_run = self.repository.get_assurance_run(existing_id)
                if existing_run:
                    return existing_run

        now = datetime.now(timezone.utc)
        assurance = DecisionAssuranceRecord(
            decision_id=decision_id,
            organization_id=decision.organization_id,
            facility_id=decision.facility_id,
            lifecycle_state=AssuranceLifecycleState.EVALUATING,
            evaluated_by=user.user_id,
            evaluated_at=now,
            policy_version=payload.policy_version or "v1.0.0",
            idempotency_key=payload.idempotency_key,
            correlation_id=payload.correlation_id,
            metadata=payload.metadata or {},
        )

        all_findings: List[AssuranceFindingRecord] = []

        # 1. Provenance Verification
        prov_ok, prov_details, prov_findings = self.provenance_service.verify_provenance(
            decision=decision, assurance_id=assurance.assurance_id
        )
        assurance.provenance_verified = prov_ok
        assurance.provenance_details = prov_details
        all_findings.extend(prov_findings)

        # 2. Authorization & Separation-of-Duties Verification
        auth_status, sep_status, auth_details, auth_findings = (
            self.auth_service.verify_authorization_and_separation(
                decision=decision, assurance_id=assurance.assurance_id
            )
        )
        assurance.authorization_status = auth_status
        assurance.separation_of_duties_status = sep_status
        assurance.authorization_details = auth_details
        all_findings.extend(auth_findings)

        # 3. Policy Applicability Verification
        pol_ok, pol_details, pol_findings = self.policy_service.verify_policy_applicability(
            decision=decision,
            assurance_id=assurance.assurance_id,
            current_eval_policy_version=assurance.policy_version,
        )
        assurance.policy_compliance_verified = pol_ok
        assurance.policy_details = pol_details
        all_findings.extend(pol_findings)

        # 4. Evidence Integrity Assurance
        ev_status, ev_details, ev_findings = self.evidence_service.evaluate_evidence(
            decision=decision, assurance_id=assurance.assurance_id
        )
        assurance.evidence_assurance_status = ev_status
        assurance.evidence_details = ev_details
        all_findings.extend(ev_findings)

        # 5. Cross-Workflow Consistency Checks
        related_decisions = [
            self.repository.get_decision_register(rel_id)
            for rel_id in decision.related_decision_ids
            if self.repository.get_decision_register(rel_id) is not None
        ]
        cons_ok, cons_details, cons_findings, checks = (
            self.consistency_service.evaluate_consistency(
                decision=decision,
                related_decisions=related_decisions,  # type: ignore
                assurance_id=assurance.assurance_id,
            )
        )
        assurance.cross_workflow_consistent = cons_ok
        assurance.consistency_details = cons_details
        all_findings.extend(cons_findings)
        for chk in checks:
            self.repository.save_consistency_check(chk)

        # Save all generated findings
        for f in all_findings:
            self.repository.save_finding(f)

        assurance.findings_count = len(all_findings)
        critical_count = sum(1 for f in all_findings if f.severity == FindingSeverity.CRITICAL)
        high_count = sum(1 for f in all_findings if f.severity == FindingSeverity.HIGH)
        assurance.critical_findings_count = critical_count

        # ---------------------------------------------------------------------
        # Final Lifecycle Synthesis (Strict Governance Precedence)
        # ---------------------------------------------------------------------
        if not prov_ok:
            assurance.lifecycle_state = AssuranceLifecycleState.PROVENANCE_INCOMPLETE
            assurance.assurance_rationale = "Decision failed authoritative provenance verification."
        elif auth_status == AuthorizationVerificationStatus.UNAUTHORIZED or auth_status == AuthorizationVerificationStatus.REVOKED:
            assurance.lifecycle_state = AssuranceLifecycleState.AUTHORIZATION_INVALID
            assurance.assurance_rationale = f"Authorization integrity failed: {auth_status.value}."
        elif auth_status == AuthorizationVerificationStatus.HISTORICAL_UNVERIFIABLE:
            assurance.lifecycle_state = AssuranceLifecycleState.AUTHORIZATION_UNVERIFIABLE
            assurance.assurance_rationale = "Historical authorization evidence is missing or unverifiable."
        elif sep_status == SeparationOfDutiesStatus.SELF_APPROVAL_DETECTED:
            assurance.lifecycle_state = AssuranceLifecycleState.SEPARATION_OF_DUTIES_VIOLATION
            assurance.assurance_rationale = "Separation of duties breach: Self-approval detected."
        elif not cons_ok:
            assurance.lifecycle_state = AssuranceLifecycleState.DECISION_CONFLICT
            assurance.assurance_rationale = "Cross-workflow contradiction detected with related decision."
        elif ev_status == EvidenceAssuranceStatus.EVIDENCE_INVALIDATED:
            assurance.lifecycle_state = AssuranceLifecycleState.EVIDENCE_CONFLICTED
            assurance.assurance_rationale = "Decision relies on invalidated or withdrawn evidence."
        elif not pol_ok:
            assurance.lifecycle_state = AssuranceLifecycleState.POLICY_MISMATCH
            assurance.assurance_rationale = "Decision policy applicability window mismatch."
        elif ev_status == EvidenceAssuranceStatus.EVIDENCE_MISSING:
            assurance.lifecycle_state = AssuranceLifecycleState.EVIDENCE_INCOMPLETE
            assurance.assurance_rationale = "Supporting clinical evidence references are missing."
        elif critical_count > 0 or high_count > 0:
            assurance.lifecycle_state = AssuranceLifecycleState.REVIEW_REQUIRED
            assurance.assurance_rationale = f"Assurance surfaced {high_count + critical_count} high-severity findings."
        elif len(all_findings) > 0:
            assurance.lifecycle_state = AssuranceLifecycleState.VERIFIED_WITH_LIMITATIONS
            assurance.limitations = [f.title for f in all_findings]
            assurance.assurance_rationale = "Decision verified with non-critical limitations noted."
        else:
            assurance.lifecycle_state = AssuranceLifecycleState.VERIFIED
            assurance.assurance_rationale = "All mandatory provenance, authorization, policy, evidence, and consistency checks satisfied."

        self.repository.save_assurance_run(assurance)
        return assurance

    # -------------------------------------------------------------------------
    # Finding Operations
    # -------------------------------------------------------------------------

    def review_finding(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: ReviewAssuranceFindingRequest,
    ) -> AssuranceFindingRecord:
        """Record formal review on an assurance integrity finding."""
        finding = self.repository.get_finding(finding_id)
        if not finding:
            raise AppException(
                code=ErrorCode.ASSURANCE_FINDING_NOT_FOUND,
                message=f"Assurance finding {finding_id} not found.",
                status_code=404,
            )

        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role is not authorized to review assurance findings.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        finding.review_outcome = payload.review_outcome
        finding.review_rationale = payload.review_rationale
        if payload.recommended_action:
            finding.recommended_action = payload.recommended_action
        finding.reviewed_by = user.user_id
        finding.reviewed_at = now

        self.repository.save_finding(finding)
        return finding

    def resolve_finding(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: ResolveAssuranceFindingRequest,
    ) -> AssuranceFindingRecord:
        """Mark an assurance finding resolved with documented rationale."""
        finding = self.repository.get_finding(finding_id)
        if not finding:
            raise AppException(
                code=ErrorCode.ASSURANCE_FINDING_NOT_FOUND,
                message=f"Assurance finding {finding_id} not found.",
                status_code=404,
            )

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Role not authorized to resolve assurance findings.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        finding.is_resolved = True
        finding.resolution_rationale = payload.resolution_rationale
        finding.resolved_by = user.user_id
        finding.resolved_at = now
        finding.evidence_refs.extend(payload.supporting_evidence_refs or [])

        self.repository.save_finding(finding)
        return finding

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    def generate_summary_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> DecisionAssuranceReportResponse:
        """Generate high-level aggregated assurance report."""
        decisions = self.repository.list_decisions(
            organization_id=user.organization_id, facility_id=facility_id, limit=500
        )

        verified = 0
        with_lims = 0
        review_req = 0
        unverifiable = 0
        sep_viol = 0
        conflicts = 0

        for d in decisions:
            latest = self.repository.get_latest_assurance_for_decision(d.decision_id)
            if latest:
                if latest.lifecycle_state == AssuranceLifecycleState.VERIFIED:
                    verified += 1
                elif latest.lifecycle_state == AssuranceLifecycleState.VERIFIED_WITH_LIMITATIONS:
                    with_lims += 1
                elif latest.lifecycle_state == AssuranceLifecycleState.REVIEW_REQUIRED:
                    review_req += 1
                elif latest.lifecycle_state == AssuranceLifecycleState.AUTHORIZATION_UNVERIFIABLE:
                    unverifiable += 1
                elif latest.lifecycle_state == AssuranceLifecycleState.SEPARATION_OF_DUTIES_VIOLATION:
                    sep_viol += 1
                elif latest.lifecycle_state == AssuranceLifecycleState.DECISION_CONFLICT:
                    conflicts += 1

        all_findings = self.repository.list_findings(limit=500)
        active_findings = sum(1 for f in all_findings if not f.is_resolved)

        return DecisionAssuranceReportResponse(
            organization_id=user.organization_id,
            facility_id=facility_id,
            total_decisions_registered=len(decisions),
            verified_count=verified,
            verified_with_limitations_count=with_lims,
            review_required_count=review_req,
            authorization_unverifiable_count=unverifiable,
            separation_violation_count=sep_viol,
            conflicted_count=conflicts,
            active_findings_count=active_findings,
        )


# Global singleton instance
_global_decision_assurance_service = GovernanceDecisionAssuranceService()


def get_governance_decision_assurance_service() -> GovernanceDecisionAssuranceService:
    """Dependency provider returning singleton service instance."""
    return _global_decision_assurance_service

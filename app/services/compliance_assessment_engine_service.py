"""Phase 69: Compliance Assessment Engine Service.

Executes deterministic, policy-versioned compliance assessments:
- Evaluates requirement lifecycle validity
- Evaluates control mapping coverage
- Evaluates evidence presence, accessibility, and validity status
- Synthesizes compliance status under strict governance rules:
  - Missing evidence NEVER yields COMPLIANT (yields EVIDENCE_INSUFFICIENT)
  - Inaccessible evidence yields EVIDENCE_UNAVAILABLE
  - Invalidated evidence yields EVIDENCE_CONFLICTED
  - Stale evidence yields COMPLIANT_WITH_LIMITATIONS (with explicit limitations noted)
  - Unmapped controls yield CONTROL_NOT_IMPLEMENTED
  - Fully satisfied requirements yield COMPLIANT
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_compliance_repository import (
    GovernanceComplianceRepository,
    get_governance_compliance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.compliance_assessment import (
    AssessmentType,
    ComplianceAssessmentRecord,
    ComplianceStatus,
    ReassessRequest,
    TriggerAssessmentRequest,
)
from app.schemas.compliance_evidence import EvidenceValidityStatus
from app.schemas.compliance_finding import (
    ComplianceFindingRecord,
    ComplianceGapCategory,
    CompliancePriority,
)
from app.schemas.compliance_framework import RequirementLifecycleStatus
from app.schemas.user import AuthenticatedUserContext


class ComplianceAssessmentEngineService:
    """Core service executing reproducible governance compliance evaluations."""

    def __init__(self, repository: Optional[GovernanceComplianceRepository] = None) -> None:
        self.repository = repository or get_governance_compliance_repository()

    def evaluate_requirement(
        self,
        user: AuthenticatedUserContext,
        payload: TriggerAssessmentRequest,
    ) -> ComplianceAssessmentRecord:
        """Execute a compliance assessment run for a requirement."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot execute compliance assessments.",
                status_code=403,
            )

        # Check idempotency
        if payload.idempotency_key:
            existing_id = self.repository.get_idempotent_id(payload.idempotency_key)
            if existing_id:
                existing_record = self.repository.get_assessment(existing_id)
                if existing_record:
                    return existing_record

        # Retrieve requirement
        req = self.repository.get_requirement(payload.requirement_id)
        if not req:
            raise AppException(
                code=ErrorCode.COMPLIANCE_REQUIREMENT_NOT_FOUND,
                message=f"Requirement {payload.requirement_id} not found.",
                status_code=404,
            )
        if req.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot assess requirement across tenant boundaries.",
                status_code=403,
            )

        # Invariant: Unapproved requirements cannot be assessed
        if req.lifecycle_status not in {
            RequirementLifecycleStatus.ACTIVE,
            RequirementLifecycleStatus.APPROVED,
        }:
            raise AppException(
                code=ErrorCode.INVALID_COMPLIANCE_STATE,
                message=f"Requirement {req.requirement_id} cannot be assessed in status {req.lifecycle_status.value}.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        assessment = ComplianceAssessmentRecord(
            framework_id=req.framework_id,
            framework_version=req.framework_version,
            requirement_id=req.requirement_id,
            organization_id=req.organization_id,
            facility_id=req.facility_id or user.facility_id,
            assessment_scope=payload.assessment_scope or "ORGANIZATION",
            assessment_type=payload.assessment_type or AssessmentType.MANUAL,
            status=ComplianceStatus.ASSESSMENT_IN_PROGRESS,
            assessed_by=user.user_id,
            assessed_at=now,
            policy_version_used=payload.policy_version_override or req.framework_version,
            correlation_id=payload.correlation_id,
            idempotency_key=payload.idempotency_key,
            created_at=now,
            metadata=payload.metadata or {},
        )

        # Retrieve control mappings and evidence
        mappings = self.repository.list_control_mappings(req.requirement_id)
        evidence_items = self.repository.list_evidence_for_requirement(req.requirement_id)
        assessment.evidence_refs = [ev.evidence_id for ev in evidence_items]

        findings: List[ComplianceFindingRecord] = []
        limitations: List[str] = []

        # ---------------------------------------------------------------------
        # Evaluation Invariant 1: Control Mapping Coverage
        # ---------------------------------------------------------------------
        if not mappings:
            findings.append(
                ComplianceFindingRecord(
                    assessment_id=assessment.assessment_id,
                    requirement_id=req.requirement_id,
                    gap_category=ComplianceGapCategory.REQUIREMENT_MAPPING_MISSING,
                    priority=CompliancePriority.CRITICAL,
                    title="Missing Control Traceability Mapping",
                    description=f"Requirement {req.requirement_code} has no approved control mappings.",
                    assigned_owner_id=req.owner_id,
                    assigned_owner_role=req.owner_role,
                )
            )
            assessment.status = ComplianceStatus.CONTROL_NOT_IMPLEMENTED
            assessment.assessment_rationale = (
                "Assessment failed: No authoritative control mappings are configured for this requirement."
            )

        # ---------------------------------------------------------------------
        # Evaluation Invariant 2: Evidence Completeness & Integrity
        # ---------------------------------------------------------------------
        elif not evidence_items:
            findings.append(
                ComplianceFindingRecord(
                    assessment_id=assessment.assessment_id,
                    requirement_id=req.requirement_id,
                    gap_category=ComplianceGapCategory.REQUIRED_EVIDENCE_MISSING,
                    priority=CompliancePriority.HIGH,
                    title="Required Compliance Evidence Missing",
                    description=f"Requirement {req.requirement_code} has mapped controls but zero supporting evidence items.",
                    assigned_owner_id=req.owner_id,
                    assigned_owner_role=req.owner_role,
                )
            )
            assessment.status = ComplianceStatus.EVIDENCE_INSUFFICIENT
            assessment.assessment_rationale = (
                "Assessment failed: Authoritative controls exist but no evidence items have been indexed."
            )

        else:
            # Check for invalid, inaccessible, or stale items
            inaccessible_items = [ev for ev in evidence_items if not ev.is_accessible]
            invalidated_items = [
                ev for ev in evidence_items if ev.validity_status == EvidenceValidityStatus.INVALIDATED
            ]
            stale_items = [
                ev for ev in evidence_items if ev.validity_status == EvidenceValidityStatus.STALE
            ]

            if invalidated_items:
                findings.append(
                    ComplianceFindingRecord(
                        assessment_id=assessment.assessment_id,
                        requirement_id=req.requirement_id,
                        gap_category=ComplianceGapCategory.EVIDENCE_INVALIDATED,
                        priority=CompliancePriority.CRITICAL,
                        title="Invalidated Supporting Evidence Detected",
                        description=f"Evidence item(s) {[ev.evidence_id for ev in invalidated_items]} was retracted or invalidated.",
                        evidence_refs=[ev.evidence_id for ev in invalidated_items],
                        assigned_owner_id=req.owner_id,
                        assigned_owner_role=req.owner_role,
                    )
                )
                assessment.status = ComplianceStatus.EVIDENCE_CONFLICTED
                assessment.assessment_rationale = (
                    "Assessment failed: Supporting clinical or governance evidence was explicitly invalidated."
                )

            elif inaccessible_items:
                findings.append(
                    ComplianceFindingRecord(
                        assessment_id=assessment.assessment_id,
                        requirement_id=req.requirement_id,
                        gap_category=ComplianceGapCategory.REQUIRED_EVIDENCE_UNAVAILABLE,
                        priority=CompliancePriority.HIGH,
                        title="Required Evidence Inaccessible or Offline",
                        description=f"Evidence item(s) {[ev.evidence_id for ev in inaccessible_items]} could not be accessed.",
                        evidence_refs=[ev.evidence_id for ev in inaccessible_items],
                        assigned_owner_id=req.owner_id,
                        assigned_owner_role=req.owner_role,
                    )
                )
                assessment.status = ComplianceStatus.EVIDENCE_UNAVAILABLE
                assessment.assessment_rationale = (
                    "Assessment failed: Supporting evidence exists but the underlying repository is unreachable."
                )

            elif stale_items:
                findings.append(
                    ComplianceFindingRecord(
                        assessment_id=assessment.assessment_id,
                        requirement_id=req.requirement_id,
                        gap_category=ComplianceGapCategory.EVIDENCE_STALE,
                        priority=CompliancePriority.MEDIUM,
                        title="Stale Supporting Evidence",
                        description=f"Evidence item(s) {[ev.evidence_id for ev in stale_items]} exceeded allowed freshness threshold.",
                        evidence_refs=[ev.evidence_id for ev in stale_items],
                        assigned_owner_id=req.owner_id,
                        assigned_owner_role=req.owner_role,
                    )
                )
                limitations.append(f"{len(stale_items)} supporting evidence item(s) exceeded freshness threshold.")
                assessment.status = ComplianceStatus.COMPLIANT_WITH_LIMITATIONS
                assessment.limitations = limitations
                assessment.assessment_rationale = (
                    "Requirement satisfied with non-critical limitations: Supporting evidence requires scheduled refresh."
                )

            else:
                assessment.status = ComplianceStatus.COMPLIANT
                assessment.assessment_rationale = (
                    "All mapped authoritative controls verified against active, valid supporting evidence."
                )

        # Save findings
        for f in findings:
            self.repository.save_finding(f)

        assessment.findings_count = len(findings)
        assessment.critical_findings_count = sum(
            1 for f in findings if f.priority in {CompliancePriority.CRITICAL, CompliancePriority.HIGH}
        )

        return self.repository.save_assessment(assessment)

    def reassess_requirement(
        self,
        user: AuthenticatedUserContext,
        assessment_id: str,
        payload: ReassessRequest,
    ) -> ComplianceAssessmentRecord:
        """Trigger reassessment of a previously evaluated requirement."""
        prior = self.repository.get_assessment(assessment_id)
        if not prior:
            raise AppException(
                code=ErrorCode.COMPLIANCE_ASSESSMENT_NOT_FOUND,
                message=f"Prior assessment {assessment_id} not found.",
                status_code=404,
            )

        # Mark prior as SUPERSEDED
        prior.status = ComplianceStatus.SUPERSEDED
        self.repository.save_assessment(prior)

        # Execute fresh assessment
        trigger_req = TriggerAssessmentRequest(
            requirement_id=prior.requirement_id,
            assessment_scope=prior.assessment_scope,
            assessment_type=AssessmentType.POST_CORRECTIVE_ACTION,
            policy_version_override=payload.policy_version_override,
            metadata={"reassessment_reason": payload.reassessment_reason, "prior_assessment_id": prior.assessment_id},
        )
        return self.evaluate_requirement(user, trigger_req)


# Global singleton
_global_assessment_engine = ComplianceAssessmentEngineService()


def get_compliance_assessment_engine_service() -> ComplianceAssessmentEngineService:
    """Dependency provider for compliance assessment engine."""
    return _global_assessment_engine

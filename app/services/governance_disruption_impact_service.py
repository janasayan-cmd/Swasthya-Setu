"""Phase 87: Disruption Impact Assessment Engine Service.

Evaluates the potential operational impact of a disruption scenario on critical
governance capabilities, responsibilities, and continuity targets.
Grounds findings in Phase 86 dependency mappings, availability evidence, and fallback readiness.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_disruption_impact_repository import (
    GovernanceDisruptionImpactRepository,
    get_governance_disruption_impact_repository,
)
from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_disruption_common import (
    AssessmentReviewStatus,
    ImpactCertainty,
    ImpactSeverity,
)
from app.schemas.governance_disruption_impact import (
    AssessmentChallengeRequest,
    AssessmentEvidenceRequest,
    AssessmentReviewRequest,
    CreateImpactAssessmentRequest,
    DirectImpactFinding,
    DisruptionImpactAssessmentRecord,
    IndirectImpactFinding,
    RunImpactAssessmentRequest,
)
from app.schemas.governance_resource_common import (
    DependencyMappingStatus,
    FallbackReadinessOutcome,
)


class GovernanceDisruptionImpactService:

    def __init__(
        self,
        repo: GovernanceDisruptionImpactRepository,
        resource_repo: Optional[GovernanceResourceDependencyRepository] = None,
    ) -> None:
        self.repo = repo
        self.resource_repo = resource_repo or get_governance_resource_dependency_repository()

    def create_assessment(
        self, tenant_id: str, user_id: str, request: CreateImpactAssessmentRequest
    ) -> DisruptionImpactAssessmentRecord:
        scenario = self.repo.get_scenario(request.scenario_id, tenant_id)
        if not scenario:
            raise AppException(
                code=ErrorCode.DISRUPTION_SCENARIO_NOT_FOUND,
                message=f"Disruption scenario '{request.scenario_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        now = datetime.utcnow()
        record = DisruptionImpactAssessmentRecord(
            assessment_id=f"dia-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            scenario_id=request.scenario_id,
            assessment_name=request.assessment_name,
            dependency_graph_version=request.dependency_graph_version,
            assessment_timestamp=now,
            affected_capability_refs=list(scenario.affected_capability_refs),
            affected_responsibility_refs=list(scenario.affected_responsibility_refs),
            affected_resource_refs=list(scenario.affected_resource_refs),
            direct_findings=[],
            indirect_findings=[],
            potential_operational_consequences=[],
            available_fallback_refs=[],
            remaining_limitations=[],
            uncertainty_indicators=[],
            evidence_refs=list(scenario.evidence_refs),
            overall_impact_severity=ImpactSeverity.HIGH,
            review_status=AssessmentReviewStatus.DRAFT,
            assessment_version=1,
            assessed_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_assessment(record)

    def get_assessment(self, tenant_id: str, assessment_id: str) -> DisruptionImpactAssessmentRecord:
        record = self.repo.get_assessment(assessment_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.DISRUPTION_IMPACT_ASSESSMENT_NOT_FOUND,
                message=f"Disruption impact assessment '{assessment_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_assessments(
        self,
        tenant_id: str,
        scenario_id: Optional[str] = None,
        review_status: Optional[AssessmentReviewStatus] = None,
        severity: Optional[ImpactSeverity] = None,
    ) -> List[DisruptionImpactAssessmentRecord]:
        return self.repo.list_assessments(tenant_id, scenario_id, review_status, severity)

    def run_assessment(
        self, tenant_id: str, assessment_id: str, user_id: str, request: RunImpactAssessmentRequest
    ) -> DisruptionImpactAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)
        scenario = self.repo.get_scenario(record.scenario_id, tenant_id)
        if not scenario:
            raise AppException(
                code=ErrorCode.DISRUPTION_SCENARIO_NOT_FOUND,
                message=f"Scenario '{record.scenario_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        duration_hours = request.override_duration_hours or scenario.assumed_duration_hours

        # Fetch Phase 86 resource mappings
        approved_mappings = self.resource_repo.list_dependency_mappings(
            tenant_id, status=DependencyMappingStatus.APPROVED
        )
        all_resources = self.resource_repo.list_resources(tenant_id)
        res_map = {r.resource_id: r for r in all_resources}

        direct_findings: List[DirectImpactFinding] = []
        indirect_findings: List[IndirectImpactFinding] = []
        operational_consequences: List[str] = []
        available_fallbacks: List[str] = []
        remaining_limitations: List[str] = []
        uncertainties: List[str] = []
        affected_capabilities = set(record.affected_capability_refs)
        affected_responsibilities = set(record.affected_responsibility_refs)
        affected_resources = set(scenario.affected_resource_refs)

        # 1. Direct Impact Evaluation
        for res_id in scenario.affected_resource_refs:
            resource = res_map.get(res_id)
            res_name = resource.resource_name if resource else res_id

            # Check alternative resources for fallback
            alternatives = self.resource_repo.list_alternatives_for_resource(res_id, tenant_id)
            verified_alts = [
                a for a in alternatives
                if a.fallback_readiness == FallbackReadinessOutcome.READY_VERIFIED
            ]
            has_fallback = len(verified_alts) > 0
            fallback_res_id = verified_alts[0].alternative_resource_id if has_fallback else None
            fallback_readiness = (
                FallbackReadinessOutcome.READY_VERIFIED.value if has_fallback
                else (alternatives[0].fallback_readiness.value if alternatives else "NO_FALLBACK")
            )

            if has_fallback:
                available_fallbacks.append(f"Fallback available for '{res_name}' via '{fallback_res_id}'.")
            else:
                remaining_limitations.append(f"Resource '{res_name}' lacks verified fallback.")

            # Mappings where this resource is directly required
            direct_maps = [m for m in approved_mappings if m.resource_id == res_id]
            for m in direct_maps:
                affected_capabilities.add(m.governance_capability_ref)
                if m.responsibility_ref:
                    affected_responsibilities.add(m.responsibility_ref)

                finding_sev = ImpactSeverity.CRITICAL if not has_fallback else ImpactSeverity.MEDIUM
                direct_findings.append(DirectImpactFinding(
                    finding_id=f"dir-{uuid.uuid4().hex[:10]}",
                    resource_id=res_id,
                    resource_name=res_name,
                    affected_capability_ref=m.governance_capability_ref,
                    affected_responsibility_ref=m.responsibility_ref,
                    dependency_type=m.dependency_type.value if hasattr(m.dependency_type, "value") else str(m.dependency_type),
                    severity=finding_sev,
                    certainty=ImpactCertainty.CONFIRMED if has_fallback else ImpactCertainty.POTENTIAL,
                    operating_capacity_remaining_pct=50.0 if has_fallback else 0.0,
                    fallback_available=has_fallback,
                    fallback_resource_id=fallback_res_id,
                    fallback_readiness=fallback_readiness,
                    explanation=f"Resource '{res_name}' failure directly degrades capability '{m.governance_capability_ref}'.",
                    evidence_refs=m.evidence_refs,
                ))

        # 2. Indirect Dependency Propagation
        if request.include_indirect_dependencies:
            for res_id in scenario.affected_resource_refs:
                # Find other resources that list res_id in their dependency_refs
                dependent_resources = [
                    r for r in all_resources
                    if res_id in r.dependency_refs
                ]
                for dep_res in dependent_resources:
                    affected_resources.add(dep_res.resource_id)
                    # Find capabilities depending on this dependent resource
                    dep_maps = [m for m in approved_mappings if m.resource_id == dep_res.resource_id]
                    for dm in dep_maps:
                        affected_capabilities.add(dm.governance_capability_ref)
                        indirect_findings.append(IndirectImpactFinding(
                            finding_id=f"ind-{uuid.uuid4().hex[:10]}",
                            root_resource_id=res_id,
                            intermediate_resource_id=dep_res.resource_id,
                            affected_capability_ref=dm.governance_capability_ref,
                            affected_responsibility_ref=dm.responsibility_ref,
                            propagation_hops=2,
                            severity=ImpactSeverity.HIGH,
                            certainty=ImpactCertainty.CONDITIONAL,
                            explanation=(
                                f"Resource '{dep_res.resource_name}' depends upstream on disrupted '{res_id}', "
                                f"propagating degradation to capability '{dm.governance_capability_ref}'."
                            ),
                            evidence_refs=[],
                        ))

        # 3. Disruption Duration Analysis & MTPD threshold
        mtpd_exceeded = duration_hours >= 4.0
        rto_exceeded = duration_hours >= 2.0
        if mtpd_exceeded:
            operational_consequences.append(
                f"Disruption duration ({duration_hours}h) exceeds Maximum Tolerable Period of Disruption (4.0h)."
            )
        if len(direct_findings) == 0 and len(indirect_findings) == 0:
            uncertainties.append("No approved Phase 86 capability mappings found for disrupted resources.")

        # Determine overall severity
        has_critical = any(f.severity == ImpactSeverity.CRITICAL for f in direct_findings) or mtpd_exceeded
        overall_severity = ImpactSeverity.CRITICAL if has_critical else ImpactSeverity.HIGH

        now = datetime.utcnow()
        record.affected_capability_refs = sorted(list(affected_capabilities))
        record.affected_responsibility_refs = sorted(list(affected_responsibilities))
        record.affected_resource_refs = sorted(list(affected_resources))
        record.direct_findings = direct_findings
        record.indirect_findings = indirect_findings
        record.potential_operational_consequences = operational_consequences
        record.available_fallback_refs = available_fallbacks
        record.remaining_limitations = remaining_limitations
        record.uncertainty_indicators = uncertainties
        record.mtpd_exceeded = mtpd_exceeded
        record.rto_exceeded = rto_exceeded
        record.overall_impact_severity = overall_severity
        record.review_status = AssessmentReviewStatus.AUTOMATED_ANALYSIS_COMPLETED
        record.updated_at = now

        return self.repo.save_assessment(record)

    def submit_for_review(self, tenant_id: str, assessment_id: str, user_id: str) -> DisruptionImpactAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)
        if record.review_status not in (
            AssessmentReviewStatus.AUTOMATED_ANALYSIS_COMPLETED,
            AssessmentReviewStatus.DRAFT,
            AssessmentReviewStatus.CHALLENGED,
        ):
            raise AppException(
                code=ErrorCode.INVALID_IMPACT_ASSESSMENT_STATE,
                message=f"Cannot submit assessment in state '{record.review_status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        record.review_status = AssessmentReviewStatus.EVIDENCE_REVIEW_PENDING
        record.updated_at = datetime.utcnow()
        return self.repo.save_assessment(record)

    def review_assessment(
        self, tenant_id: str, assessment_id: str, reviewer_id: str, request: AssessmentReviewRequest
    ) -> DisruptionImpactAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)
        if record.assessed_by == reviewer_id:
            raise AppException(
                code=ErrorCode.DISRUPTION_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties: Assessor cannot review or approve their own impact assessment.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        now = datetime.utcnow()
        record.review_status = request.review_status
        record.review_notes = request.review_notes
        record.reviewed_by = reviewer_id
        record.reviewed_at = now
        record.updated_at = now
        return self.repo.save_assessment(record)

    def challenge_assessment(
        self, tenant_id: str, assessment_id: str, challenger_id: str, request: AssessmentChallengeRequest
    ) -> DisruptionImpactAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)
        now = datetime.utcnow()
        record.review_status = AssessmentReviewStatus.CHALLENGED
        record.challenge_notes = request.challenge_notes
        record.challenged_by = challenger_id
        record.updated_at = now
        return self.repo.save_assessment(record)

    def request_evidence(
        self, tenant_id: str, assessment_id: str, user_id: str, request: AssessmentEvidenceRequest
    ) -> DisruptionImpactAssessmentRecord:
        record = self.get_assessment(tenant_id, assessment_id)
        record.review_status = AssessmentReviewStatus.ADDITIONAL_EVIDENCE_REQUESTED
        record.uncertainty_indicators.append(
            f"Evidence requested: {request.requested_evidence_description} for {request.target_capabilities}"
        )
        record.updated_at = datetime.utcnow()
        return self.repo.save_assessment(record)


_impact_service: Optional[GovernanceDisruptionImpactService] = None


def get_governance_disruption_impact_service() -> GovernanceDisruptionImpactService:
    global _impact_service
    if _impact_service is None:
        _impact_service = GovernanceDisruptionImpactService(
            get_governance_disruption_impact_repository()
        )
    return _impact_service

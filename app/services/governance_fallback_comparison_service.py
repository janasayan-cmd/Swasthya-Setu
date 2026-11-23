"""Phase 87: Fallback Effectiveness Comparison Service.

Evaluates and compares the operational mitigation value of different fallback arrangements
using Phase 86 readiness tiers and verification evidence.
"""

import uuid
from datetime import datetime
from typing import List, Optional
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
from app.schemas.governance_disruption_common import ImpactSeverity
from app.schemas.governance_fallback_comparison import (
    FallbackComparisonItem,
    FallbackComparisonRecord,
    RunFallbackComparisonRequest,
)
from app.schemas.governance_resource_common import (
    DependencyMappingStatus,
    FallbackReadinessOutcome,
)


class GovernanceFallbackComparisonService:

    def __init__(
        self,
        repo: GovernanceDisruptionImpactRepository,
        resource_repo: Optional[GovernanceResourceDependencyRepository] = None,
    ) -> None:
        self.repo = repo
        self.resource_repo = resource_repo or get_governance_resource_dependency_repository()

    def compare_fallbacks(
        self, tenant_id: str, assessment_id: str, user_id: str, request: RunFallbackComparisonRequest
    ) -> FallbackComparisonRecord:
        assessment = self.repo.get_assessment(assessment_id, tenant_id)
        if not assessment:
            raise AppException(
                code=ErrorCode.DISRUPTION_IMPACT_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        resource = self.resource_repo.get_resource(request.resource_id, tenant_id)
        if not resource:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource '{request.resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        approved_mappings = self.resource_repo.list_dependency_mappings(
            tenant_id, status=DependencyMappingStatus.APPROVED
        )
        dependent_caps = [
            m.governance_capability_ref for m in approved_mappings if m.resource_id == request.resource_id
        ]

        alternatives = self.resource_repo.list_alternatives_for_resource(request.resource_id, tenant_id)
        comparison_items: List[FallbackComparisonItem] = []

        # Baseline: No fallback
        comparison_items.append(FallbackComparisonItem(
            fallback_id=None,
            alternative_resource_id=None,
            alternative_resource_name="None (Baseline Unmitigated)",
            readiness_tier="NO_FALLBACK",
            estimated_impact_severity=ImpactSeverity.CRITICAL if len(dependent_caps) >= 2 else ImpactSeverity.HIGH,
            mitigated_capabilities=[],
            unmitigated_capabilities=dependent_caps,
            shares_upstream_dependency=False,
            evidence_quality="CONFIRMED",
            notes="Without fallback, capability execution halts entirely during outage.",
        ))

        optimal_alt_id: Optional[str] = None
        recommendations: List[str] = []

        for alt in alternatives:
            alt_res = self.resource_repo.get_resource(alt.alternative_resource_id, tenant_id)
            alt_name = alt_res.resource_name if alt_res else alt.alternative_resource_id

            # Check if alternative shares upstream dependencies with primary
            shares_upstream = False
            if alt_res and resource:
                common_deps = set(alt_res.dependency_refs).intersection(set(resource.dependency_refs))
                if common_deps:
                    shares_upstream = True

            tier = alt.fallback_readiness.value if hasattr(alt.fallback_readiness, "value") else str(alt.fallback_readiness)
            if alt.fallback_readiness == FallbackReadinessOutcome.READY_VERIFIED:
                sev = ImpactSeverity.LOW if not shares_upstream else ImpactSeverity.MEDIUM
                eq = "EVIDENCE_BACKED"
                notes = "Demonstrated live operational readiness in validated drills."
                if not optimal_alt_id and not shares_upstream:
                    optimal_alt_id = alt.alternative_id
            elif alt.fallback_readiness == FallbackReadinessOutcome.CONDITIONALLY_READY:
                sev = ImpactSeverity.MEDIUM
                eq = "PARTIALLY_EVIDENCED"
                notes = "Operational with identified constraints or limited capacity."
            elif alt.fallback_readiness == FallbackReadinessOutcome.INSUFFICIENT_EVIDENCE:
                sev = ImpactSeverity.HIGH
                eq = "ASSUMPTION_BASED"
                notes = "Evidence lacking; cannot be relied upon during actual disruption."
            else:
                sev = ImpactSeverity.HIGH
                eq = "UNKNOWN"
                notes = f"Readiness unverified ({tier})."

            mitigated = dependent_caps if alt.fallback_readiness == FallbackReadinessOutcome.READY_VERIFIED else []
            unmitigated = [] if alt.fallback_readiness == FallbackReadinessOutcome.READY_VERIFIED else dependent_caps

            comparison_items.append(FallbackComparisonItem(
                fallback_id=alt.alternative_id,
                alternative_resource_id=alt.alternative_resource_id,
                alternative_resource_name=alt_name,
                readiness_tier=tier,
                estimated_impact_severity=sev,
                mitigated_capabilities=mitigated,
                unmitigated_capabilities=unmitigated,
                shares_upstream_dependency=shares_upstream,
                evidence_quality=eq,
                notes=notes,
            ))

        if optimal_alt_id:
            recommendations.append(f"Recommended primary fallback: Alternative '{optimal_alt_id}'.")
        else:
            recommendations.append("No verified independent fallback found. Recommend immediate fallback testing.")

        now = datetime.utcnow()
        record = FallbackComparisonRecord(
            comparison_id=f"fb-cmp-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            resource_id=request.resource_id,
            baseline_severity_without_fallback=ImpactSeverity.CRITICAL,
            comparison_items=comparison_items,
            optimal_fallback_id=optimal_alt_id,
            recommendations=recommendations,
            compared_by=user_id,
            compared_at=now,
        )
        return self.repo.save_fallback_comparison(record)

    def get_fallback_comparison(self, tenant_id: str, comparison_id: str) -> FallbackComparisonRecord:
        record = self.repo.get_fallback_comparison(comparison_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.FALLBACK_COMPARISON_NOT_FOUND,
                message=f"Fallback comparison '{comparison_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_fallback_comparisons(
        self, tenant_id: str, assessment_id: Optional[str] = None
    ) -> List[FallbackComparisonRecord]:
        return self.repo.list_fallback_comparisons(tenant_id, assessment_id)


_fallback_comparison_service: Optional[GovernanceFallbackComparisonService] = None


def get_governance_fallback_comparison_service() -> GovernanceFallbackComparisonService:
    global _fallback_comparison_service
    if _fallback_comparison_service is None:
        _fallback_comparison_service = GovernanceFallbackComparisonService(
            get_governance_disruption_impact_repository()
        )
    return _fallback_comparison_service

"""Phase 86: SPOF and Dependency Graph Analysis Service.

Analyzes the dependency graph to detect single points of failure, shared dependencies,
circular dependencies, and concentration risks. All findings are explainable.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_resource_common import (
    DependencyMappingStatus,
    FallbackReadinessOutcome,
    ResourceAvailabilityStatus,
    SPOFSeverity,
)
from app.schemas.governance_resource_spof_analysis import (
    DependencyGraphAnalysisRecord,
    RunDependencyGraphAnalysisRequest,
    SPOFFindingRecord,
)


class GovernanceResourceSPOFAnalysisService:

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def run_analysis(
        self,
        tenant_id: str,
        user_id: str,
        request: RunDependencyGraphAnalysisRequest,
    ) -> DependencyGraphAnalysisRecord:
        resources = self.repo.list_resources(tenant_id)
        mappings = self.repo.list_dependency_mappings(
            tenant_id, status=DependencyMappingStatus.APPROVED
        )
        alternatives = self.repo.list_alternatives(tenant_id)

        findings: List[SPOFFindingRecord] = []
        circular_deps: List[List[str]] = []
        shared_deps: List[dict] = []
        critical_path: List[str] = []
        caps_without_mapping: List[str] = []
        resources_without_verified_avail: List[str] = []
        resources_without_fallback: List[str] = []
        advisory_notes: List[str] = []

        # Build resource-to-capabilities map
        resource_to_caps: Dict[str, List[str]] = {}
        capability_to_resources: Dict[str, List[str]] = {}
        for m in mappings:
            if m.resource_id not in resource_to_caps:
                resource_to_caps[m.resource_id] = []
            resource_to_caps[m.resource_id].append(m.governance_capability_ref)
            if m.governance_capability_ref not in capability_to_resources:
                capability_to_resources[m.governance_capability_ref] = []
            capability_to_resources[m.governance_capability_ref].append(m.resource_id)

        # Detect SPOF: single resource supporting multiple REQUIRED critical capabilities
        for resource_id, cap_refs in resource_to_caps.items():
            if len(cap_refs) >= 2:
                resource = self.repo.get_resource(resource_id, tenant_id)
                res_name = resource.resource_name if resource else resource_id
                # Check if any alternatives exist with verified readiness
                res_alternatives = self.repo.list_alternatives_for_resource(resource_id, tenant_id)
                has_verified_fallback = any(
                    a.fallback_readiness == FallbackReadinessOutcome.READY_VERIFIED
                    for a in res_alternatives
                )
                severity = SPOFSeverity.CRITICAL if len(cap_refs) >= 3 else SPOFSeverity.HIGH
                if not has_verified_fallback:
                    findings.append(SPOFFindingRecord(
                        finding_id=f"spof-{uuid.uuid4().hex[:10]}",
                        tenant_id=tenant_id,
                        finding_type="SHARED_RESOURCE_SINGLE_POINT_OF_FAILURE",
                        affected_capability_refs=cap_refs,
                        affected_resource_refs=[resource_id],
                        dependency_path=[resource_id] + cap_refs,
                        detection_rule="shared_resource_spof_v1",
                        severity=severity,
                        recommended_follow_up=f"Resource '{res_name}' supports {len(cap_refs)} capabilities without a verified fallback. Document and assess an alternative resource.",
                    ))
                # Mark as shared dep
                shared_deps.append({
                    "resource_id": resource_id,
                    "resource_name": res_name,
                    "capability_refs": cap_refs,
                    "has_verified_fallback": has_verified_fallback,
                })

        # Detect capabilities without any resource mapping
        all_known_caps = set(capability_to_resources.keys())
        # We can only flag capabilities referenced in mappings not approved
        draft_mappings = self.repo.list_dependency_mappings(tenant_id, status=DependencyMappingStatus.DRAFT)
        for m in draft_mappings:
            if m.governance_capability_ref not in all_known_caps:
                caps_without_mapping.append(m.governance_capability_ref)

        # Check resources for verified availability
        for res in resources:
            latest_obs = self.repo.get_latest_observation(res.resource_id, tenant_id)
            if not latest_obs or latest_obs.observed_status not in (
                ResourceAvailabilityStatus.AVAILABLE_VERIFIED,
                ResourceAvailabilityStatus.AVAILABLE_UNVERIFIED,
            ):
                resources_without_verified_avail.append(res.resource_id)

        # Check critical resources for fallback
        for res in resources:
            from app.schemas.governance_resource_common import ResourceCriticality
            if res.criticality in (ResourceCriticality.ESSENTIAL, ResourceCriticality.CRITICAL):
                res_alts = self.repo.list_alternatives_for_resource(res.resource_id, tenant_id)
                has_verified = any(
                    a.fallback_readiness == FallbackReadinessOutcome.READY_VERIFIED
                    for a in res_alts
                )
                if not has_verified:
                    resources_without_fallback.append(res.resource_id)
                    # Add LOW/MEDIUM SPOF finding for essential resources with no fallback
                    if res.criticality == ResourceCriticality.ESSENTIAL:
                        cap_refs_for_res = resource_to_caps.get(res.resource_id, [])
                        findings.append(SPOFFindingRecord(
                            finding_id=f"spof-{uuid.uuid4().hex[:10]}",
                            tenant_id=tenant_id,
                            finding_type="ESSENTIAL_RESOURCE_NO_VERIFIED_FALLBACK",
                            affected_capability_refs=cap_refs_for_res,
                            affected_resource_refs=[res.resource_id],
                            dependency_path=[res.resource_id],
                            detection_rule="essential_no_fallback_v1",
                            severity=SPOFSeverity.HIGH,
                            recommended_follow_up=f"Essential resource '{res.resource_name}' has no verified fallback. Assess and document an alternative.",
                        ))

        # Circular dependency detection (simple: check if a resource lists itself as a dep)
        for res in resources:
            if res.resource_id in res.dependency_refs:
                circular_deps.append([res.resource_id, res.resource_id])
                findings.append(SPOFFindingRecord(
                    finding_id=f"spof-{uuid.uuid4().hex[:10]}",
                    tenant_id=tenant_id,
                    finding_type="CIRCULAR_DEPENDENCY",
                    affected_resource_refs=[res.resource_id],
                    dependency_path=[res.resource_id],
                    detection_rule="circular_dependency_v1",
                    severity=SPOFSeverity.CRITICAL,
                    recommended_follow_up=f"Resource '{res.resource_name}' lists itself as a dependency. Review and correct dependency data.",
                ))

        # Build critical path (resources supporting most capabilities)
        sorted_by_cap_count = sorted(resource_to_caps.items(), key=lambda x: len(x[1]), reverse=True)
        critical_path = [r[0] for r in sorted_by_cap_count[:5]]

        if resources_without_verified_avail:
            advisory_notes.append(
                f"{len(resources_without_verified_avail)} resource(s) lack verified availability evidence. Treat these as UNKNOWN status."
            )
        if resources_without_fallback:
            advisory_notes.append(
                f"{len(resources_without_fallback)} critical/essential resource(s) have no verified fallback arrangement."
            )
        if findings:
            advisory_notes.append(
                f"{len(findings)} SPOF finding(s) detected. All are advisory and require human review before action."
            )

        analysis = DependencyGraphAnalysisRecord(
            analysis_id=f"gpa-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            analysis_scope=request.analysis_scope,
            total_resources_analyzed=len(resources),
            total_dependencies_analyzed=len(mappings),
            spof_findings=findings,
            circular_dependencies_detected=circular_deps,
            shared_dependencies=shared_deps,
            critical_path_resource_ids=critical_path,
            capabilities_without_resource_mapping=list(set(caps_without_mapping)),
            resources_without_verified_availability=resources_without_verified_avail,
            resources_without_fallback=resources_without_fallback,
            analyzed_by=user_id,
            analyzed_at=datetime.utcnow(),
            advisory_notes=advisory_notes,
        )
        return self.repo.save_graph_analysis(analysis)

    def get_analysis(self, tenant_id: str, analysis_id: str) -> DependencyGraphAnalysisRecord:
        from app.core.exceptions import AppException, ErrorCode
        from fastapi import status as http_status
        record = self.repo.get_graph_analysis(analysis_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.DEPENDENCY_GRAPH_ANALYSIS_NOT_FOUND,
                message=f"Dependency graph analysis '{analysis_id}' not found.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_analyses(self, tenant_id: str) -> List[DependencyGraphAnalysisRecord]:
        return self.repo.list_graph_analyses(tenant_id)


_spof_service: Optional[GovernanceResourceSPOFAnalysisService] = None


def get_governance_resource_spof_analysis_service() -> GovernanceResourceSPOFAnalysisService:
    global _spof_service
    if _spof_service is None:
        _spof_service = GovernanceResourceSPOFAnalysisService(
            get_governance_resource_dependency_repository()
        )
    return _spof_service

"""Phase 87: Cascading Failure and Cross-Dependency Propagation Service.

Implements explainable cascading dependency analysis across multi-level resource hierarchies,
shared upstream feeds, and common external providers.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
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
from app.schemas.governance_cascading_failure import (
    CascadingAnalysisRecord,
    CascadingFailureFinding,
    PropagationNode,
    PropagationPath,
    RunCascadingAnalysisRequest,
)
from app.schemas.governance_disruption_common import (
    ImpactCertainty,
    ImpactSeverity,
)
from app.schemas.governance_resource_common import DependencyMappingStatus


class GovernanceCascadingFailureService:

    def __init__(
        self,
        repo: GovernanceDisruptionImpactRepository,
        resource_repo: Optional[GovernanceResourceDependencyRepository] = None,
    ) -> None:
        self.repo = repo
        self.resource_repo = resource_repo or get_governance_resource_dependency_repository()

    def run_cascading_analysis(
        self, tenant_id: str, user_id: str, request: RunCascadingAnalysisRequest
    ) -> CascadingAnalysisRecord:
        # Determine root resources to analyze
        root_resource_ids: List[str] = []
        if request.assessment_id:
            assessment = self.repo.get_assessment(request.assessment_id, tenant_id)
            if not assessment:
                raise AppException(
                    code=ErrorCode.DISRUPTION_IMPACT_ASSESSMENT_NOT_FOUND,
                    message=f"Assessment '{request.assessment_id}' not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            root_resource_ids = list(assessment.affected_resource_refs)
        elif request.scenario_id:
            scenario = self.repo.get_scenario(request.scenario_id, tenant_id)
            if not scenario:
                raise AppException(
                    code=ErrorCode.DISRUPTION_SCENARIO_NOT_FOUND,
                    message=f"Scenario '{request.scenario_id}' not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            root_resource_ids = list(scenario.affected_resource_refs)
        else:
            all_resources = self.resource_repo.list_resources(tenant_id)
            root_resource_ids = [r.resource_id for r in all_resources]

        all_resources = self.resource_repo.list_resources(tenant_id)
        res_map = {r.resource_id: r for r in all_resources}
        approved_mappings = self.resource_repo.list_dependency_mappings(
            tenant_id, status=DependencyMappingStatus.APPROVED
        )

        propagation_paths: List[PropagationPath] = []
        cascading_findings: List[CascadingFailureFinding] = []
        shared_upstream_resources: List[Dict[str, object]] = []
        common_provider_risks: List[Dict[str, object]] = []
        max_depth_recorded = 1

        # Check for common external providers
        provider_to_resources: Dict[str, List[str]] = {}
        for r in all_resources:
            if r.external_provider_ref:
                if r.external_provider_ref not in provider_to_resources:
                    provider_to_resources[r.external_provider_ref] = []
                provider_to_resources[r.external_provider_ref].append(r.resource_id)

        for provider_ref, r_ids in provider_to_resources.items():
            if len(r_ids) >= 2:
                common_provider_risks.append({
                    "provider_ref": provider_ref,
                    "resource_count": len(r_ids),
                    "resource_ids": r_ids,
                    "risk_summary": f"Provider '{provider_ref}' is a single point of failure for {len(r_ids)} critical resources.",
                })
                cascading_findings.append(CascadingFailureFinding(
                    finding_id=f"casc-prov-{uuid.uuid4().hex[:10]}",
                    initial_disruption_source=f"Provider: {provider_ref}",
                    propagation_path=r_ids,
                    affected_dependency_nodes=r_ids,
                    affected_capabilities=[],
                    affected_responsibilities=[],
                    potential_impact=f"Outage of provider '{provider_ref}' cascades to multiple assets simultaneously.",
                    severity=ImpactSeverity.CRITICAL if len(r_ids) >= 3 else ImpactSeverity.HIGH,
                    certainty=ImpactCertainty.CONFIRMED,
                    common_provider_ref=provider_ref,
                    explanation=f"Common external provider failure domain shared across {len(r_ids)} assets.",
                ))

        # Check propagation paths for each root resource
        for root_id in root_resource_ids:
            root_res = res_map.get(root_id)
            root_name = root_res.resource_name if root_res else root_id

            # Direct mapping from root
            root_caps = [m.governance_capability_ref for m in approved_mappings if m.resource_id == root_id]
            root_resps = [m.responsibility_ref for m in approved_mappings if m.resource_id == root_id and m.responsibility_ref]

            # Level 1 path
            nodes_l1 = [
                PropagationNode(
                    node_id=root_id,
                    node_type="RESOURCE",
                    name=root_name,
                    depth=0,
                    dependency_relationship="ROOT_DISRUPTION",
                )
            ]
            for cap in root_caps:
                nodes_l1.append(
                    PropagationNode(
                        node_id=cap,
                        node_type="CAPABILITY",
                        name=cap,
                        depth=1,
                        parent_node_id=root_id,
                        dependency_relationship="DIRECT_REQUIRED",
                    )
                )

            propagation_paths.append(PropagationPath(
                path_id=f"path-{uuid.uuid4().hex[:10]}",
                root_disruption_id=root_id,
                terminal_node_id=root_caps[0] if root_caps else root_id,
                nodes=nodes_l1,
                total_hops=1,
                propagation_type="DIRECT",
            ))

            # Level 2 downstream resource dependencies
            downstream_res = [r for r in all_resources if root_id in r.dependency_refs]
            if downstream_res:
                max_depth_recorded = max(max_depth_recorded, 2)
                for ds in downstream_res:
                    ds_caps = [m.governance_capability_ref for m in approved_mappings if m.resource_id == ds.resource_id]
                    nodes_l2 = list(nodes_l1) + [
                        PropagationNode(
                            node_id=ds.resource_id,
                            node_type="RESOURCE",
                            name=ds.resource_name,
                            depth=1,
                            parent_node_id=root_id,
                            dependency_relationship="UPSTREAM_FEED",
                        )
                    ]
                    for dsc in ds_caps:
                        nodes_l2.append(
                            PropagationNode(
                                node_id=dsc,
                                node_type="CAPABILITY",
                                name=dsc,
                                depth=2,
                                parent_node_id=ds.resource_id,
                                dependency_relationship="INDIRECT_CASCADE",
                            )
                        )
                    propagation_paths.append(PropagationPath(
                        path_id=f"path-{uuid.uuid4().hex[:10]}",
                        root_disruption_id=root_id,
                        terminal_node_id=ds_caps[0] if ds_caps else ds.resource_id,
                        nodes=nodes_l2,
                        total_hops=2,
                        propagation_type="MULTI_LEVEL",
                    ))
                    cascading_findings.append(CascadingFailureFinding(
                        finding_id=f"casc-{uuid.uuid4().hex[:10]}",
                        initial_disruption_source=root_id,
                        propagation_path=[root_id, ds.resource_id] + ds_caps,
                        affected_dependency_nodes=[root_id, ds.resource_id],
                        affected_capabilities=ds_caps,
                        affected_responsibilities=[],
                        potential_impact=f"Cascade from '{root_name}' to downstream '{ds.resource_name}' degrades {len(ds_caps)} capabilities.",
                        severity=ImpactSeverity.HIGH,
                        certainty=ImpactCertainty.POTENTIAL,
                        shared_upstream_dependency_id=root_id,
                        explanation=f"Resource '{ds.resource_name}' has explicit dependency on disrupted '{root_name}'.",
                    ))

        # Check shared upstream dependencies
        res_dep_count: Dict[str, Set[str]] = {}
        for m in approved_mappings:
            if m.resource_id not in res_dep_count:
                res_dep_count[m.resource_id] = set()
            res_dep_count[m.resource_id].add(m.governance_capability_ref)

        for res_id, caps in res_dep_count.items():
            if len(caps) >= 2:
                r_obj = res_map.get(res_id)
                shared_upstream_resources.append({
                    "resource_id": res_id,
                    "resource_name": r_obj.resource_name if r_obj else res_id,
                    "capability_count": len(caps),
                    "capabilities": sorted(list(caps)),
                })

        now = datetime.utcnow()
        record = CascadingAnalysisRecord(
            analysis_id=f"casc-an-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            assessment_id=request.assessment_id,
            scenario_id=request.scenario_id,
            total_paths_identified=len(propagation_paths),
            max_depth_traversed=max_depth_recorded,
            cascading_findings=cascading_findings,
            propagation_paths=propagation_paths,
            shared_upstream_resources=shared_upstream_resources,
            common_provider_risks=common_provider_risks,
            analyzed_by=user_id,
            analyzed_at=now,
        )
        return self.repo.save_cascading_analysis(record)

    def get_cascading_analysis(self, tenant_id: str, analysis_id: str) -> CascadingAnalysisRecord:
        record = self.repo.get_cascading_analysis(analysis_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CASCADING_ANALYSIS_NOT_FOUND,
                message=f"Cascading analysis '{analysis_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_cascading_analyses(
        self, tenant_id: str, assessment_id: Optional[str] = None
    ) -> List[CascadingAnalysisRecord]:
        return self.repo.list_cascading_analyses(tenant_id, assessment_id)


_cascading_service: Optional[GovernanceCascadingFailureService] = None


def get_governance_cascading_failure_service() -> GovernanceCascadingFailureService:
    global _cascading_service
    if _cascading_service is None:
        _cascading_service = GovernanceCascadingFailureService(
            get_governance_disruption_impact_repository()
        )
    return _cascading_service

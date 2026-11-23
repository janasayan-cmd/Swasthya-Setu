"""Phase 87: Multi-Resource and Compound Disruption Analysis Service.

Evaluates scenarios involving multiple simultaneous resource disruptions and identifies
hidden common-mode failures, non-independent fallback dependencies, and combined constraints.
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
from app.schemas.governance_compound_disruption import (
    CompoundDisruptionScenarioRecord,
    CreateCompoundScenarioRequest,
    EvaluateCompoundScenarioRequest,
)
from app.schemas.governance_disruption_common import ImpactSeverity
from app.schemas.governance_resource_common import DependencyMappingStatus


class GovernanceCompoundDisruptionService:

    def __init__(
        self,
        repo: GovernanceDisruptionImpactRepository,
        resource_repo: Optional[GovernanceResourceDependencyRepository] = None,
    ) -> None:
        self.repo = repo
        self.resource_repo = resource_repo or get_governance_resource_dependency_repository()

    def create_compound_scenario(
        self, tenant_id: str, user_id: str, request: CreateCompoundScenarioRequest
    ) -> CompoundDisruptionScenarioRecord:
        now = datetime.utcnow()
        record = CompoundDisruptionScenarioRecord(
            compound_scenario_id=f"cmp-scen-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            scenario_name=request.scenario_name,
            description=request.description,
            component_scenario_ids=request.component_scenario_ids,
            simultaneous_resource_ids=request.simultaneous_resource_ids,
            shared_dependencies_identified=[],
            combined_affected_capabilities=[],
            combined_affected_responsibilities=[],
            available_fallback_arrangements=[],
            non_independent_fallbacks=[],
            capacity_limitations=[],
            unresolved_assumptions=[],
            compound_severity=ImpactSeverity.CRITICAL,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_compound_scenario(record)

    def get_compound_scenario(self, tenant_id: str, compound_scenario_id: str) -> CompoundDisruptionScenarioRecord:
        record = self.repo.get_compound_scenario(compound_scenario_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.COMPOUND_SCENARIO_NOT_FOUND,
                message=f"Compound disruption scenario '{compound_scenario_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_compound_scenarios(self, tenant_id: str) -> List[CompoundDisruptionScenarioRecord]:
        return self.repo.list_compound_scenarios(tenant_id)

    def evaluate_compound_scenario(
        self, tenant_id: str, compound_scenario_id: str, user_id: str, request: EvaluateCompoundScenarioRequest
    ) -> CompoundDisruptionScenarioRecord:
        record = self.get_compound_scenario(tenant_id, compound_scenario_id)

        all_res_ids: Set[str] = set(record.simultaneous_resource_ids)
        # Also include resources from component scenarios
        for scen_id in record.component_scenario_ids:
            scen = self.repo.get_scenario(scen_id, tenant_id)
            if scen:
                all_res_ids.update(scen.affected_resource_refs)

        approved_mappings = self.resource_repo.list_dependency_mappings(
            tenant_id, status=DependencyMappingStatus.APPROVED
        )
        all_resources = self.resource_repo.list_resources(tenant_id)
        res_map = {r.resource_id: r for r in all_resources}

        combined_caps: Set[str] = set()
        combined_resps: Set[str] = set()
        shared_deps: List[str] = []
        non_independent_fallbacks: List[str] = []
        available_fallbacks: List[str] = []
        capacity_limits: List[str] = []

        # Find all capabilities and responsibilities mapped to these simultaneous resources
        for r_id in all_res_ids:
            maps = [m for m in approved_mappings if m.resource_id == r_id]
            for m in maps:
                combined_caps.add(m.governance_capability_ref)
                if m.responsibility_ref:
                    combined_resps.add(m.responsibility_ref)

            # Check alternative resources
            alts = self.resource_repo.list_alternatives_for_resource(r_id, tenant_id)
            for a in alts:
                # Non-independence check: does the alternative itself depend on any of the disrupted resources?
                alt_res = res_map.get(a.alternative_resource_id)
                if alt_res:
                    overlap = set(alt_res.dependency_refs).intersection(all_res_ids)
                    if overlap or a.alternative_resource_id in all_res_ids:
                        non_independent_fallbacks.append(
                            f"Alternative '{a.alternative_resource_id}' for '{r_id}' is co-disrupted or depends on disrupted assets {list(overlap)}."
                        )
                    else:
                        available_fallbacks.append(a.alternative_resource_id)

        # Check for shared upstream dependencies across the simultaneous resources
        for r_id in all_res_ids:
            r_obj = res_map.get(r_id)
            if r_obj:
                for up_id in r_obj.dependency_refs:
                    if up_id in all_res_ids and up_id != r_id:
                        shared_deps.append(f"Resource '{r_id}' depends upstream on simultaneously failing '{up_id}'.")

        if len(all_res_ids) > 1:
            capacity_limits.append(
                f"Simultaneous failure of {len(all_res_ids)} critical resources exhausts standard operational buffers."
            )

        now = datetime.utcnow()
        record.shared_dependencies_identified = shared_deps
        record.combined_affected_capabilities = sorted(list(combined_caps))
        record.combined_affected_responsibilities = sorted(list(combined_resps))
        record.available_fallback_arrangements = available_fallbacks
        record.non_independent_fallbacks = non_independent_fallbacks
        record.capacity_limitations = capacity_limits
        record.compound_severity = ImpactSeverity.CRITICAL if len(combined_caps) >= 2 else ImpactSeverity.HIGH
        record.evaluated_at = now
        record.evaluated_by = user_id
        record.updated_at = now

        return self.repo.save_compound_scenario(record)


_compound_service: Optional[GovernanceCompoundDisruptionService] = None


def get_governance_compound_disruption_service() -> GovernanceCompoundDisruptionService:
    global _compound_service
    if _compound_service is None:
        _compound_service = GovernanceCompoundDisruptionService(
            get_governance_disruption_impact_repository()
        )
    return _compound_service

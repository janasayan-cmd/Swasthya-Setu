"""Phase 86: Clinical Safety Governance Resilience Resource Dependency Repository.

Thread-safe in-memory persistence for:
- Critical resource inventory
- Capability-to-resource dependency mappings
- Resource availability observations
- Alternative resource and fallback arrangements
- Capacity requirements
- SPOF/dependency graph analyses
- Resource dependency gaps
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_resource_common import (
    DependencyMappingStatus,
    FallbackReadinessOutcome,
    ResourceAvailabilityStatus,
    ResourceCategory,
    ResourceCriticality,
    ResourceGapCategory,
    ResourceGapStatus,
    ResourceLifecycleStatus,
)
from app.schemas.governance_resource_inventory import CriticalResourceRecord
from app.schemas.governance_resource_dependency_mapping import CapabilityResourceDependencyRecord
from app.schemas.governance_resource_availability import ResourceAvailabilityObservationRecord
from app.schemas.governance_resource_alternative import AlternativeResourceRecord
from app.schemas.governance_resource_capacity import CapacityRequirementRecord
from app.schemas.governance_resource_spof_analysis import DependencyGraphAnalysisRecord
from app.schemas.governance_resource_gap import ResourceDependencyGapRecord


class GovernanceResourceDependencyRepository:
    """Thread-safe in-memory repository for Phase 86 resource dependency data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._resources: Dict[str, CriticalResourceRecord] = {}
        self._dependency_mappings: Dict[str, CapabilityResourceDependencyRecord] = {}
        self._availability_observations: Dict[str, ResourceAvailabilityObservationRecord] = {}
        self._alternatives: Dict[str, AlternativeResourceRecord] = {}
        self._capacity_requirements: Dict[str, CapacityRequirementRecord] = {}
        self._graph_analyses: Dict[str, DependencyGraphAnalysisRecord] = {}
        self._resource_gaps: Dict[str, ResourceDependencyGapRecord] = {}

    def clear(self) -> None:
        with self._lock:
            self._resources.clear()
            self._dependency_mappings.clear()
            self._availability_observations.clear()
            self._alternatives.clear()
            self._capacity_requirements.clear()
            self._graph_analyses.clear()
            self._resource_gaps.clear()

    # =========================================================================
    # 1. Resources
    # =========================================================================

    def save_resource(self, record: CriticalResourceRecord) -> CriticalResourceRecord:
        with self._lock:
            self._resources[record.resource_id] = record
            return record

    def get_resource(self, resource_id: str, tenant_id: str) -> Optional[CriticalResourceRecord]:
        with self._lock:
            item = self._resources.get(resource_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_resources(
        self,
        tenant_id: str,
        category: Optional[ResourceCategory] = None,
        criticality: Optional[ResourceCriticality] = None,
        lifecycle_status: Optional[ResourceLifecycleStatus] = None,
    ) -> List[CriticalResourceRecord]:
        with self._lock:
            items = [r for r in self._resources.values() if r.tenant_id == tenant_id]
            if category:
                items = [r for r in items if r.category == category]
            if criticality:
                items = [r for r in items if r.criticality == criticality]
            if lifecycle_status:
                items = [r for r in items if r.lifecycle_status == lifecycle_status]
            return sorted(items, key=lambda x: x.created_at, reverse=True)

    # =========================================================================
    # 2. Dependency Mappings
    # =========================================================================

    def save_dependency_mapping(self, record: CapabilityResourceDependencyRecord) -> CapabilityResourceDependencyRecord:
        with self._lock:
            self._dependency_mappings[record.dependency_id] = record
            return record

    def get_dependency_mapping(self, dependency_id: str, tenant_id: str) -> Optional[CapabilityResourceDependencyRecord]:
        with self._lock:
            item = self._dependency_mappings.get(dependency_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_dependency_mappings(
        self,
        tenant_id: str,
        resource_id: Optional[str] = None,
        capability_ref: Optional[str] = None,
        status: Optional[DependencyMappingStatus] = None,
    ) -> List[CapabilityResourceDependencyRecord]:
        with self._lock:
            items = [d for d in self._dependency_mappings.values() if d.tenant_id == tenant_id]
            if resource_id:
                items = [d for d in items if d.resource_id == resource_id]
            if capability_ref:
                items = [d for d in items if d.governance_capability_ref == capability_ref]
            if status:
                items = [d for d in items if d.status == status]
            return sorted(items, key=lambda x: x.created_at, reverse=True)

    # =========================================================================
    # 3. Availability Observations
    # =========================================================================

    def save_observation(self, record: ResourceAvailabilityObservationRecord) -> ResourceAvailabilityObservationRecord:
        with self._lock:
            self._availability_observations[record.observation_id] = record
            return record

    def get_observation(self, observation_id: str, tenant_id: str) -> Optional[ResourceAvailabilityObservationRecord]:
        with self._lock:
            item = self._availability_observations.get(observation_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_observations(
        self,
        tenant_id: str,
        resource_id: Optional[str] = None,
    ) -> List[ResourceAvailabilityObservationRecord]:
        with self._lock:
            items = [o for o in self._availability_observations.values() if o.tenant_id == tenant_id]
            if resource_id:
                items = [o for o in items if o.resource_id == resource_id]
            return sorted(items, key=lambda x: x.observation_timestamp, reverse=True)

    def get_latest_observation(self, resource_id: str, tenant_id: str) -> Optional[ResourceAvailabilityObservationRecord]:
        with self._lock:
            observations = [
                o for o in self._availability_observations.values()
                if o.tenant_id == tenant_id and o.resource_id == resource_id
            ]
            if not observations:
                return None
            return max(observations, key=lambda x: x.observation_timestamp)

    # =========================================================================
    # 4. Alternative Resources
    # =========================================================================

    def save_alternative(self, record: AlternativeResourceRecord) -> AlternativeResourceRecord:
        with self._lock:
            self._alternatives[record.alternative_id] = record
            return record

    def get_alternative(self, alternative_id: str, tenant_id: str) -> Optional[AlternativeResourceRecord]:
        with self._lock:
            item = self._alternatives.get(alternative_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_alternatives_for_resource(
        self, primary_resource_id: str, tenant_id: str
    ) -> List[AlternativeResourceRecord]:
        with self._lock:
            return [
                a for a in self._alternatives.values()
                if a.tenant_id == tenant_id and a.primary_resource_id == primary_resource_id
            ]

    def list_alternatives(self, tenant_id: str) -> List[AlternativeResourceRecord]:
        with self._lock:
            return [a for a in self._alternatives.values() if a.tenant_id == tenant_id]

    # =========================================================================
    # 5. Capacity Requirements
    # =========================================================================

    def save_capacity_requirement(self, record: CapacityRequirementRecord) -> CapacityRequirementRecord:
        with self._lock:
            self._capacity_requirements[record.requirement_id] = record
            return record

    def get_capacity_requirement(self, requirement_id: str, tenant_id: str) -> Optional[CapacityRequirementRecord]:
        with self._lock:
            item = self._capacity_requirements.get(requirement_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_capacity_requirements(
        self,
        tenant_id: str,
        resource_id: Optional[str] = None,
        capability_ref: Optional[str] = None,
    ) -> List[CapacityRequirementRecord]:
        with self._lock:
            items = [c for c in self._capacity_requirements.values() if c.tenant_id == tenant_id]
            if resource_id:
                items = [c for c in items if c.resource_id == resource_id]
            if capability_ref:
                items = [c for c in items if c.governance_capability_ref == capability_ref]
            return items

    # =========================================================================
    # 6. Graph Analyses
    # =========================================================================

    def save_graph_analysis(self, record: DependencyGraphAnalysisRecord) -> DependencyGraphAnalysisRecord:
        with self._lock:
            self._graph_analyses[record.analysis_id] = record
            return record

    def get_graph_analysis(self, analysis_id: str, tenant_id: str) -> Optional[DependencyGraphAnalysisRecord]:
        with self._lock:
            item = self._graph_analyses.get(analysis_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_graph_analyses(self, tenant_id: str) -> List[DependencyGraphAnalysisRecord]:
        with self._lock:
            items = [g for g in self._graph_analyses.values() if g.tenant_id == tenant_id]
            return sorted(items, key=lambda x: x.analyzed_at, reverse=True)

    # =========================================================================
    # 7. Resource Gaps
    # =========================================================================

    def save_resource_gap(self, record: ResourceDependencyGapRecord) -> ResourceDependencyGapRecord:
        with self._lock:
            self._resource_gaps[record.gap_id] = record
            return record

    def get_resource_gap(self, gap_id: str, tenant_id: str) -> Optional[ResourceDependencyGapRecord]:
        with self._lock:
            item = self._resource_gaps.get(gap_id)
            if item and item.tenant_id == tenant_id:
                return item
            return None

    def list_resource_gaps(
        self,
        tenant_id: str,
        status: Optional[ResourceGapStatus] = None,
        category: Optional[ResourceGapCategory] = None,
        resource_id: Optional[str] = None,
    ) -> List[ResourceDependencyGapRecord]:
        with self._lock:
            items = [g for g in self._resource_gaps.values() if g.tenant_id == tenant_id]
            if status:
                items = [g for g in items if g.status == status]
            if category:
                items = [g for g in items if g.category == category]
            if resource_id:
                items = [g for g in items if g.resource_id == resource_id]
            return sorted(items, key=lambda x: x.identified_at, reverse=True)


_resource_dependency_repository_instance: Optional[GovernanceResourceDependencyRepository] = None


def get_governance_resource_dependency_repository() -> GovernanceResourceDependencyRepository:
    global _resource_dependency_repository_instance
    if _resource_dependency_repository_instance is None:
        _resource_dependency_repository_instance = GovernanceResourceDependencyRepository()
    return _resource_dependency_repository_instance

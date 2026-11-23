"""Phase 86: Resource Dependency Reporting Schemas.

Provides structured executive summaries, concentration analysis,
fallback readiness, and availability reports.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
)


class ResourceCoverageSummaryReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_critical_resources: int
    category_distribution: Dict[str, int]
    resources_with_verified_availability: int
    resources_with_unknown_or_stale_availability: int
    resources_with_fallback_verified: int
    resources_without_fallback: int
    total_dependencies_mapped: int
    open_resource_gaps_count: int
    spof_findings_count: int
    overall_coverage_health_pct: float
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class DependencyConcentrationReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_spof_findings: int
    critical_spof_count: int
    high_spof_count: int
    shared_resource_count: int
    capabilities_at_risk_count: int
    top_spof_resource_ids: List[str] = Field(default_factory=list)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class FallbackReadinessReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_alternatives_documented: int
    ready_verified_count: int
    conditionally_ready_count: int
    not_ready_count: int
    not_assessed_count: int
    insufficient_evidence_count: int
    expired_count: int
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class ResourceAvailabilityStatusReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_resources: int
    available_verified_count: int
    available_unverified_count: int
    degraded_count: int
    unavailable_count: int
    unknown_count: int
    stale_count: int
    conflicting_count: int
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class ResourceGapsSummaryReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_gaps: int
    open_gaps: int
    escalated_gaps: int
    resolved_gaps: int
    critical_gaps: int
    high_gaps: int
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)

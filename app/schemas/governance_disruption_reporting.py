"""Phase 87: Disruption Impact Reporting Schemas.

Defines executive reports for disruption impact, cascading dependencies,
compound disruptions, fallback comparisons, and overall assessment coverage.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_disruption_common import (
    MANDATORY_DISRUPTION_IMPACT_DISCLAIMER,
)


class DisruptionImpactSummaryReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_scenarios_registered: int
    approved_scenarios_count: int
    total_assessments_completed: int
    critical_impact_assessments_count: int
    high_impact_assessments_count: int
    assessments_exceeding_mtpd: int
    open_remediation_follow_ups: int
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class CascadingDependenciesReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_cascading_analyses: int
    total_propagation_paths_identified: int
    max_propagation_depth_recorded: int
    shared_upstream_bottleneck_resources: List[str] = Field(default_factory=list)
    common_provider_dependency_count: int
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class CompoundDisruptionsReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_compound_scenarios: int
    compound_scenarios_evaluated: int
    scenarios_with_non_independent_fallbacks: int
    scenarios_with_personnel_overlap: int
    critical_compound_findings_count: int
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class FallbackComparisonReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_resources_compared: int
    resources_with_verified_mitigation: int
    resources_with_partial_mitigation: int
    resources_lacking_effective_fallback: int
    stale_evidence_warnings_count: int
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class ImpactAssessmentCoverageReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_critical_capabilities: int
    capabilities_with_active_assessment: int
    capabilities_coverage_pct: float
    assessments_requiring_reassessment: int
    overdue_human_reviews_count: int
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)

"""Phase 87: Fallback Effectiveness Comparison Schemas.

Defines schemas for comparing expected governance impact under different fallback conditions:
no fallback, unverified fallback, verified fallback, conditionally ready, and stale evidence.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_disruption_common import (
    MANDATORY_DISRUPTION_IMPACT_DISCLAIMER,
    ImpactSeverity,
)


class FallbackComparisonItem(BaseModel):
    fallback_id: Optional[str] = None
    alternative_resource_id: Optional[str] = None
    alternative_resource_name: Optional[str] = None
    readiness_tier: str  # NO_FALLBACK, UNVERIFIED_FALLBACK, READY_VERIFIED, CONDITIONALLY_READY, STALE_EVIDENCE
    estimated_impact_severity: ImpactSeverity
    mitigated_capabilities: List[str] = Field(default_factory=list)
    unmitigated_capabilities: List[str] = Field(default_factory=list)
    shares_upstream_dependency: bool = False
    evidence_quality: str  # EVIDENCE_BACKED, PARTIALLY_EVIDENCED, ASSUMPTION_BASED, UNKNOWN
    notes: str


class FallbackComparisonRecord(BaseModel):
    comparison_id: str
    tenant_id: str
    assessment_id: str
    resource_id: str
    baseline_severity_without_fallback: ImpactSeverity
    comparison_items: List[FallbackComparisonItem] = Field(default_factory=list)
    optimal_fallback_id: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    compared_by: str
    compared_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class RunFallbackComparisonRequest(BaseModel):
    resource_id: str
    notes: Optional[str] = None

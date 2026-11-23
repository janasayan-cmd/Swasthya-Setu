"""Phase 87: Cascading Failure and Cross-Dependency Propagation Schemas.

Defines schemas for multi-level dependency propagation analysis, shared upstream
dependency detection, and explainable cascading failure identification.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_disruption_common import (
    MANDATORY_DISRUPTION_IMPACT_DISCLAIMER,
    ImpactCertainty,
    ImpactSeverity,
)


class PropagationNode(BaseModel):
    node_id: str
    node_type: str  # RESOURCE, CAPABILITY, RESPONSIBILITY, FACILITY, PROVIDER
    name: str
    depth: int
    parent_node_id: Optional[str] = None
    dependency_relationship: str


class PropagationPath(BaseModel):
    path_id: str
    root_disruption_id: str
    terminal_node_id: str
    nodes: List[PropagationNode] = Field(default_factory=list)
    total_hops: int
    propagation_type: str  # DIRECT, MULTI_LEVEL, SHARED_UPSTREAM, COMMON_PROVIDER, COMMON_INFRASTRUCTURE


class CascadingFailureFinding(BaseModel):
    finding_id: str
    initial_disruption_source: str
    propagation_path: List[str] = Field(default_factory=list)
    affected_dependency_nodes: List[str] = Field(default_factory=list)
    affected_capabilities: List[str] = Field(default_factory=list)
    affected_responsibilities: List[str] = Field(default_factory=list)
    potential_impact: str
    severity: ImpactSeverity = ImpactSeverity.HIGH
    certainty: ImpactCertainty = ImpactCertainty.POTENTIAL
    detection_rule_version: str = "1.0"
    shared_upstream_dependency_id: Optional[str] = None
    common_provider_ref: Optional[str] = None
    supporting_evidence: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    explanation: str


class CascadingAnalysisRecord(BaseModel):
    analysis_id: str
    tenant_id: str
    assessment_id: Optional[str] = None
    scenario_id: Optional[str] = None
    total_paths_identified: int = 0
    max_depth_traversed: int = 0
    cascading_findings: List[CascadingFailureFinding] = Field(default_factory=list)
    propagation_paths: List[PropagationPath] = Field(default_factory=list)
    shared_upstream_resources: List[Dict[str, object]] = Field(default_factory=list)
    common_provider_risks: List[Dict[str, object]] = Field(default_factory=list)
    analyzed_by: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class RunCascadingAnalysisRequest(BaseModel):
    assessment_id: Optional[str] = None
    scenario_id: Optional[str] = None
    max_depth: int = Field(default=4, ge=1, le=10)
    include_personnel_interactions: bool = True

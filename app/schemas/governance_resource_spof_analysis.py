"""Phase 86: Single-Point-of-Failure and Dependency Concentration Analysis Schemas.

Defines structures for SPOF finding records, dependency graph analysis,
and concentration risk assessments.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
    SPOFSeverity,
)


class SPOFFindingRecord(BaseModel):
    finding_id: str
    tenant_id: str
    finding_type: str  # e.g. SINGLE_RESOURCE_DEPENDENCY, SHARED_UPSTREAM, PROVIDER_CONCENTRATION
    affected_capability_refs: List[str] = Field(default_factory=list)
    affected_resource_refs: List[str] = Field(default_factory=list)
    dependency_path: List[str] = Field(default_factory=list)
    detection_rule: str
    detection_rule_version: str = "1.0"
    severity: SPOFSeverity = SPOFSeverity.HIGH
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    evidence_refs: List[str] = Field(default_factory=list)
    confidence_level: str = "HIGH"  # HIGH, MEDIUM, LOW
    review_status: str = "OPEN"  # OPEN, ACKNOWLEDGED, REMEDIATION_IN_PROGRESS, CLOSED
    recommended_follow_up: Optional[str] = None
    reviewed_by: Optional[str] = None
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class DependencyGraphAnalysisRecord(BaseModel):
    analysis_id: str
    tenant_id: str
    analysis_scope: str = "ORGANIZATION"
    total_resources_analyzed: int = 0
    total_dependencies_analyzed: int = 0
    spof_findings: List[SPOFFindingRecord] = Field(default_factory=list)
    circular_dependencies_detected: List[List[str]] = Field(default_factory=list)
    shared_dependencies: List[dict] = Field(default_factory=list)
    critical_path_resource_ids: List[str] = Field(default_factory=list)
    capabilities_without_resource_mapping: List[str] = Field(default_factory=list)
    resources_without_verified_availability: List[str] = Field(default_factory=list)
    resources_without_fallback: List[str] = Field(default_factory=list)
    analyzed_by: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    advisory_notes: List[str] = Field(default_factory=list)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class RunDependencyGraphAnalysisRequest(BaseModel):
    analysis_scope: str = "ORGANIZATION"
    include_indirect_dependencies: bool = True
    min_severity: SPOFSeverity = SPOFSeverity.MEDIUM

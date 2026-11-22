"""Phase 83: Knowledge Reporting and Maintenance Schemas.

Supports executive and management reporting on knowledge health, distribution,
acknowledgements, learning gaps, recommendations, and maintenance scans.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_knowledge import (
    KnowledgeCategory,
    KnowledgeLifecycleState,
    MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER,
)


class ResilienceKnowledgeSearchRequest(BaseModel):
    query: Optional[str] = None
    categories: Optional[List[KnowledgeCategory]] = None
    states: Optional[List[KnowledgeLifecycleState]] = None
    tags: Optional[List[str]] = None
    owner_id: Optional[str] = None
    limit: int = 50
    offset: int = 0


class KnowledgeInventoryReport(BaseModel):
    total_knowledge_records: int
    by_category: Dict[str, int]
    by_state: Dict[str, int]
    by_confidentiality: Dict[str, int]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class DistributionComplianceReport(BaseModel):
    total_campaigns: int
    active_campaigns: int
    total_acknowledgements_required: int
    total_acknowledged: int
    acknowledgement_rate_percent: float
    overdue_acknowledgements: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class ApplicationEvidenceReport(BaseModel):
    total_evidence_records: int
    verified_evidence_records: int
    rejected_evidence_records: int
    by_operational_context: Dict[str, int]
    average_effectiveness_rating: float
    linked_phase55_assessments: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class LearningGapsReport(BaseModel):
    total_gaps_identified: int
    open_gaps: int
    by_gap_type: Dict[str, int]
    by_severity: Dict[str, int]
    capa_referred_gaps: int
    resolved_gaps: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class CapabilityDevelopmentReport(BaseModel):
    total_recommendations: int
    by_activity_type: Dict[str, int]
    by_status: Dict[str, int]
    completed_activities: int
    scheduled_activities: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class KnowledgeSuccessionReport(BaseModel):
    total_transfers: int
    verified_transfers: int
    pending_transfers: int
    rejected_transfers: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class ResiliencePreparednessMaturityReport(BaseModel):
    knowledge_base_maturity_score: float
    published_guidance_count: int
    compliance_score_percent: float
    gap_resolution_rate_percent: float
    active_conflicts_count: int
    overall_resilience_posture: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class RoutineMaintenanceScanResult(BaseModel):
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    outdated_knowledge_ids: List[str] = Field(default_factory=list)
    pending_review_knowledge_ids: List[str] = Field(default_factory=list)
    unresolved_conflict_ids: List[str] = Field(default_factory=list)
    unaddressed_gap_ids: List[str] = Field(default_factory=list)
    low_acknowledgement_campaign_ids: List[str] = Field(default_factory=list)
    total_anomalies_detected: int
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)

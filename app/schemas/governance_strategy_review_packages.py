"""Phase 79: Strategic Review Package Schemas.

Defines schemas and models for:
- Packaging consolidated strategic execution oversight dossiers
- Referring dossiers to Phase 72 Management Review
- Scheduled background scan job results
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class StrategicReviewPackageRecord(BaseModel):
    """Authoritative dossier for strategic review by executive governance leaders."""
    model_config = ConfigDict(extra="forbid")

    package_id: str
    tenant_id: str
    title: str
    reporting_period: str
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    included_roadmap_ids: List[str] = Field(default_factory=list)
    executive_summary: str
    monitored_status_summary: Dict[str, Any] = Field(default_factory=dict)
    cross_roadmap_dependency_summary: Dict[str, Any] = Field(default_factory=dict)
    alignment_findings: List[Dict[str, Any]] = Field(default_factory=list)
    invalidated_assumptions: List[Dict[str, Any]] = Field(default_factory=list)
    active_signals: List[Dict[str, Any]] = Field(default_factory=list)
    open_exceptions: List[Dict[str, Any]] = Field(default_factory=list)
    adaptation_proposals: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_coverage: float = 1.0
    known_limitations: str = ""
    prepared_by: str
    phase_72_referral_reference: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    created_at: str


class GenerateReviewPackageRequest(BaseModel):
    """Request to generate a strategic execution review package."""
    model_config = ConfigDict(extra="forbid")

    title: str
    reporting_period: str
    organizational_scope: Optional[Dict[str, Any]] = None
    included_roadmap_ids: List[str]
    executive_summary: str
    known_limitations: Optional[str] = ""


class ReferReviewPackageToPhase72Request(BaseModel):
    """Request to formally refer review package to Phase 72 Management Review."""
    model_config = ConfigDict(extra="forbid")

    agenda_item_title: str
    phase_72_meeting_id: Optional[str] = None
    referral_notes: Optional[str] = None


class ExecutionRoutineScanJobResult(BaseModel):
    """Result of an idempotent background strategic execution maintenance scan."""
    model_config = ConfigDict(extra="forbid")

    scanned_roadmaps: int
    scanned_monitored_items: int
    stale_evidence_flagged: int
    dependency_conflicts_flagged: int
    invalidated_assumptions_flagged: int
    active_signals_flagged: int
    status: str

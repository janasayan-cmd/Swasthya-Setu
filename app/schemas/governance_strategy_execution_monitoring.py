"""Phase 79: Strategic Execution Monitoring Schemas.

Defines schemas and models for:
- Monitoring execution across approved Phase 78 strategic roadmaps, objectives, and milestones
- Tracking synchronization status against Phase 75, Phase 73, Phase 74, Phase 76, Phase 77
- Distinguishing source-reported status from verified evidence and analytical observations
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


CLINICAL_SAFETY_MONITORING_DISCLAIMER = (
    "Strategic execution monitoring and scenario projections are advisory oversight and coordination tools "
    "and do NOT constitute proof of clinical safety, regulatory compliance, or actual clinical outcomes. "
    "Phase 79 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, 73, 74, 75, 76, 77, or 78."
)


class MonitoredWorkflowType(str, Enum):
    """Upstream and authoritative governance workflow types monitored in Phase 79."""
    PHASE_78_ROADMAP = "PHASE_78_ROADMAP"
    PHASE_78_OBJECTIVE = "PHASE_78_OBJECTIVE"
    PHASE_78_MILESTONE = "PHASE_78_MILESTONE"
    PHASE_78_CAPABILITY_TARGET = "PHASE_78_CAPABILITY_TARGET"
    PHASE_75_PORTFOLIO = "PHASE_75_PORTFOLIO"
    PHASE_73_IMPLEMENTATION = "PHASE_73_IMPLEMENTATION"
    PHASE_74_ADOPTION = "PHASE_74_ADOPTION"
    PHASE_76_BENEFIT = "PHASE_76_BENEFIT"
    PHASE_77_MATURITY = "PHASE_77_MATURITY"


class MonitoringHealthStatus(str, Enum):
    """Monitored execution health status."""
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    OFF_TRACK = "OFF_TRACK"
    BLOCKED = "BLOCKED"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    UNAVAILABLE = "UNAVAILABLE"


class StrategicExecutionMonitoringRecord(BaseModel):
    """Authoritative record for an item monitored under strategic execution oversight."""
    model_config = ConfigDict(extra="forbid")

    monitoring_id: str
    tenant_id: str
    roadmap_id: str
    monitored_item_type: MonitoredWorkflowType
    monitored_item_id: str
    source_status: str
    health_status: MonitoringHealthStatus
    evidence_freshness_timestamp: str
    is_stale: bool = False
    analytical_observation: str = ""
    detected_issue_count: int = 0
    last_synchronized_at: str
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER


class CreateExecutionMonitoringRequest(BaseModel):
    """Request to initiate strategic execution monitoring for a roadmap item."""
    model_config = ConfigDict(extra="forbid")

    roadmap_id: str
    monitored_item_type: MonitoredWorkflowType
    monitored_item_id: str
    source_status: str
    health_status: MonitoringHealthStatus = MonitoringHealthStatus.ON_TRACK
    analytical_observation: Optional[str] = ""
    evidence_freshness_timestamp: Optional[str] = None


class ReconcileExecutionMonitoringRequest(BaseModel):
    """Request to update synchronized status for a monitored item."""
    model_config = ConfigDict(extra="forbid")

    source_status: str
    health_status: MonitoringHealthStatus
    analytical_observation: Optional[str] = None
    detected_issue_count: Optional[int] = 0
    evidence_freshness_timestamp: Optional[str] = None

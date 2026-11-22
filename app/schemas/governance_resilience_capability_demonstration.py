"""Phase 84: Practical Capability Demonstration Schemas.

Supports recording and evaluating practical capability demonstrations (tabletops,
simulated disruptions, operational handoffs, recovery coordination) linked to Phase 80/81.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class DemonstrationMethod(str, Enum):
    SCENARIO_BASED_EXERCISE = "SCENARIO_BASED_EXERCISE"
    TABLETOP_EXERCISE = "TABLETOP_EXERCISE"
    SIMULATED_GOVERNANCE_DISRUPTION = "SIMULATED_GOVERNANCE_DISRUPTION"
    RECOVERY_COORDINATION_DEMO = "RECOVERY_COORDINATION_DEMO"
    DELEGATED_AUTHORITY_SCENARIO = "DELEGATED_AUTHORITY_SCENARIO"
    DECISION_CONTINUITY_SIMULATION = "DECISION_CONTINUITY_SIMULATION"
    EVIDENCE_RECONCILIATION_EXERCISE = "EVIDENCE_RECONCILIATION_EXERCISE"
    DEPENDENCY_DISRUPTION_SCENARIO = "DEPENDENCY_DISRUPTION_SCENARIO"
    OPERATIONAL_HANDOFF_DEMO = "OPERATIONAL_HANDOFF_DEMO"
    STRUCTURED_ASSESSOR_OBSERVATION = "STRUCTURED_ASSESSOR_OBSERVATION"


class DemonstrationOutcome(str, Enum):
    SUCCESSFUL = "SUCCESSFUL"
    PARTIALLY_SUCCESSFUL = "PARTIALLY_SUCCESSFUL"
    UNSUCCESSFUL = "UNSUCCESSFUL"
    INCONCLUSIVE = "INCONCLUSIVE"


class DemonstrationReviewStatus(str, Enum):
    RECORDED = "RECORDED"
    REVIEWED = "REVIEWED"
    DISPUTED = "DISPUTED"


class CapabilityDemonstrationRecord(BaseModel):
    demonstration_id: str
    tenant_id: str
    capability_id: str
    assessment_id: Optional[str] = None
    scenario_reference: Optional[str] = None
    participant_user_id: Optional[str] = None
    team_reference: Optional[str] = None
    method: DemonstrationMethod
    expected_behavior: str
    observed_behavior: str
    evidence_references: List[str] = Field(default_factory=list)
    outcome: DemonstrationOutcome = DemonstrationOutcome.INCONCLUSIVE
    review_status: DemonstrationReviewStatus = DemonstrationReviewStatus.RECORDED
    assessor_observations: Optional[str] = None
    limitations: Optional[str] = None
    reassessment_recommended: bool = False
    recorded_by: str
    reviewed_by: Optional[str] = None
    demonstrated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class RecordDemonstrationRequest(BaseModel):
    capability_id: str
    assessment_id: Optional[str] = None
    scenario_reference: Optional[str] = None
    participant_user_id: Optional[str] = None
    team_reference: Optional[str] = None
    method: DemonstrationMethod
    expected_behavior: str
    observed_behavior: str
    evidence_references: List[str] = Field(default_factory=list)
    outcome: DemonstrationOutcome
    assessor_observations: Optional[str] = None
    limitations: Optional[str] = None
    reassessment_recommended: bool = False


class ReviewDemonstrationRequest(BaseModel):
    review_status: DemonstrationReviewStatus
    reviewer_notes: Optional[str] = None

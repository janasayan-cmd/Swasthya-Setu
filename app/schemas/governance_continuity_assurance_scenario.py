"""Phase 81: Scenario Coverage and Stress Validation Schemas.

Supports advisory stress testing and scenario coverage analysis across 12
predefined disruption scenarios without triggering actual production disruptions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class DisruptionScenarioType(str, Enum):
    PRIMARY_SYSTEM_OUTAGE = "PRIMARY_SYSTEM_OUTAGE"
    IDENTITY_AUTHENTICATION_OUTAGE = "IDENTITY_AUTHENTICATION_OUTAGE"
    NOTIFICATION_SERVICE_OUTAGE = "NOTIFICATION_SERVICE_OUTAGE"
    LOSS_OF_CRITICAL_OWNER = "LOSS_OF_CRITICAL_OWNER"
    MULTIPLE_PERSONNEL_UNAVAILABLE = "MULTIPLE_PERSONNEL_UNAVAILABLE"
    EXTERNAL_INTEGRATION_FAILURE = "EXTERNAL_INTEGRATION_FAILURE"
    FACILITY_DISRUPTION = "FACILITY_DISRUPTION"
    PROLONGED_COMMUNICATION_FAILURE = "PROLONGED_COMMUNICATION_FAILURE"
    LOSS_OF_EVIDENCE_ACCESS = "LOSS_OF_EVIDENCE_ACCESS"
    DATA_INTEGRITY_CONCERN = "DATA_INTEGRITY_CONCERN"
    SIMULTANEOUS_MULTI_CAPABILITY_DISRUPTION = "SIMULTANEOUS_MULTI_CAPABILITY_DISRUPTION"
    EXTENDED_DISRUPTION_BEYOND_TARGETS = "EXTENDED_DISRUPTION_BEYOND_TARGETS"


class ScenarioEvaluationOutcome(str, Enum):
    ADEQUATELY_ADDRESSED = "ADEQUATELY_ADDRESSED"
    PARTIALLY_ADDRESSED = "PARTIALLY_ADDRESSED"
    VULNERABILITY_IDENTIFIED = "VULNERABILITY_IDENTIFIED"
    UNTESTED = "UNTESTED"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class CreateScenarioAssessmentRequest(BaseModel):
    scenario_type: DisruptionScenarioType
    scenario_title: str
    scenario_description: str
    severity_level: str = "HIGH"  # CRITICAL, HIGH, MEDIUM, LOW
    affected_capability_ids: List[str] = Field(default_factory=list)
    required_dependencies: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    expected_continuity_response: str
    expected_recovery_sequence: List[str] = Field(default_factory=list)


class EvaluateScenarioRequest(BaseModel):
    evaluation_outcome: ScenarioEvaluationOutcome
    actual_exercise_ref: Optional[str] = None
    identified_weaknesses: List[str] = Field(default_factory=list)
    recommended_mitigations: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None


class ContinuityScenarioAssessmentRecord(BaseModel):
    scenario_id: str
    scenario_type: DisruptionScenarioType
    scenario_title: str
    scenario_description: str
    severity_level: str
    affected_capability_ids: List[str] = Field(default_factory=list)
    required_dependencies: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    expected_continuity_response: str
    expected_recovery_sequence: List[str] = Field(default_factory=list)
    evaluation_outcome: ScenarioEvaluationOutcome = ScenarioEvaluationOutcome.UNTESTED
    actual_exercise_ref: Optional[str] = None
    identified_weaknesses: List[str] = Field(default_factory=list)
    recommended_mitigations: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None
    is_advisory_only: bool = True
    created_by: str
    created_at: datetime
    evaluated_by: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER

"""Phase 77: Systemic Governance Gaps Schemas.

Defines schemas for identifying, classifying, human confirming,
and routing systemic governance capability gaps.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    MaturityDimensionEnum,
)


class GapClassification(str, Enum):
    """Classification of systemic governance weaknesses."""
    CAPABILITY_DEFICIT = "CAPABILITY_DEFICIT"
    COVERAGE_DEFICIT = "COVERAGE_DEFICIT"
    RELIABILITY_DRIFT = "RELIABILITY_DRIFT"
    EVIDENCE_DEFICIENCY = "EVIDENCE_DEFICIENCY"
    CONTROL_ABSENCE = "CONTROL_ABSENCE"


class GapStatus(str, Enum):
    """Lifecycle status of a systemic governance gap."""
    POTENTIAL_GAP = "POTENTIAL_GAP"
    CONFIRMED_GAP = "CONFIRMED_GAP"
    ADDRESSED_IN_PLAN = "ADDRESSED_IN_PLAN"
    RESOLVED = "RESOLVED"
    ACCEPTED_EXCEPTION = "ACCEPTED_EXCEPTION"


class SystemicGovernanceGapRecord(BaseModel):
    """Authoritative record for an identified systemic governance gap."""
    model_config = ConfigDict(extra="forbid")

    gap_id: str
    tenant_id: str
    title: str
    description: str
    classification: GapClassification
    status: GapStatus
    impacted_dimensions: List[MaturityDimensionEnum] = Field(default_factory=list)
    impacted_scopes: List[Dict[str, Any]] = Field(default_factory=list)
    originating_assessment_ids: List[str] = Field(default_factory=list)
    identified_by: str
    identified_at: str
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    confirmation_notes: Optional[str] = None
    improvement_plan_id: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class IdentifyGapRequest(BaseModel):
    """Request to identify a potential systemic governance gap."""
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    classification: GapClassification
    impacted_dimensions: List[MaturityDimensionEnum]
    impacted_scopes: Optional[List[Dict[str, Any]]] = None
    originating_assessment_ids: Optional[List[str]] = None


class ConfirmGapRequest(BaseModel):
    """Request to human-confirm an identified systemic gap."""
    model_config = ConfigDict(extra="forbid")

    confirmation_notes: str


class RouteGapRequest(BaseModel):
    """Request to link a gap to an improvement plan."""
    model_config = ConfigDict(extra="forbid")

    improvement_plan_id: str
    routing_notes: Optional[str] = None

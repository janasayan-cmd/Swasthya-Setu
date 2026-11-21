"""Phase 79: Strategic Assumption Monitoring Schemas.

Defines schemas and models for:
- Tracking and validating assumptions underpinning approved strategic roadmaps
- Distinguishing unverified assumptions from invalidated assumptions
- Generating review signals when critical assumptions change
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class AssumptionCategory(str, Enum):
    """Category of operational or strategic assumption."""
    WORKFORCE_AVAILABILITY = "WORKFORCE_AVAILABILITY"
    ORGANIZATIONAL_CAPACITY = "ORGANIZATIONAL_CAPACITY"
    TECHNOLOGY_READINESS = "TECHNOLOGY_READINESS"
    INTEGRATION_AVAILABILITY = "INTEGRATION_AVAILABILITY"
    FUNDING_ASSUMPTION = "FUNDING_ASSUMPTION"
    OPERATIONAL_READINESS = "OPERATIONAL_READINESS"
    TRAINING_CAPACITY = "TRAINING_CAPACITY"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"


class AssumptionStatus(str, Enum):
    """Lifecycle status of a strategic assumption."""
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VALIDATED = "VALIDATED"
    PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class StrategicAssumptionRecord(BaseModel):
    """Authoritative record for an assumption supporting an approved roadmap."""
    model_config = ConfigDict(extra="forbid")

    assumption_id: str
    tenant_id: str
    roadmap_id: str
    category: AssumptionCategory
    description: str
    source_rationale: str
    owner_id: str
    validation_method: str
    last_validated_date: Optional[str] = None
    expected_review_date: str
    status: AssumptionStatus
    impact_if_invalidated: str
    supporting_evidence_reference: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    created_at: str
    updated_at: str


class CreateAssumptionRequest(BaseModel):
    """Request to register a strategic planning assumption."""
    model_config = ConfigDict(extra="forbid")

    roadmap_id: str
    category: AssumptionCategory
    description: str
    source_rationale: str
    owner_id: str
    validation_method: str
    expected_review_date: str
    impact_if_invalidated: str


class ValidateAssumptionRequest(BaseModel):
    """Request to record validation evidence or update status for an assumption."""
    model_config = ConfigDict(extra="forbid")

    status: AssumptionStatus
    supporting_evidence_reference: Optional[str] = None
    validation_notes: Optional[str] = None

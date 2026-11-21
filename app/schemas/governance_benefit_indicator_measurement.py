"""Phase 76: Benefit Performance Indicators and Measurement Intake Schemas.

Defines schemas and models for:
- Configurable benefit performance indicators
- Structured measurement intake and verification
- Explicit separation of duties on measurement validation
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class IndicatorType(str, Enum):
    """Supported indicator calculation formats."""
    COUNT = "COUNT"
    RATE = "RATE"
    PERCENTAGE = "PERCENTAGE"
    DURATION = "DURATION"
    FREQUENCY = "FREQUENCY"
    RATIO = "RATIO"
    THRESHOLD_CONDITION = "THRESHOLD_CONDITION"
    QUALITATIVE_ASSESSMENT = "QUALITATIVE_ASSESSMENT"


class ExpectedDirection(str, Enum):
    """Direction of improvement for the indicator."""
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    THRESHOLD_MAINTAINED = "THRESHOLD_MAINTAINED"


class IndicatorOutcome(str, Enum):
    """Result status of an evaluated performance indicator."""
    NOT_ASSESSED = "NOT_ASSESSED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BELOW_BASELINE = "BELOW_BASELINE"
    IMPROVING = "IMPROVING"
    TARGET_PARTIALLY_ACHIEVED = "TARGET_PARTIALLY_ACHIEVED"
    TARGET_ACHIEVED = "TARGET_ACHIEVED"
    TARGET_EXCEEDED = "TARGET_EXCEEDED"
    DETERIORATING = "DETERIORATING"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class MeasurementStatus(str, Enum):
    """Validation lifecycle of an observed measurement."""
    SUBMITTED = "SUBMITTED"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class BenefitIndicatorRecord(BaseModel):
    """Authoritative record for a benefit performance indicator."""
    model_config = ConfigDict(extra="forbid")

    indicator_id: str
    benefit_id: str
    tenant_id: str
    name: str
    description: str
    indicator_type: IndicatorType
    calculation_methodology: str
    unit: str
    expected_direction: ExpectedDirection
    baseline_reference: Optional[str] = None
    target_reference: Optional[str] = None
    measurement_frequency: str
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    source_system: str
    data_quality_rules: List[str] = Field(default_factory=list)
    responsible_owner_id: str
    verification_requirements: List[str] = Field(default_factory=list)
    version: int = 1
    created_by: str
    created_at: str
    updated_at: str


class CreateIndicatorRequest(BaseModel):
    """Request payload to configure a performance indicator."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    indicator_type: IndicatorType
    calculation_methodology: str = Field(..., min_length=5)
    unit: str = Field(..., min_length=1)
    expected_direction: ExpectedDirection
    baseline_reference: Optional[str] = None
    target_reference: Optional[str] = None
    measurement_frequency: str = Field(..., min_length=2)
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    source_system: str = Field(..., min_length=2)
    data_quality_rules: List[str] = Field(default_factory=list)
    responsible_owner_id: str = Field(..., min_length=2)
    verification_requirements: List[str] = Field(default_factory=list)


class AssessIndicatorRequest(BaseModel):
    """Request payload to calculate and assess an indicator outcome."""
    model_config = ConfigDict(extra="forbid")

    assessment_period: str = Field(..., min_length=2)
    observed_value: Optional[float] = None
    qualitative_state: Optional[str] = None
    supporting_evidence_refs: List[str] = Field(default_factory=list)


class IndicatorAssessmentResult(BaseModel):
    """Evaluation result for an indicator."""
    model_config = ConfigDict(extra="forbid")

    indicator_id: str
    benefit_id: str
    assessment_period: str
    outcome: IndicatorOutcome
    observed_value: Optional[float] = None
    qualitative_state: Optional[str] = None
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    calculated_at: str
    assessed_by: str


class BenefitMeasurementRecord(BaseModel):
    """Authoritative record for an observed benefit measurement intake."""
    model_config = ConfigDict(extra="forbid")

    measurement_id: str
    benefit_id: str
    indicator_id: str
    tenant_id: str
    measurement_period: str
    observed_value: Optional[float] = None
    qualitative_state: Optional[str] = None
    unit: str
    source_reference: str
    source_system: str
    collection_timestamp: str
    data_freshness_days: int = 0
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    evidence_references: List[str] = Field(default_factory=list)
    validation_status: MeasurementStatus = MeasurementStatus.SUBMITTED
    reviewer_id: Optional[str] = None
    verification_timestamp: Optional[str] = None
    validation_notes: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    created_by: str
    created_at: str
    updated_at: str


class CreateMeasurementRequest(BaseModel):
    """Request payload to submit an observed measurement."""
    model_config = ConfigDict(extra="forbid")

    indicator_id: str = Field(..., min_length=2)
    measurement_period: str = Field(..., min_length=2)
    observed_value: Optional[float] = None
    qualitative_state: Optional[str] = None
    unit: str = Field(..., min_length=1)
    source_reference: str = Field(..., min_length=2)
    source_system: str = Field(..., min_length=2)
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    evidence_references: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class ValidateMeasurementRequest(BaseModel):
    """Request payload to validate a submitted measurement."""
    model_config = ConfigDict(extra="forbid")

    validation_notes: str = Field(..., min_length=3)


class RejectMeasurementRequest(BaseModel):
    """Request payload to reject a submitted measurement."""
    model_config = ConfigDict(extra="forbid")

    rejection_reason: str = Field(..., min_length=5)

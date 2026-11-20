"""Phase 71: Analytics Configuration & Versioning Schemas.

Defines schemas for:
- Versioned analytical configuration for repeat matching, scoring, and thresholds
- Controlled configuration lifecycle (creation, approval, deprecation)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsConfigRecord(BaseModel):
    """Domain record representing an approved analytical configuration version."""

    model_config = ConfigDict(extra="ignore")

    configuration_id: str = Field(default_factory=lambda: f"gcfg-{uuid.uuid4().hex[:12]}")
    version: str = "v1.0.0"
    name: str
    description: str

    repeat_matching_rules: Dict[str, Any] = Field(
        default_factory=lambda: {
            "match_category": True,
            "match_control": True,
            "match_process": True,
            "min_similarity_score": 0.65,
        }
    )
    severity_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "CRITICAL": 10.0,
            "URGENT": 7.0,
            "HIGH": 5.0,
            "ELEVATED": 3.0,
            "ROUTINE": 1.0,
        }
    )
    pattern_detection_thresholds: Dict[str, Any] = Field(
        default_factory=lambda: {
            "min_findings_per_pattern": 2,
            "min_facilities_for_cross_unit": 2,
        }
    )
    priority_scoring_factors: Dict[str, float] = Field(
        default_factory=lambda: {
            "severity_weight": 0.35,
            "recurrence_weight": 0.25,
            "facility_spread_weight": 0.20,
            "unresolved_duration_weight": 0.20,
        }
    )

    is_active: bool = True
    is_deprecated: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateAnalyticsConfigRequest(BaseModel):
    """Request payload to establish a new analytics configuration version."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    repeat_matching_rules: Optional[Dict[str, Any]] = None
    severity_weights: Optional[Dict[str, float]] = None
    pattern_detection_thresholds: Optional[Dict[str, Any]] = None
    priority_scoring_factors: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ApproveAnalyticsConfigRequest(BaseModel):
    """Request payload to approve an analytics configuration."""

    model_config = ConfigDict(extra="ignore")

    approval_notes: str


class DeprecateAnalyticsConfigRequest(BaseModel):
    """Request payload to deprecate an existing analytics configuration."""

    model_config = ConfigDict(extra="ignore")

    deprecation_reason: str

"""Operational Usage Anomaly Schemas (Phase 28).

Provides:
- Anomaly categorization and lifecycle state
- Usage anomaly record representations
- Acknowledgement and resolution payloads
- Paginated anomaly query results

CRITICAL SAFETY & GOVERNANCE INVARIANTS:
- USAGE SPIKE != SECURITY INCIDENT
- ANOMALY != MALICIOUS ACTIVITY
- An operational anomaly is flagged as ANOMALY_DETECTED, NEVER SECURITY_ATTACK
  unless separately confirmed by security infrastructure.
- Zero PHI in anomaly descriptions or metrics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AnomalyType(str, Enum):
    """Types of operational usage anomalies detected."""

    API_TRAFFIC_SPIKE = "API_TRAFFIC_SPIKE"
    API_ERROR_SPIKE = "API_ERROR_SPIKE"
    LATENCY_SPIKE = "LATENCY_SPIKE"
    ABNORMAL_JOB_VOLUME = "ABNORMAL_JOB_VOLUME"
    REPEATED_FAILED_REQUESTS = "REPEATED_FAILED_REQUESTS"
    PROVIDER_FAILURE_BURST = "PROVIDER_FAILURE_BURST"
    RESOURCE_CONSUMPTION_SURGE = "RESOURCE_CONSUMPTION_SURGE"
    UNEXPECTED_USAGE_PATTERN = "UNEXPECTED_USAGE_PATTERN"


class AnomalySeverity(str, Enum):
    """Operational urgency level of the anomaly."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyStatus(str, Enum):
    """Lifecycle state of an operational anomaly."""

    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class UsageAnomaly(BaseModel):
    """Detected operational usage anomaly record."""

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: str = Field(default_factory=lambda: f"anom-{uuid.uuid4().hex[:10]}")
    anomaly_id: Optional[str] = None
    anomaly_type: AnomalyType = AnomalyType.UNEXPECTED_USAGE_PATTERN
    severity: AnomalySeverity = AnomalySeverity.MEDIUM
    status: AnomalyStatus = Field(default=AnomalyStatus.DETECTED)
    title: str = Field(default="Operational Usage Anomaly")
    description: str = Field(default="")
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metric_name: str = Field(default="operational_metric")
    current_value: float = Field(default=0.0)
    threshold_value: float = Field(default=0.0)
    baseline_value: float = Field(default=0.0)
    deviation_percent: float = Field(default=0.0)
    endpoint: Optional[str] = None
    endpoint_or_component: Optional[str] = None
    provider_name: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.anomaly_id and not self.id:
            self.id = self.anomaly_id
        elif self.id and not self.anomaly_id:
            self.anomaly_id = self.id
        if self.endpoint and not self.endpoint_or_component:
            self.endpoint_or_component = self.endpoint
        elif self.endpoint_or_component and not self.endpoint:
            self.endpoint = self.endpoint_or_component


class AnomalyAcknowledgeRequest(BaseModel):
    """Payload to acknowledge an operational anomaly."""

    model_config = ConfigDict(extra="ignore")

    notes: Optional[str] = Field(default=None, max_length=500)


class AnomalyResolveRequest(BaseModel):
    """Payload to resolve an operational anomaly."""

    model_config = ConfigDict(extra="ignore")

    resolution_notes: str = Field(..., min_length=3, max_length=1000)
    status: AnomalyStatus = Field(default=AnomalyStatus.RESOLVED)


class AnomalyListResponse(BaseModel):
    """Paginated list of detected anomalies."""

    model_config = ConfigDict(extra="ignore")

    items: List[UsageAnomaly] = Field(default_factory=list)
    anomalies: List[UsageAnomaly] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)
    skip: int = Field(default=0, ge=0)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)

    def model_post_init(self, __context: Any) -> None:
        if self.anomalies and not self.items:
            self.items = self.anomalies
        elif self.items and not self.anomalies:
            self.anomalies = self.items
        if self.total_count and not self.total:
            self.total = self.total_count
        elif self.total and not self.total_count:
            self.total_count = self.total
        if self.offset and not self.skip:
            self.skip = self.offset
        elif self.skip and not self.offset:
            self.offset = self.skip

"""Phase 71: Clinical Safety Governance Audit Analytics Source & Data Quality Schemas.

Defines schemas for:
- Controlled analytics source registration
- Data quality and reliability statuses
- Reporting period types and date range filters
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsSourceType(str, Enum):
    """Authoritative source entity types ingested into audit intelligence."""

    AUDIT_FINDING = "AUDIT_FINDING"
    AUDIT_REPORT = "AUDIT_REPORT"
    AUDIT_TEST = "AUDIT_TEST"
    AUDIT_SCOPE = "AUDIT_SCOPE"
    COMPLIANCE_ASSESSMENT = "COMPLIANCE_ASSESSMENT"
    DECISION_ASSURANCE = "DECISION_ASSURANCE"
    GOVERNANCE_EXCEPTION = "GOVERNANCE_EXCEPTION"
    POST_CLOSURE_VERIFICATION = "POST_CLOSURE_VERIFICATION"
    EFFECTIVENESS_REVIEW = "EFFECTIVENESS_REVIEW"
    CORRECTIVE_ACTION = "CORRECTIVE_ACTION"
    RISK_REVIEW = "RISK_REVIEW"
    SURVEILLANCE_SIGNAL = "SURVEILLANCE_SIGNAL"


class DataQualityStatus(str, Enum):
    """Reliability and completeness classification for analytical datasets."""

    COMPLETE = "COMPLETE"
    PARTIALLY_COMPLETE = "PARTIALLY_COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    INCONSISTENT = "INCONSISTENT"
    UNAVAILABLE = "UNAVAILABLE"


class ReportingPeriodType(str, Enum):
    """Configurable standard reporting periods."""

    LAST_30_DAYS = "LAST_30_DAYS"
    LAST_90_DAYS = "LAST_90_DAYS"
    LAST_6_MONTHS = "LAST_6_MONTHS"
    LAST_12_MONTHS = "LAST_12_MONTHS"
    CUSTOM = "CUSTOM"


class AnalyticsSourceRecord(BaseModel):
    """Domain model tracking an ingested authoritative analytical source record."""

    model_config = ConfigDict(extra="ignore")

    source_id: str = Field(default_factory=lambda: f"gsrc-{uuid.uuid4().hex[:12]}")
    source_type: AnalyticsSourceType
    source_record_id: str
    source_version: Optional[str] = "v1.0.0"
    source_status: str
    source_owner: str
    reporting_period: Optional[str] = None
    retrieval_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance_reference: str
    access_classification: str = "RESTRICTED"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DateRangeFilter(BaseModel):
    """Date boundary filters for historical finding queries and trend analytics."""

    model_config = ConfigDict(extra="ignore")

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    period_type: Optional[ReportingPeriodType] = ReportingPeriodType.LAST_90_DAYS

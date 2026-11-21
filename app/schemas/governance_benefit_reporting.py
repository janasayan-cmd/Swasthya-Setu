"""Phase 76: Benefit Reporting & Executive Analytics Schemas.

Defines schemas and models for:
- System-wide benefit realization reports
- Delayed and unrealized benefit inventories
- Longitudinal sustainability reports
- Portfolio benefit performance analytics
- Background benefit assurance job run results
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BenefitRealizationReportResponse(BaseModel):
    """System-wide summary of benefit realization progress."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_benefits: int = 0
    realized_count: int = 0
    partially_realized_count: int = 0
    delayed_count: int = 0
    not_realized_count: int = 0
    insufficient_evidence_count: int = 0
    benefits_by_category: Dict[str, int] = Field(default_factory=dict)
    clinical_safety_notice: str = (
        "Operational benefit realization only. Does not replace Phase 55 clinical effectiveness."
    )


class DelayedBenefitsReportResponse(BaseModel):
    """Report detailing benefits past their expected realization date."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    delayed_benefits_count: int = 0
    delayed_benefits: List[Dict[str, Any]] = Field(default_factory=list)


class UnrealizedBenefitsReportResponse(BaseModel):
    """Report detailing benefits that failed to realize expected operational outcomes."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    unrealized_benefits_count: int = 0
    unrealized_benefits: List[Dict[str, Any]] = Field(default_factory=list)


class BenefitSustainabilityReportResponse(BaseModel):
    """Report tracking longitudinal sustainability across multi-period measurements."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_monitored_benefits: int = 0
    sustained_count: int = 0
    declining_count: int = 0
    reversed_count: int = 0
    stale_data_count: int = 0
    sustainability_trends: List[Dict[str, Any]] = Field(default_factory=list)


class PortfolioBenefitPerformanceReportResponse(BaseModel):
    """Consolidated benefit performance across all active portfolios."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_portfolios_evaluated: int = 0
    portfolio_benefit_metrics: List[Dict[str, Any]] = Field(default_factory=list)


class BenefitVerificationReportResponse(BaseModel):
    """Summary of independent verification status across benefits."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_verifications: int = 0
    verified_count: int = 0
    verified_with_limitations_count: int = 0
    not_verified_count: int = 0
    pending_verification_count: int = 0
    verifications: List[Dict[str, Any]] = Field(default_factory=list)


class BenefitAssuranceJobRunResult(BaseModel):
    """Result of an automated benefit assurance routine scan."""
    model_config = ConfigDict(extra="forbid")

    job_name: str = "benefit_assurance_routine_scan"
    run_timestamp: str
    overdue_targets_flagged: int = 0
    missing_measurements_flagged: int = 0
    stale_source_evidence_flagged: int = 0
    expired_exceptions_flagged: int = 0
    details: List[str] = Field(default_factory=list)

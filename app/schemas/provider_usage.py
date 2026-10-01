"""External Provider & Cost/Consumption Analytics Schemas (Phase 28).

Provides schemas for:
- External provider usage metrics (OCR, AI, Medication terminology, Safety, FHIR, etc.)
- AI & LLM operational telemetry (token counts, models, latency, cost)
- Cost and resource consumption tracking
- Provider availability and performance summaries

CRITICAL INVARIANTS:
- PROVIDER FAILURE != SUCCESS
- ANALYTICS != CLINICAL DECISION
- No raw PHI in prompts, completions, OCR text, or provider payloads
- No secrets, API keys, or billing credentials exposed
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProviderCategory(str, Enum):
    """Categories of external and infrastructure service providers."""

    OCR = "ocr"
    MEDICATION_TERMINOLOGY = "medication_terminology"
    MEDICATION_SAFETY = "medication_safety"
    AI = "ai"
    FHIR_HL7 = "fhir_hl7"
    GEOLOCATION = "geolocation"
    OBJECT_STORAGE = "object_storage"
    QUEUE_PROVIDER = "queue_provider"
    OTHER = "other"


class ProviderUsageItem(BaseModel):
    """Aggregated usage metrics for a specific external provider."""

    model_config = ConfigDict(extra="ignore")

    provider_name: str = Field(..., description="Identifier of the external provider (e.g. google_cloud_vision, gemini, rxnorm)")
    provider_category: ProviderCategory = Field(..., description="Operational category of the provider")
    provider_version: Optional[str] = Field(default=None, description="Reported or configured provider API version")
    request_count: int = Field(default=0, ge=0, description="Total API requests sent to this provider")
    success_count: int = Field(default=0, ge=0, description="Successful responses from this provider")
    failure_count: int = Field(default=0, ge=0, description="Failed responses (5xx, 4xx, network errors)")
    timeout_count: int = Field(default=0, ge=0, description="Requests that timed out before receiving a response")
    retry_count: int = Field(default=0, ge=0, description="Total automatic retries performed")
    avg_latency_ms: float = Field(default=0.0, ge=0.0, description="Mean roundtrip latency in milliseconds")
    p95_latency_ms: float = Field(default=0.0, ge=0.0, description="95th percentile latency in milliseconds")
    availability_percentage: float = Field(default=100.0, ge=0.0, le=100.0, description="Estimated uptime/availability percentage")
    estimated_cost_usd: float = Field(default=0.0, ge=0.0, description="Estimated usage cost in USD based on volume/tokens")


class ProviderUsageResponse(BaseModel):
    """Response payload for provider usage analytics."""

    model_config = ConfigDict(extra="ignore")

    total_providers_tracked: int = Field(default=0, ge=0)
    total_provider_requests: int = Field(default=0, ge=0)
    total_provider_failures: int = Field(default=0, ge=0)
    total_provider_timeouts: int = Field(default=0, ge=0)
    overall_provider_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    providers: List[ProviderUsageItem] = Field(default_factory=list)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AIUsageMetricsItem(BaseModel):
    """Telemetry item for AI and LLM inference operations (Phase 14 integration)."""

    model_config = ConfigDict(extra="ignore")

    model_name: str = Field(..., description="Model identifier (e.g. gemini-1.5-pro, gemini-1.5-flash)")
    task_type: str = Field(..., description="Operational AI task type (e.g. clinical_summarization, extraction, triage_support)")
    request_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    timeout_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    structured_output_validation_failures: int = Field(default=0, ge=0, description="Number of schema validation failures on LLM outputs")
    prompt_tokens: int = Field(default=0, ge=0, description="Aggregate prompt tokens consumed")
    completion_tokens: int = Field(default=0, ge=0, description="Aggregate completion tokens generated")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
    p95_latency_ms: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)


class CostCategory(str, Enum):
    """Cost & resource consumption breakdown categories."""

    AI_INFERENCE = "ai_inference"
    OCR_DOCUMENT_PAGES = "ocr_document_pages"
    MEDICATION_SAFETY_CHECKS = "medication_safety_checks"
    MEDICATION_TERMINOLOGY = "medication_terminology"
    INTEROPERABILITY_TRANSFERS = "interoperability_transfers"
    STORAGE_CONSUMPTION = "storage_consumption"
    QUEUE_MESSAGING = "queue_messaging"
    COMPUTE_API_VOLUME = "compute_api_volume"


class CostBreakdownItem(BaseModel):
    """Cost breakdown line item for capacity and financial governance."""

    model_config = ConfigDict(extra="ignore")

    category: CostCategory = Field(..., description="Operational cost category")
    resource_units: float = Field(default=0.0, ge=0.0, description="Quantity of consumed units (tokens, pages, calls, GB-months)")
    unit_description: str = Field(..., description="Description of the unit (e.g., '1K tokens', 'pages', 'API calls')")
    estimated_cost_usd: float = Field(default=0.0, ge=0.0, description="Calculated expenditure in USD")
    percentage_of_total: float = Field(default=0.0, ge=0.0, le=100.0)


class CostMetricsResponse(BaseModel):
    """Aggregated operational resource and cost metrics response."""

    model_config = ConfigDict(extra="ignore")

    total_cost_usd: float = Field(default=0.0, ge=0.0)
    currency: str = Field(default="USD")
    breakdown: List[CostBreakdownItem] = Field(default_factory=list)
    ai_telemetry: List[AIUsageMetricsItem] = Field(default_factory=list)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None
    capacity_notes: List[str] = Field(default_factory=list, description="Advisory capacity and cost trend insights")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

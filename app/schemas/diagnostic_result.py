"""Pydantic schemas for Diagnostic Results & Analyte Items (Phase 34).

SAFETY & ARCHITECTURAL INVARIANTS:
- LAB RESULT != CLINICAL INTERPRETATION
- ABNORMAL RESULT != DIAGNOSIS
- CRITICAL RESULT FLAG != AUTONOMOUS TREATMENT DECISION
- RESULT EXTRACTION != RESULT VERIFICATION
- RESULT VERIFICATION != CLINICAL DIAGNOSIS
- REFERENCE RANGE != UNIVERSAL NORMALITY (DO NOT INVENT REFERENCE RANGES)
- MISSING REFERENCE RANGE != NORMAL
- MISSING UNIT != ASSUMED UNIT (DO NOT CONVERT UNITS SILENTLY)
- UNKNOWN RESULT != NORMAL RESULT
- CORRECTED RESULT != REPLACED HISTORY (FULL IMMUTABLE VERSIONING PRESERVED)
- IMPORTED RESULT != VERIFIED RESULT
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ResultStatus(str, Enum):
    """Lifecycle status of a diagnostic laboratory result."""

    PRELIMINARY = "PRELIMINARY"
    FINAL = "FINAL"
    CORRECTED = "CORRECTED"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    """Phase 10-aligned clinical verification states."""

    EXTRACTED = "EXTRACTED"
    IMPORTED = "IMPORTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    VERIFIED = "VERIFIED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class AbnormalFlag(str, Enum):
    """Provider-supplied flags denoting analyte reference deviation."""

    NORMAL = "NORMAL"
    HIGH = "HIGH"
    LOW = "LOW"
    CRITICAL = "CRITICAL"
    ABNORMAL = "ABNORMAL"
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    REACTIVE = "REACTIVE"
    NON_REACTIVE = "NON_REACTIVE"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNKNOWN = "UNKNOWN"


class ReferenceRange(BaseModel):
    """Authoritative reference range supplied by testing laboratory."""

    model_config = ConfigDict(populate_by_name=True)

    is_available: bool = Field(default=True, description="False if laboratory provided no reference range")
    low: Optional[float] = Field(default=None, description="Lower limit of normal")
    high: Optional[float] = Field(default=None, description="Upper limit of normal")
    unit: Optional[str] = Field(default=None, description="Unit of measurement for reference interval")
    text: Optional[str] = Field(default=None, description="Descriptive text range or qualitative expectation")
    age_low: Optional[int] = Field(default=None, description="Demographic age lower bound (years/months)")
    age_high: Optional[int] = Field(default=None, description="Demographic age upper bound (years/months)")
    sex: Optional[str] = Field(default=None, description="Demographic sex applicability (M, F, ALL)")
    provider_comment: Optional[str] = Field(default=None, description="Provider method or caveat comments")


class DiagnosticResultItemCreate(BaseModel):
    """Single analyte measurement or observation to be recorded."""

    analyte_name: str = Field(description="Name of tested analyte or observation")
    analyte_code: Optional[str] = Field(default=None, description="LOINC or provider analyte code")
    system: Optional[str] = Field(default="LOINC", description="Coding terminology system")
    numeric_value: Optional[float] = Field(default=None, description="Quantitative measurement if applicable")
    qualitative_value: Optional[str] = Field(default=None, description="Categorical finding (e.g. POSITIVE, DETECTED)")
    unit: Optional[str] = Field(default=None, description="Authoritative unit (e.g. mg/dL, mmol/L)")
    reference_range: Optional[ReferenceRange] = Field(default=None, description="Supplied reference range")
    abnormal_flag: AbnormalFlag = Field(default=AbnormalFlag.UNKNOWN, description="Laboratory-assigned abnormality flag")
    notes: Optional[str] = Field(default=None, description="Technician comments or method description")


class DiagnosticResultItem(BaseModel):
    """Persisted analyte measurement."""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str
    result_id: str
    analyte_name: str
    analyte_code: Optional[str] = None
    system: Optional[str] = "LOINC"
    numeric_value: Optional[float] = None
    qualitative_value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[ReferenceRange] = None
    abnormal_flag: AbnormalFlag = AbnormalFlag.UNKNOWN
    notes: Optional[str] = None


class DiagnosticResultIngest(BaseModel):
    """Payload for ingesting results from an external provider or laboratory."""

    order_id: Optional[str] = Field(default=None, description="Associated HealthSetu order ID if known")
    patient_id: Optional[str] = Field(default=None, description="Associated HealthSetu patient ID if known")
    external_patient_id: Optional[str] = Field(default=None, description="Provider patient identifier")
    external_order_id: Optional[str] = Field(default=None, description="Provider order reference number")
    provider_id: str = Field(description="Identifier of laboratory/diagnostic provider")
    provider_result_id: str = Field(description="Provider unique result identifier")
    status: ResultStatus = Field(default=ResultStatus.FINAL)
    items: List[DiagnosticResultItemCreate] = Field(min_length=1, description="Analyte measurements")
    report_text: Optional[str] = Field(default=None, description="Narrative report text if supplied")
    document_id: Optional[str] = Field(default=None, description="Associated secure medical document ID")
    collected_at: Optional[datetime] = None
    resulted_at: Optional[datetime] = None
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class DiagnosticResultRecord(BaseModel):
    """Authoritative representation of a laboratory/diagnostic result record."""

    model_config = ConfigDict(populate_by_name=True)

    result_id: str = Field(description="Unique internal result identifier")
    order_id: Optional[str] = None
    patient_id: str
    encounter_id: Optional[str] = None
    clinician_id: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    provider_id: str
    provider_result_id: str
    status: ResultStatus = ResultStatus.FINAL
    verification_status: VerificationStatus = VerificationStatus.REVIEW_REQUIRED
    items: List[DiagnosticResultItem] = Field(default_factory=list)
    has_critical_flag: bool = Field(default=False, description="True if any item has CRITICAL abnormal flag")
    version: int = Field(default=1, ge=1, description="Version number of this result")
    is_current: bool = Field(default=True, description="True if this is the active current version")
    supersedes_result_id: Optional[str] = Field(default=None, description="Prior version result ID if amended")
    correction_reason: Optional[str] = Field(default=None, description="Documented reason for correction/amendment")
    corrected_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    collected_at: Optional[datetime] = None
    resulted_at: Optional[datetime] = None
    document_id: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResultVerificationRequest(BaseModel):
    """Request payload for Phase 10 clinician result verification."""

    action: str = Field(pattern="^(VERIFY|REJECT)$", description="'VERIFY' to certify fact or 'REJECT' if invalid")
    notes: Optional[str] = Field(default=None, description="Clinician review and verification commentary")


class DiagnosticResultFilter(BaseModel):
    """Filter options for querying diagnostic results."""

    patient_id: Optional[str] = None
    order_id: Optional[str] = None
    clinician_id: Optional[str] = None
    status: Optional[ResultStatus] = None
    verification_status: Optional[VerificationStatus] = None
    has_critical: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class DiagnosticResultListResponse(BaseModel):
    """Paginated diagnostic results list."""

    items: List[DiagnosticResultRecord] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)

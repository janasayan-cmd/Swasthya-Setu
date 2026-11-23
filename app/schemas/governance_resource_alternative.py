"""Phase 86: Alternative Resource and Fallback Mapping Schemas.

Defines structures for documenting alternative resources, substitution conditions,
access prerequisites, and fallback readiness assessments.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
    FallbackReadinessOutcome,
)


class AlternativeResourceRecord(BaseModel):
    alternative_id: str
    tenant_id: str
    primary_resource_id: str
    alternative_resource_id: str
    substitution_conditions: str
    dependency_compatibility: Optional[str] = None
    required_configuration_ref: Optional[str] = None
    access_prerequisites: List[str] = Field(default_factory=list)
    organizational_scope: str = "ORGANIZATION"
    capacity_constraints: Optional[str] = None
    known_limitations: Optional[str] = None
    verification_evidence_ref: Optional[str] = None
    last_successful_validation: Optional[datetime] = None
    approval_ref: Optional[str] = None
    expiry_date: Optional[datetime] = None
    fallback_readiness: FallbackReadinessOutcome = FallbackReadinessOutcome.NOT_ASSESSED
    readiness_assessed_by: Optional[str] = None
    readiness_assessed_at: Optional[datetime] = None
    readiness_notes: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class CreateAlternativeResourceRequest(BaseModel):
    primary_resource_id: str
    alternative_resource_id: str
    substitution_conditions: str
    dependency_compatibility: Optional[str] = None
    required_configuration_ref: Optional[str] = None
    access_prerequisites: List[str] = Field(default_factory=list)
    organizational_scope: str = "ORGANIZATION"
    capacity_constraints: Optional[str] = None
    known_limitations: Optional[str] = None
    expiry_date: Optional[datetime] = None


class AssessFallbackReadinessRequest(BaseModel):
    fallback_readiness: FallbackReadinessOutcome
    readiness_notes: str
    verification_evidence_ref: Optional[str] = None
    last_successful_validation: Optional[datetime] = None
    limitations_identified: Optional[str] = None
    limitations_identified: Optional[str] = None

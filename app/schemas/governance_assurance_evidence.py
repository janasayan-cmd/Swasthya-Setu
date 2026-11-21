"""Phase 77: Clinical Safety Governance Assurance Evidence Schemas.

Defines schemas for evidence intake, lineage tracking across earlier phases,
freshness verification, and validation status.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    MaturityDimensionEnum,
)


class EvidenceSourceWorkflow(str, Enum):
    """Source workflow reference across HealthSetu phases."""
    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"
    PHASE_54_CAPA = "PHASE_54_CAPA"
    PHASE_63_RISK = "PHASE_63_RISK"
    PHASE_67_ESCALATION = "PHASE_67_ESCALATION"
    PHASE_69_COMPLIANCE = "PHASE_69_COMPLIANCE"
    PHASE_70_AUDIT = "PHASE_70_AUDIT"
    PHASE_71_AUDIT_INTEL = "PHASE_71_AUDIT_INTEL"
    PHASE_72_MANAGEMENT_REVIEW = "PHASE_72_MANAGEMENT_REVIEW"
    PHASE_73_IMPLEMENTATION = "PHASE_73_IMPLEMENTATION"
    PHASE_74_ADOPTION = "PHASE_74_ADOPTION"
    PHASE_75_PORTFOLIO = "PHASE_75_PORTFOLIO"
    PHASE_76_BENEFIT = "PHASE_76_BENEFIT"
    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"
    ORGANIZATIONAL_POLICY = "ORGANIZATIONAL_POLICY"


class EvidenceVerificationStatus(str, Enum):
    """Verification status of submitted governance assurance evidence."""
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNVERIFIED = "UNVERIFIED"


class GovernanceAssuranceEvidenceRecord(BaseModel):
    """Authoritative record for submitted governance assurance evidence."""
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    tenant_id: str
    assessment_id: str
    dimension: MaturityDimensionEnum
    criterion_id: str
    source_workflow: EvidenceSourceWorkflow
    source_record_id: str
    title: str
    description: str
    artifact_uri: Optional[str] = None
    verification_status: EvidenceVerificationStatus
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    verification_notes: Optional[str] = None
    collected_by: str
    collected_at: str
    freshness_timestamp: str
    is_stale: bool = False
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class SubmitAssuranceEvidenceRequest(BaseModel):
    """Request to submit an evidence item for an assessment criterion."""
    model_config = ConfigDict(extra="forbid")

    dimension: MaturityDimensionEnum
    criterion_id: str
    source_workflow: EvidenceSourceWorkflow
    source_record_id: str
    title: str
    description: str
    artifact_uri: Optional[str] = None
    freshness_timestamp: Optional[str] = None


class VerifyAssuranceEvidenceRequest(BaseModel):
    """Request to verify submitted assurance evidence."""
    model_config = ConfigDict(extra="forbid")

    verification_notes: Optional[str] = None


class RejectAssuranceEvidenceRequest(BaseModel):
    """Request to reject submitted assurance evidence."""
    model_config = ConfigDict(extra="forbid")

    rejection_reason: str

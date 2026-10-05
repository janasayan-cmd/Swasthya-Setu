"""HealthSetu Phase 42 - Patient Submission Schemas.

Models for patient self-service submissions, corrections, document attachments,
and provenance tracking.

NON-NEGOTIABLE CLINICAL SAFETY PRINCIPLES:
- PATIENT SUBMISSION != VERIFIED MEDICAL DATA
- PATIENT MEDICATION ENTRY != VERIFIED MEDICATION
- PATIENT ALLERGY ENTRY != VERIFIED ALLERGY
- PATIENT REPORTED SYMPTOM != TRIAGE RESULT
- HISTORICAL SUBMISSIONS MUST BE PRESERVED UPON CORRECTION (Submission 1 -> Submission 2)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.questionnaire import QuestionnaireAnswer


class SubmissionType(str, Enum):
    """Categorization of submission payload."""

    ACTION_SUBMISSION = "ACTION_SUBMISSION"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    DOCUMENT = "DOCUMENT"
    APPOINTMENT_CONFIRMATION = "APPOINTMENT_CONFIRMATION"
    CARE_PLAN_ACKNOWLEDGEMENT = "CARE_PLAN_ACKNOWLEDGEMENT"
    CORRECTION = "CORRECTION"
    REFUSAL = "REFUSAL"


class SubmissionProvenance(BaseModel):
    """Immutable provenance record tracking who, when, and how data was submitted."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    actor_id: str
    actor_role: str
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    system_version: str = "HealthSetu-Phase42"


class PatientSubmissionRecord(BaseModel):
    """Authoritative representation of a patient submission instance."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"psub_{uuid4().hex[:16]}")
    action_id: str
    patient_id: str
    submission_version: int = 1
    submission_type: SubmissionType
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    responses: Dict[str, Any] = Field(default_factory=dict)
    document_ids: List[str] = Field(default_factory=list)
    questionnaire_answers: List[QuestionnaireAnswer] = Field(default_factory=list)
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None
    is_correction: bool = False
    correction_reason: Optional[str] = None
    prior_submission_id: Optional[str] = None
    provenance: SubmissionProvenance
    clinical_verification_status: str = "PATIENT_REPORTED_UNVERIFIED"
    is_verified_clinical_record: bool = False
    clinical_safety_notice: str = (
        "PATIENT SUBMISSION != VERIFIED MEDICAL DATA. "
        "SUBMISSION CANNOT BE AUTONOMOUSLY CONVERTED INTO DIAGNOSES, MEDICATION CHANGES, "
        "OR EMERGENCY DISPATCH."
    )


class DocumentSubmissionRequest(BaseModel):
    """Request payload to link an existing uploaded document to a patient action."""

    document_id: str = Field(..., description="ID of previously uploaded Phase 5 document")
    document_type: Optional[str] = None
    description: Optional[str] = None
    idempotency_key: Optional[str] = None


class DocumentSubmissionRecord(BaseModel):
    """Authoritative link between a patient action and a Phase 5 secure document."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"pdoc_{uuid4().hex[:16]}")
    action_id: str
    patient_id: str
    document_id: str
    document_type: Optional[str] = None
    description: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_by: str
    clinical_verification_notice: str = (
        "UPLOADED DOCUMENT CONTAINS UNVERIFIED PATIENT DATA PENDING CLINICAL REVIEW."
    )

"""HealthSetu Phase 42 - Questionnaire Schemas.

Structured Non-Clinical and Operational Questionnaire Definitions and Responses.

NON-NEGOTIABLE CLINICAL SAFETY PRINCIPLES:
- PATIENT QUESTIONNAIRE != DIAGNOSIS
- PATIENT REPORTED SYMPTOM != TRIAGE RESULT
- QUESTIONNAIRE RESPONSES ARE PATIENT-REPORTED DATA, NOT VERIFIED MEDICAL TRUTH.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(str, Enum):
    """Supported structured question input types."""

    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TEXT = "TEXT"
    SCALE = "SCALE"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    NUMBER = "NUMBER"


class QuestionItem(BaseModel):
    """A single structured question in a questionnaire."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str = Field(..., description="Unique question identifier within questionnaire")
    text: str = Field(..., description="The prompt or question text displayed to the patient")
    question_type: QuestionType
    required: bool = True
    options: List[str] = Field(default_factory=list, description="Allowed choices for choice questions")
    help_text: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class QuestionnaireDefinition(BaseModel):
    """Reusable questionnaire template version."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"qst_{uuid4().hex[:12]}")
    code: str = Field(..., description="Machine-readable questionnaire identifier")
    title: str = Field(..., description="Title of questionnaire")
    description: Optional[str] = None
    version: str = "1.0.0"
    is_active: bool = True
    questions: List[QuestionItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuestionnaireAnswer(BaseModel):
    """A patient's answer to a single question."""

    question_id: str
    question_text: Optional[str] = None
    value: Any = Field(..., description="Structured answer value (string, number, boolean, or list)")


class QuestionnaireSubmissionRequest(BaseModel):
    """Payload submitted by a patient for a questionnaire action."""

    answers: List[QuestionnaireAnswer] = Field(..., min_length=1, description="List of question answers")
    idempotency_key: Optional[str] = None
    notes: Optional[str] = None


class QuestionnaireResponseRecord(BaseModel):
    """Authoritative snapshot of a patient's questionnaire submission."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"qres_{uuid4().hex[:16]}")
    questionnaire_id: str
    questionnaire_version: str
    action_id: str
    patient_id: str
    answers: List[QuestionnaireAnswer] = Field(default_factory=list)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_by: Optional[str] = None
    clinical_verification_notice: str = (
        "PATIENT QUESTIONNAIRE RESPONSES ARE PATIENT-REPORTED OBSERVATIONS, "
        "NOT CLINICALLY VERIFIED ASSESSMENTS OR TRIAGE RESULTS."
    )

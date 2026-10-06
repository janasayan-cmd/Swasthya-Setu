"""Decision Explanation Contracts (Phase 47).

Defines:
- Patient-facing and Clinician-facing explanation models
- Invariants:
  - EXPLANATION != CLINICAL JUSTIFICATION
  - EXPLANATION != INTERNAL MODEL REASONING (No hidden chain-of-thought exposure)
  - Patient-facing explanations use safe, plain wording without unsupported clinical claims
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decisions import DecisionType


class ExplanationAudience(str, Enum):
    """Target consumer role for structured explanations."""

    PATIENT = "PATIENT"
    CLINICIAN = "CLINICIAN"
    AUDITOR = "AUDITOR"


class ExplanationResponse(BaseModel):
    """Structured explanation answering what, why, and how for a system decision."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str
    decision_type: DecisionType
    audience: ExplanationAudience
    headline: str = Field(description="High-level summary of recommendation or classification")
    why_generated: str = Field(description="Explanation of why this output was produced")
    inputs_considered: List[str] = Field(default_factory=list, description="List of factors/data points evaluated")
    rules_or_model_used: str = Field(description="Rule set or model provider reference")
    human_oversight_status: str = Field(description="Current review determination (e.g. APPROVED BY CLINICIAN)")
    is_current: bool = Field(description="True if not superseded or expired")
    is_applied: bool = Field(description="True if recommendation has been applied to clinical workflow")
    evidence_references: List[str] = Field(default_factory=list, description="Safe references to guidelines or evidence")
    confidence: Optional[float] = Field(default=None, description="Explicit provider confidence if available")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = Field(
        default="System-generated recommendations are clinical aids and do not constitute an autonomous diagnosis or treatment plan.",
        description="Clinical safety boundary disclaimer",
    )

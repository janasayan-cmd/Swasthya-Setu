"""Base abstraction for Data Quality rule engine (Phase 26)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.data_quality import DataQualityFindingRecord


class RuleContext(BaseModel):
    """Aggregate clinical context provided to data quality rules for evaluation."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    patient_id: str
    patient: Optional[Any] = None
    allergies: List[Any] = Field(default_factory=list)
    medications: List[Any] = Field(default_factory=list)
    prescriptions: List[Any] = Field(default_factory=list)
    vitals: List[Any] = Field(default_factory=list)
    documents: List[Any] = Field(default_factory=list)
    encounters: List[Any] = Field(default_factory=list)
    care_plans: List[Any] = Field(default_factory=list)
    observations: List[Any] = Field(default_factory=list)
    external_imports: List[Any] = Field(default_factory=list)
    custom_context: Dict[str, Any] = Field(default_factory=dict)


class DataQualityRule(ABC):
    """Base class for all deterministic data quality, duplicate, and conflict rules."""

    rule_name: str = "BaseRule"
    rule_version: str = "1.0.0"
    category: str = "GENERAL"

    @abstractmethod
    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        """Evaluate context and return any detected data quality findings."""
        pass

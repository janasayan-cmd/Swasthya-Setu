"""Phase 80: Continuity Performance and Assurance Reporting Schemas.

Defines schemas and models for:
- Consolidated governance resilience and continuity reporting
- Scheduled background routine maintenance scan job result
"""

from typing import Any, Dict, List
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
    ClinicalSafetyGovernanceCapabilityRecord,
)
from app.schemas.governance_continuity_plan import GovernanceContinuityPlanRecord
from app.schemas.governance_continuity_dependency import GovernanceContinuityDependencyRecord
from app.schemas.governance_continuity_disruption import GovernanceDisruptionRecord
from app.schemas.governance_continuity_arrangements import AlternativeOperatingArrangementRecord
from app.schemas.governance_continuity_reconciliation import TemporaryGovernanceDecisionRecord
from app.schemas.governance_continuity_recovery import GovernanceRecoveryRecord
from app.schemas.governance_continuity_exercises import ContinuityExerciseRecord
from app.schemas.governance_continuity_gaps import ContinuityGapRecord


class CapabilityInventorySummaryResponse(BaseModel):
    """Overview summary of critical governance capabilities by tier."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    total_capabilities: int
    tier_1_critical_count: int
    tier_2_essential_count: int
    tier_3_important_count: int
    tier_4_supporting_count: int
    approved_count: int
    pending_count: int
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER


class ContinuityPlanCoverageResponse(BaseModel):
    """Report detailing continuity plan coverage across critical capabilities."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    total_plans: int
    active_plans_count: int
    covered_capability_count: int
    uncovered_capability_ids: List[str] = Field(default_factory=list)
    coverage_ratio: float = 1.0
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER


class OrganizationalResilienceAssuranceResponse(BaseModel):
    """Consolidated executive dossier assessing organizational governance resilience."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    reporting_period: str
    governance_resilience_rating: str
    total_critical_capabilities: int
    active_continuity_plans: int
    active_disruptions_count: int
    open_reconciliations_count: int
    unresolved_gaps_count: int
    resilience_summary: str
    evidence_coverage: float = 0.95
    known_limitations: str = ""
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER


class ContinuityRoutineScanJobResult(BaseModel):
    """Idempotent scheduled routine maintenance scan job report."""
    model_config = ConfigDict(extra="forbid")

    scanned_capabilities: int
    scanned_plans: int
    spofs_detected: int
    expired_plans_flagged: int
    overdue_exercises_flagged: int
    unreconciled_decisions_flagged: int
    active_gaps_flagged: int
    status: str = "COMPLETED"
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER

"""Phase 78: Governance Strategy Reporting Schemas.

Defines schemas and models for:
- Multi-year roadmap overviews and milestone schedules
- Strategy-to-portfolio alignment analysis
- Background scheduled job execution results
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class StrategyRoadmapOverviewResponse(BaseModel):
    """High-level summary of a strategic roadmap and its components."""
    model_config = ConfigDict(extra="forbid")

    roadmap_id: str
    tenant_id: str
    title: str
    status: str
    current_version: int
    planning_horizon: str
    start_date: str
    end_date: str
    total_objectives: int
    total_milestones: int
    completed_milestones: int
    delayed_milestones: int
    total_investment_proposed: float
    currency: str
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class ObjectiveRegisterResponse(BaseModel):
    """Report response listing strategic objectives and their status."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    roadmap_id: Optional[str] = None
    objectives: List[Dict[str, Any]]
    total_count: int
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class MilestoneScheduleResponse(BaseModel):
    """Report response listing roadmap milestones chronologically."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    roadmap_id: str
    milestones: List[Dict[str, Any]]
    total_count: int
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class PortfolioStrategyAlignmentResponse(BaseModel):
    """Report analyzing alignment between strategic objectives and Phase 75 portfolios."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    roadmap_id: str
    aligned_objectives_count: int
    unlinked_objectives_count: int
    active_portfolio_links: List[Dict[str, Any]]
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class StrategyIssueSummaryResponse(BaseModel):
    """Report summarizing open strategic risks, conflicts, and issues."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    roadmap_id: str
    total_issues: int
    open_issues: int
    escalated_issues: int
    issues_by_classification: Dict[str, int]
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class StrategyRoutineScanJobResult(BaseModel):
    """Result of an idempotent background strategic roadmap maintenance scan."""
    model_config = ConfigDict(extra="forbid")

    scanned_roadmaps: int
    scanned_milestones: int
    overdue_milestones_flagged: int
    dependency_conflicts_detected: int
    reminders_generated: int
    status: str

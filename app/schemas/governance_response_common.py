"""Phase 88: Clinical Safety Governance Resilience Response Strategy — Common Schemas.

Shared enums, constants, and mandatory disclaimer for response strategy optimization,
recovery option evaluation, and continuity decision support.
"""

from enum import Enum

MANDATORY_RESPONSE_STRATEGY_DISCLAIMER = (
    "Response strategy evaluation, recovery option comparison, and continuity decision-support records "
    "are administrative governance instruments and do NOT constitute proof of operational resilience, "
    "engineering redundancy, failover guarantee, or clinical safety certification. "
    "Phase 88 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, "
    "73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, or 87. "
    "The system does not autonomously activate continuity plans, switch infrastructure, or deploy personnel."
)


class ResponseStrategyCategory(str, Enum):
    """Classification of proposed resilience response and recovery strategies."""
    MAINTAIN_WITH_SAFEGUARDS = "MAINTAIN_WITH_SAFEGUARDS"
    OPERATE_VIA_ALTERNATIVE_RESOURCES = "OPERATE_VIA_ALTERNATIVE_RESOURCES"
    TEMPORARY_REDUCTION_NONESSENTIAL = "TEMPORARY_REDUCTION_NONESSENTIAL"
    SWITCH_COMMUNICATION_CHANNEL = "SWITCH_COMMUNICATION_CHANNEL"
    ALTERNATIVE_INFORMATION_ACCESS = "ALTERNATIVE_INFORMATION_ACCESS"
    COORDINATE_TEMPORARY_ARRANGEMENTS = "COORDINATE_TEMPORARY_ARRANGEMENTS"
    PRIORITIZE_RESTORATION = "PRIORITIZE_RESTORATION"
    MANUAL_DOCUMENTATION_PROCEDURES = "MANUAL_DOCUMENTATION_PROCEDURES"
    EXTERNAL_SERVICE_ALTERNATIVE = "EXTERNAL_SERVICE_ALTERNATIVE"
    MANAGEMENT_DIRECTED_DECISION = "MANAGEMENT_DIRECTED_DECISION"


class StrategyReviewStatus(str, Enum):
    """Lifecycle review status of a proposed response strategy."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class RecoveryFeasibilityOutcome(str, Enum):
    """Evidence-grounded feasibility evaluation outcome for candidate recovery options."""
    FEASIBLE_VERIFIED = "FEASIBLE_VERIFIED"
    CONDITIONALLY_FEASIBLE = "CONDITIONALLY_FEASIBLE"
    NOT_FEASIBLE = "NOT_FEASIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_ASSESSED = "NOT_ASSESSED"
    EXPIRED_EVIDENCE = "EXPIRED_EVIDENCE"


class RecommendationLifecycleStatus(str, Enum):
    """Human review and decision governance status for a recovery recommendation package."""
    DRAFT = "DRAFT"
    ANALYSIS_PENDING = "ANALYSIS_PENDING"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    EVIDENCE_REVIEW_PENDING = "EVIDENCE_REVIEW_PENDING"
    UNDER_HUMAN_REVIEW = "UNDER_HUMAN_REVIEW"
    CHALLENGED = "CHALLENGED"
    ADDITIONAL_EVIDENCE_REQUIRED = "ADDITIONAL_EVIDENCE_REQUIRED"
    RECOMMENDATION_PREPARED = "RECOMMENDATION_PREPARED"
    SUBMITTED_FOR_DECISION = "SUBMITTED_FOR_DECISION"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CLOSED = "CLOSED"


class ContinuityHandoffStatus(str, Enum):
    """Status of an approved strategy handoff to Phase 80 Continuity Operations."""
    PREPARED = "PREPARED"
    HANDED_OFF = "HANDED_OFF"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ACTIVE_IN_CONTINUITY = "ACTIVE_IN_CONTINUITY"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class ExecutionTrackingStatus(str, Enum):
    """Operational progress and reconciliation status of recovery strategy execution."""
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    DEVIATION_REPORTED = "DEVIATION_REPORTED"
    RESTORED_PENDING_VERIFICATION = "RESTORED_PENDING_VERIFICATION"
    VERIFIED_RESTORED = "VERIFIED_RESTORED"
    FAILED = "FAILED"

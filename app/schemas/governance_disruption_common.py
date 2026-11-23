"""Phase 87: Clinical Safety Governance Resilience Disruption Impact — Common Schemas.

Shared enums, constants, and mandatory disclaimer for disruption impact analysis,
cascading failure assessment, and cross-dependency scenario intelligence.
"""

from enum import Enum

MANDATORY_DISRUPTION_IMPACT_DISCLAIMER = (
    "Disruption impact analysis, cascading failure assessments, and cross-dependency scenario intelligence "
    "are administrative governance instruments and do NOT constitute proof of operational resilience, "
    "engineering redundancy, failover guarantee, or clinical safety certification. "
    "Phase 87 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, "
    "73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, or 86. "
    "Hypothetical disruption scenarios must never be treated as actual incidents, and "
    "unverified dependency paths do not prove inevitable operational failure."
)


class DisruptionScenarioCategory(str, Enum):
    """Categories of disruption scenarios."""
    APPLICATION_UNAVAILABILITY = "APPLICATION_UNAVAILABILITY"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    NETWORK_DISRUPTION = "NETWORK_DISRUPTION"
    CLOUD_INTERRUPTION = "CLOUD_INTERRUPTION"
    DATA_STORAGE_UNAVAILABILITY = "DATA_STORAGE_UNAVAILABILITY"
    IDENTITY_AUTHENTICATION_DISRUPTION = "IDENTITY_AUTHENTICATION_DISRUPTION"
    EXTERNAL_PROVIDER_OUTAGE = "EXTERNAL_PROVIDER_OUTAGE"
    INFORMATION_SOURCE_UNAVAILABILITY = "INFORMATION_SOURCE_UNAVAILABILITY"
    FACILITY_DISRUPTION = "FACILITY_DISRUPTION"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    CRITICAL_EQUIPMENT_UNAVAILABILITY = "CRITICAL_EQUIPMENT_UNAVAILABILITY"
    PERSONNEL_UNAVAILABILITY = "PERSONNEL_UNAVAILABILITY"
    MULTIPLE_SIMULTANEOUS_FAILURES = "MULTIPLE_SIMULTANEOUS_FAILURES"
    CROSS_FACILITY_DISRUPTION = "CROSS_FACILITY_DISRUPTION"
    CROSS_ORGANIZATIONAL_FAILURE = "CROSS_ORGANIZATIONAL_FAILURE"
    PROLONGED_DEGRADED_OPERATION = "PROLONGED_DEGRADED_OPERATION"


class ScenarioReviewStatus(str, Enum):
    """Lifecycle review status of a disruption scenario."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class ImpactSeverity(str, Enum):
    """Assessed severity of a disruption impact."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NEGLIGIBLE = "NEGLIGIBLE"
    UNKNOWN = "UNKNOWN"


class ImpactCertainty(str, Enum):
    """Certainty and evidence-grounding of an impact finding."""
    CONFIRMED = "CONFIRMED"
    POTENTIAL = "POTENTIAL"
    CONDITIONAL = "CONDITIONAL"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class AssessmentReviewStatus(str, Enum):
    """Human review and governance state of an impact assessment."""
    DRAFT = "DRAFT"
    AUTOMATED_ANALYSIS_COMPLETED = "AUTOMATED_ANALYSIS_COMPLETED"
    EVIDENCE_REVIEW_PENDING = "EVIDENCE_REVIEW_PENDING"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    CHALLENGED = "CHALLENGED"
    ADDITIONAL_EVIDENCE_REQUESTED = "ADDITIONAL_EVIDENCE_REQUESTED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    CLOSED = "CLOSED"


class DisruptionDurationType(str, Enum):
    """Standardized duration categories for disruption analysis."""
    SHORT_INTERRUPTION = "SHORT_INTERRUPTION"  # < 1 hour
    EXTENDED_INTERRUPTION = "EXTENDED_INTERRUPTION"  # 1-4 hours
    PROLONGED_OUTAGE = "PROLONGED_OUTAGE"  # > 4 hours
    PARTIAL_DEGRADATION = "PARTIAL_DEGRADATION"
    INTERMITTENT_AVAILABILITY = "INTERMITTENT_AVAILABILITY"
    COMPLETE_UNAVAILABILITY = "COMPLETE_UNAVAILABILITY"


class FollowUpDestinationWorkflow(str, Enum):
    """Authoritative destination workflows for impact remediation handoffs."""
    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"
    PHASE_54_CORRECTIVE_ACTION = "PHASE_54_CORRECTIVE_ACTION"
    PHASE_55_EFFECTIVENESS_VERIFICATION = "PHASE_55_EFFECTIVENESS_VERIFICATION"
    PHASE_63_RISK_MANAGEMENT = "PHASE_63_RISK_MANAGEMENT"
    PHASE_67_GOVERNANCE_EXCEPTION = "PHASE_67_GOVERNANCE_EXCEPTION"
    PHASE_72_MANAGEMENT_REVIEW = "PHASE_72_MANAGEMENT_REVIEW"
    PHASE_73_DECISION_IMPLEMENTATION = "PHASE_73_DECISION_IMPLEMENTATION"
    PHASE_80_CONTINUITY_PLANNING = "PHASE_80_CONTINUITY_PLANNING"


class FollowUpStatus(str, Enum):
    """Status of an impact remediation follow-up handoff."""
    PROPOSED = "PROPOSED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

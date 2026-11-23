"""Phase 85: Clinical Safety Governance Resilience Role-Coverage Common Schemas and Constants.

Defines shared enums, types, and the mandatory clinical safety disclaimer for role-coverage
continuity, succession readiness, and authorized backup coordination.
"""

from enum import Enum

MANDATORY_ROLE_COVERAGE_DISCLAIMER = (
    "Role-coverage continuity and succession readiness records are administrative governance "
    "instruments and do NOT constitute professional licensing, clinical credentialing, "
    "medical competence certification, legal delegation, or authorization for clinical practice. "
    "Phase 85 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, "
    "73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, or 84."
)


class CriticalityTier(str, Enum):
    """Criticality level of a governance responsibility."""
    TIER_1_ESSENTIAL = "TIER_1_ESSENTIAL"
    TIER_2_CRITICAL = "TIER_2_CRITICAL"
    TIER_3_IMPORTANT = "TIER_3_IMPORTANT"
    TIER_4_SUPPORTING = "TIER_4_SUPPORTING"


class CoverageScope(str, Enum):
    """Organizational boundary of a governance responsibility."""
    ORGANIZATION = "ORGANIZATION"
    FACILITY = "FACILITY"
    DEPARTMENT = "DEPARTMENT"
    SERVICE = "SERVICE"
    CROSS_FUNCTIONAL = "CROSS_FUNCTIONAL"


class CoverageArrangementStatus(str, Enum):
    """Lifecycle states of a role-coverage arrangement."""
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    AUTHORIZATION_PENDING = "AUTHORIZATION_PENDING"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"
    CLOSED = "CLOSED"


class BackupDesignationPrecedence(str, Enum):
    """Designation hierarchy for backups."""
    PRIMARY_BACKUP = "PRIMARY_BACKUP"
    SECONDARY_BACKUP = "SECONDARY_BACKUP"
    TERTIARY_BACKUP = "TERTIARY_BACKUP"
    CONTINGENCY_BACKUP = "CONTINGENCY_BACKUP"


class BackupVerificationStatus(str, Enum):
    """Verification outcome of designated backup readiness."""
    VERIFIED = "VERIFIED"
    DEFICIENT = "DEFICIENT"
    EXPIRED = "EXPIRED"
    PENDING_REVIEW = "PENDING_REVIEW"


class DependencyRiskRating(str, Enum):
    """Risk rating for single-person dependency or personnel concentration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ScenarioType(str, Enum):
    """Stress testing scenario types for coverage resilience."""
    PRIMARY_ABSENT = "PRIMARY_ABSENT"
    CONCURRENT_ABSENCE = "CONCURRENT_ABSENCE"
    EXTENDED_DISRUPTION = "EXTENDED_DISRUPTION"
    MASS_UNAVAILABILITY = "MASS_UNAVAILABILITY"


class SuccessionReadinessTier(str, Enum):
    """Readiness timeline tier for successor candidates."""
    READY_NOW = "READY_NOW"
    READY_NEAR_TERM = "READY_NEAR_TERM"
    DEVELOPING = "DEVELOPING"
    EMERGING = "EMERGING"


class SuccessionPlanStatus(str, Enum):
    """Lifecycle states of a succession plan."""
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class HandoverStatus(str, Enum):
    """Lifecycle states of a governance responsibility handover."""
    INITIATED = "INITIATED"
    PENDING_INCOMING_ACKNOWLEDGEMENT = "PENDING_INCOMING_ACKNOWLEDGEMENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class CoverageGapStatus(str, Enum):
    """Remediation status of identified coverage gaps."""
    IDENTIFIED = "IDENTIFIED"
    ASSIGNED = "ASSIGNED"
    REMEDIATION_IN_PROGRESS = "REMEDIATION_IN_PROGRESS"
    VERIFIED_RESOLVED = "VERIFIED_RESOLVED"
    ESCALATED = "ESCALATED"
    WAIVED_WITH_JUSTIFICATION = "WAIVED_WITH_JUSTIFICATION"


class CoverageGapCategory(str, Enum):
    """Classification of governance role-coverage gaps."""
    NO_BACKUP_DESIGNATED = "NO_BACKUP_DESIGNATED"
    UNVERIFIED_BACKUP_CAPABILITY = "UNVERIFIED_BACKUP_CAPABILITY"
    EXPIRED_DELEGATION = "EXPIRED_DELEGATION"
    SINGLE_PERSON_BOTTLENECK = "SINGLE_PERSON_BOTTLENECK"
    CONCURRENT_ALLOCATION_CONFLICT = "CONCURRENT_ALLOCATION_CONFLICT"
    SUCCESSION_DEFICIT = "SUCCESSION_DEFICIT"

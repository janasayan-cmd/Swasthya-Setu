"""Phase 86: Clinical Safety Governance Resilience Resource Dependency — Common Schemas.

Shared enums, constants, and mandatory disclaimer for resource dependency mapping,
critical resource availability, and continuity capacity assurance.
"""

from enum import Enum

MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER = (
    "Resource dependency mapping, availability observations, and continuity capacity assessments "
    "are administrative governance instruments and do NOT constitute proof of operational resilience, "
    "infrastructure readiness, clinical safety certification, or regulatory compliance. "
    "Phase 86 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, "
    "73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, or 85. "
    "Resource availability must never be inferred from missing monitoring data."
)


class ResourceCategory(str, Enum):
    """Classification of organizational resources supporting governance capabilities."""
    CRITICAL_APPLICATION = "CRITICAL_APPLICATION"
    INFRASTRUCTURE_SERVICE = "INFRASTRUCTURE_SERVICE"
    HOSTING_CLOUD = "HOSTING_CLOUD"
    NETWORK_CONNECTIVITY = "NETWORK_CONNECTIVITY"
    IDENTITY_AUTHENTICATION = "IDENTITY_AUTHENTICATION"
    DATA_STORAGE = "DATA_STORAGE"
    CLINICAL_INFORMATION_SYSTEM = "CLINICAL_INFORMATION_SYSTEM"
    GOVERNANCE_DOCUMENT_REPOSITORY = "GOVERNANCE_DOCUMENT_REPOSITORY"
    COMMUNICATION_SERVICE = "COMMUNICATION_SERVICE"
    PHYSICAL_FACILITY = "PHYSICAL_FACILITY"
    ESSENTIAL_EQUIPMENT = "ESSENTIAL_EQUIPMENT"
    EXTERNAL_SERVICE_PROVIDER = "EXTERNAL_SERVICE_PROVIDER"
    THIRD_PARTY_INTEGRATION = "THIRD_PARTY_INTEGRATION"
    INFORMATION_EVIDENCE_SOURCE = "INFORMATION_EVIDENCE_SOURCE"
    OTHER = "OTHER"


class ResourceCriticality(str, Enum):
    """Criticality tier of a governance resource."""
    ESSENTIAL = "ESSENTIAL"
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    SUPPORTING = "SUPPORTING"


class ResourceLifecycleStatus(str, Enum):
    """Lifecycle state of a resource record."""
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
    DRAFT = "DRAFT"


class DependencyType(str, Enum):
    """Classification of a capability-to-resource dependency."""
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    SUPPORTING = "SUPPORTING"
    ALTERNATIVE = "ALTERNATIVE"
    CONDITIONAL = "CONDITIONAL"


class DependencyMappingStatus(str, Enum):
    """Approval lifecycle of a dependency mapping."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class ResourceAvailabilityStatus(str, Enum):
    """Availability status of a resource as observed or inferred."""
    AVAILABLE_VERIFIED = "AVAILABLE_VERIFIED"
    AVAILABLE_UNVERIFIED = "AVAILABLE_UNVERIFIED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"


class FallbackReadinessOutcome(str, Enum):
    """Assessment outcome for a proposed fallback resource."""
    READY_VERIFIED = "READY_VERIFIED"
    CONDITIONALLY_READY = "CONDITIONALLY_READY"
    NOT_READY = "NOT_READY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_ASSESSED = "NOT_ASSESSED"
    EXPIRED = "EXPIRED"


class ResourceGapCategory(str, Enum):
    """Classification of resource dependency gaps."""
    NO_RESOURCE_MAPPED = "NO_RESOURCE_MAPPED"
    UNVERIFIED_AVAILABILITY = "UNVERIFIED_AVAILABILITY"
    MISSING_FALLBACK = "MISSING_FALLBACK"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    CAPACITY_SHORTFALL = "CAPACITY_SHORTFALL"
    SINGLE_POINT_OF_FAILURE = "SINGLE_POINT_OF_FAILURE"
    PROVIDER_CONCENTRATION = "PROVIDER_CONCENTRATION"
    OWNERSHIP_UNKNOWN = "OWNERSHIP_UNKNOWN"
    CONFLICTING_OBSERVATIONS = "CONFLICTING_OBSERVATIONS"


class ResourceGapStatus(str, Enum):
    """Remediation status of a resource gap."""
    IDENTIFIED = "IDENTIFIED"
    ASSIGNED = "ASSIGNED"
    REMEDIATION_IN_PROGRESS = "REMEDIATION_IN_PROGRESS"
    ESCALATED = "ESCALATED"
    VERIFIED_RESOLVED = "VERIFIED_RESOLVED"
    WAIVED_WITH_JUSTIFICATION = "WAIVED_WITH_JUSTIFICATION"


class SPOFSeverity(str, Enum):
    """Severity of a single-point-of-failure finding."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

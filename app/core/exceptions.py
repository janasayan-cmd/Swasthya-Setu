"""Centralized error handling and exception definitions."""

from enum import Enum
from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx_var

logger = get_logger("app.exceptions")


class ErrorCode(str, Enum):
    """Standardized error codes for application responses."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    # Phase 8: Triage & SBAR Error Codes
    TRIAGE_INVALID_INPUT = "TRIAGE_INVALID_INPUT"
    TRIAGE_INSUFFICIENT_INFORMATION = "TRIAGE_INSUFFICIENT_INFORMATION"
    TRIAGE_RULE_ENGINE_UNAVAILABLE = "TRIAGE_RULE_ENGINE_UNAVAILABLE"
    TRIAGE_RULE_EVALUATION_FAILED = "TRIAGE_RULE_EVALUATION_FAILED"
    TRIAGE_RULE_NOT_SUPPORTED = "TRIAGE_RULE_NOT_SUPPORTED"
    TRIAGE_ASSESSMENT_NOT_FOUND = "TRIAGE_ASSESSMENT_NOT_FOUND"
    TRIAGE_ACCESS_DENIED = "TRIAGE_ACCESS_DENIED"
    SBAR_GENERATION_FAILED = "SBAR_GENERATION_FAILED"
    SBAR_VALIDATION_FAILED = "SBAR_VALIDATION_FAILED"
    SBAR_NOT_FOUND = "SBAR_NOT_FOUND"
    SYMPTOM_NOT_FOUND = "SYMPTOM_NOT_FOUND"

    # Phase 9: Care Plan & Discharge Error Codes
    DISCHARGE_NOT_FOUND = "DISCHARGE_NOT_FOUND"
    DISCHARGE_EXTRACTION_FAILED = "DISCHARGE_EXTRACTION_FAILED"
    DISCHARGE_ALREADY_VERIFIED = "DISCHARGE_ALREADY_VERIFIED"
    CARE_PLAN_NOT_FOUND = "CARE_PLAN_NOT_FOUND"
    CARE_PLAN_INVALID_INPUT = "CARE_PLAN_INVALID_INPUT"
    CARE_PLAN_UNVERIFIED_DISCHARGE = "CARE_PLAN_UNVERIFIED_DISCHARGE"

    # Phase 11: Hospital & Organization Network Error Codes
    ORGANIZATION_NOT_FOUND = "ORGANIZATION_NOT_FOUND"
    ORGANIZATION_ACCESS_DENIED = "ORGANIZATION_ACCESS_DENIED"
    ORGANIZATION_INACTIVE = "ORGANIZATION_INACTIVE"
    FACILITY_NOT_FOUND = "FACILITY_NOT_FOUND"
    FACILITY_ACCESS_DENIED = "FACILITY_ACCESS_DENIED"
    FACILITY_INACTIVE = "FACILITY_INACTIVE"
    FACILITY_ORGANIZATION_MISMATCH = "FACILITY_ORGANIZATION_MISMATCH"
    DEPARTMENT_NOT_FOUND = "DEPARTMENT_NOT_FOUND"
    CLINICIAN_ORGANIZATION_ACCESS_DENIED = "CLINICIAN_ORGANIZATION_ACCESS_DENIED"
    CLINICIAN_FACILITY_ACCESS_DENIED = "CLINICIAN_FACILITY_ACCESS_DENIED"
    INVALID_ORGANIZATION_FILTER = "INVALID_ORGANIZATION_FILTER"
    INVALID_FACILITY_FILTER = "INVALID_FACILITY_FILTER"

    # Phase 12: Facility Discovery & Transfer Error Codes
    FACILITY_DISCOVERY_DISABLED = "FACILITY_DISCOVERY_DISABLED"
    FACILITY_CAPABILITY_NOT_SUPPORTED = "FACILITY_CAPABILITY_NOT_SUPPORTED"
    INVALID_LATITUDE = "INVALID_LATITUDE"
    INVALID_LONGITUDE = "INVALID_LONGITUDE"
    INVALID_RADIUS = "INVALID_RADIUS"
    INCOMPLETE_LOCATION = "INCOMPLETE_LOCATION"
    PATIENT_ACCESS_DENIED = "PATIENT_ACCESS_DENIED"
    ENCOUNTER_ACCESS_DENIED = "ENCOUNTER_ACCESS_DENIED"
    TRANSFER_NOT_FOUND = "TRANSFER_NOT_FOUND"
    TRANSFER_ACCESS_DENIED = "TRANSFER_ACCESS_DENIED"
    TRANSFER_INVALID_STATE = "TRANSFER_INVALID_STATE"
    TRANSFER_NOT_ALLOWED = "TRANSFER_NOT_ALLOWED"
    TRANSFER_CONSENT_REQUIRED = "TRANSFER_CONSENT_REQUIRED"
    SENDING_FACILITY_INVALID = "SENDING_FACILITY_INVALID"
    RECEIVING_FACILITY_INVALID = "RECEIVING_FACILITY_INVALID"
    SBAR_ACCESS_DENIED = "SBAR_ACCESS_DENIED"
    CLINICAL_CONTEXT_NOT_AVAILABLE = "CLINICAL_CONTEXT_NOT_AVAILABLE"

    # Phase 13: Interoperability & Data Exchange Error Codes
    INTEROPERABILITY_DISABLED = "INTEROPERABILITY_DISABLED"
    UNSUPPORTED_INTEROPERABILITY_FORMAT = "UNSUPPORTED_INTEROPERABILITY_FORMAT"
    UNSUPPORTED_FHIR_VERSION = "UNSUPPORTED_FHIR_VERSION"
    UNSUPPORTED_RESOURCE_TYPE = "UNSUPPORTED_RESOURCE_TYPE"
    INVALID_EXTERNAL_RESOURCE = "INVALID_EXTERNAL_RESOURCE"
    INVALID_FHIR_RESOURCE = "INVALID_FHIR_RESOURCE"
    INVALID_HL7_MESSAGE = "INVALID_HL7_MESSAGE"
    EXTERNAL_IDENTITY_UNRESOLVED = "EXTERNAL_IDENTITY_UNRESOLVED"
    AMBIGUOUS_PATIENT_MATCH = "AMBIGUOUS_PATIENT_MATCH"
    INTEROPERABILITY_CONSENT_REQUIRED = "INTEROPERABILITY_CONSENT_REQUIRED"
    IMPORT_NOT_FOUND = "IMPORT_NOT_FOUND"
    IMPORT_FAILED = "IMPORT_FAILED"
    IMPORT_REJECTED = "IMPORT_REJECTED"
    EXPORT_NOT_FOUND = "EXPORT_NOT_FOUND"
    EXPORT_FAILED = "EXPORT_FAILED"
    EXPORT_NOT_AUTHORIZED = "EXPORT_NOT_AUTHORIZED"
    EXTERNAL_PROVIDER_UNAVAILABLE = "EXTERNAL_PROVIDER_UNAVAILABLE"
    EXTERNAL_PROVIDER_TIMEOUT = "EXTERNAL_PROVIDER_TIMEOUT"
    EXTERNAL_PROVIDER_AUTHENTICATION_FAILED = "EXTERNAL_PROVIDER_AUTHENTICATION_FAILED"
    RESOURCE_MAPPING_FAILED = "RESOURCE_MAPPING_FAILED"
    RESOURCE_VALIDATION_FAILED = "RESOURCE_VALIDATION_FAILED"

    # Phase 14: AI & Intelligence Layer Error Codes
    AI_DISABLED = "AI_DISABLED"
    AI_TASK_NOT_SUPPORTED = "AI_TASK_NOT_SUPPORTED"
    AI_TASK_NOT_FOUND = "AI_TASK_NOT_FOUND"
    AI_TASK_UNAUTHORIZED = "AI_TASK_UNAUTHORIZED"
    AI_PROVIDER_NOT_CONFIGURED = "AI_PROVIDER_NOT_CONFIGURED"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_PROVIDER_TIMEOUT = "AI_PROVIDER_TIMEOUT"
    AI_PROVIDER_AUTHENTICATION_FAILED = "AI_PROVIDER_AUTHENTICATION_FAILED"
    AI_PROVIDER_RATE_LIMITED = "AI_PROVIDER_RATE_LIMITED"
    AI_REQUEST_INVALID = "AI_REQUEST_INVALID"
    AI_OUTPUT_INVALID = "AI_OUTPUT_INVALID"
    AI_OUTPUT_SCHEMA_INVALID = "AI_OUTPUT_SCHEMA_INVALID"
    AI_GROUNDING_FAILED = "AI_GROUNDING_FAILED"
    AI_SOURCE_NOT_FOUND = "AI_SOURCE_NOT_FOUND"
    AI_CONTEXT_INSUFFICIENT = "AI_CONTEXT_INSUFFICIENT"
    AI_VERIFICATION_REQUIRED = "AI_VERIFICATION_REQUIRED"
    AI_TASK_FAILED = "AI_TASK_FAILED"
    AI_CONFIGURATION_INVALID = "AI_CONFIGURATION_INVALID"
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"

    # Phase 15: Security, Audit & Compliance Error Codes
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    ACCESS_DENIED = "ACCESS_DENIED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    CONSENT_INVALID = "CONSENT_INVALID"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    INVALID_INPUT = "INVALID_INPUT"
    FILE_TYPE_NOT_ALLOWED = "FILE_TYPE_NOT_ALLOWED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    SECURITY_CONFIGURATION_INVALID = "SECURITY_CONFIGURATION_INVALID"
    INTERNAL_SECURITY_ERROR = "INTERNAL_SECURITY_ERROR"
    PATH_TRAVERSAL_DETECTED = "PATH_TRAVERSAL_DETECTED"

    # Phase 22: Asynchronous Workflow & Event-Driven Error Codes
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_NOT_AUTHORIZED = "JOB_NOT_AUTHORIZED"
    JOB_ALREADY_COMPLETED = "JOB_ALREADY_COMPLETED"
    JOB_ALREADY_CANCELLED = "JOB_ALREADY_CANCELLED"
    JOB_NOT_RETRYABLE = "JOB_NOT_RETRYABLE"
    JOB_RETRY_LIMIT_REACHED = "JOB_RETRY_LIMIT_REACHED"
    JOB_PROCESSING_TIMEOUT = "JOB_PROCESSING_TIMEOUT"
    JOB_VALIDATION_FAILED = "JOB_VALIDATION_FAILED"
    JOB_EXECUTION_FAILED = "JOB_EXECUTION_FAILED"
    EVENT_INVALID = "EVENT_INVALID"
    EVENT_VERSION_UNSUPPORTED = "EVENT_VERSION_UNSUPPORTED"
    EVENT_DUPLICATE = "EVENT_DUPLICATE"
    EVENT_PUBLICATION_FAILED = "EVENT_PUBLICATION_FAILED"
    EVENT_CONSUMPTION_FAILED = "EVENT_CONSUMPTION_FAILED"
    WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_INVALID_STATE = "WORKFLOW_INVALID_STATE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"

    # Phase 24: Advanced Data Privacy, PHI Lifecycle & Data Governance Error Codes
    PRIVACY_POLICY_DENIED = "PRIVACY_POLICY_DENIED"
    PRIVACY_PURPOSE_REQUIRED = "PRIVACY_PURPOSE_REQUIRED"
    PRIVACY_PURPOSE_INVALID = "PRIVACY_PURPOSE_INVALID"
    RETENTION_POLICY_NOT_FOUND = "RETENTION_POLICY_NOT_FOUND"
    RETENTION_NOT_ELIGIBLE = "RETENTION_NOT_ELIGIBLE"
    DELETION_HELD_BY_LEGAL_HOLD = "DELETION_HELD_BY_LEGAL_HOLD"
    DELETION_DEPENDENCY_CONFLICT = "DELETION_DEPENDENCY_CONFLICT"
    DELETION_UNCERTAIN_POLICY = "DELETION_UNCERTAIN_POLICY"
    DELETION_FAILED = "DELETION_FAILED"
    DATA_EXPORT_NOT_FOUND = "DATA_EXPORT_NOT_FOUND"
    DATA_EXPORT_EXPIRED = "DATA_EXPORT_EXPIRED"
    DATA_EXPORT_FAILED = "DATA_EXPORT_FAILED"
    DATA_EXPORT_INVALID_SCOPE = "DATA_EXPORT_INVALID_SCOPE"
    DATA_EXPORT_SCOPE_UNAUTHORIZED = "DATA_EXPORT_SCOPE_UNAUTHORIZED"
    DEIDENTIFICATION_FAILED = "DEIDENTIFICATION_FAILED"
    PSEUDONYMIZATION_FAILED = "PSEUDONYMIZATION_FAILED"

    # Phase 25: Feature Flags, Configuration Governance & Rollout Error Codes
    FEATURE_DISABLED = "FEATURE_DISABLED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"
    CONFIGURATION_NOT_FOUND = "CONFIGURATION_NOT_FOUND"
    CONFIGURATION_DRIFT_DETECTED = "CONFIGURATION_DRIFT_DETECTED"
    ROLLOUT_EVALUATION_FAILED = "ROLLOUT_EVALUATION_FAILED"
    UNAUTHORIZED_CONFIGURATION_ACCESS = "UNAUTHORIZED_CONFIGURATION_ACCESS"

    # Phase 26: Data Quality, Clinical Record Integrity & Reconciliation Error Codes
    DATA_QUALITY_DISABLED = "DATA_QUALITY_DISABLED"
    DATA_QUALITY_FINDING_NOT_FOUND = "DATA_QUALITY_FINDING_NOT_FOUND"
    RECONCILIATION_NOT_FOUND = "RECONCILIATION_NOT_FOUND"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    REVIEW_NOT_AUTHORIZED = "REVIEW_NOT_AUTHORIZED"
    RESOLUTION_NOT_AUTHORIZED = "RESOLUTION_NOT_AUTHORIZED"
    RESOURCE_VERSION_CONFLICT = "RESOURCE_VERSION_CONFLICT"
    INVALID_RECONCILIATION_STATE = "INVALID_RECONCILIATION_STATE"
    INVALID_RESOLUTION = "INVALID_RESOLUTION"
    INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"
    EXTERNAL_DATA_CONFLICT = "EXTERNAL_DATA_CONFLICT"
    DUPLICATE_REVIEW_REQUIRED = "DUPLICATE_REVIEW_REQUIRED"

    # Phase 27: Administration, Support Operations & Controlled Backoffice
    ADMIN_ACCESS_DENIED = "ADMIN_ACCESS_DENIED"
    ADMIN_PERMISSION_REQUIRED = "ADMIN_PERMISSION_REQUIRED"
    ADMIN_RESOURCE_NOT_FOUND = "ADMIN_RESOURCE_NOT_FOUND"
    ADMIN_ACTION_NOT_ALLOWED = "ADMIN_ACTION_NOT_ALLOWED"
    ADMIN_ACTION_FAILED = "ADMIN_ACTION_FAILED"
    JOB_RETRY_NOT_ALLOWED = "JOB_RETRY_NOT_ALLOWED"
    JOB_CANCEL_NOT_ALLOWED = "JOB_CANCEL_NOT_ALLOWED"
    INTEGRATION_NOT_FOUND = "INTEGRATION_NOT_FOUND"
    INTEGRATION_TEST_NOT_ALLOWED = "INTEGRATION_TEST_NOT_ALLOWED"
    INTEGRATION_UNAVAILABLE = "INTEGRATION_UNAVAILABLE"
    INCIDENT_NOT_FOUND = "INCIDENT_NOT_FOUND"
    INCIDENT_INVALID_STATE = "INCIDENT_INVALID_STATE"
    CONFIGURATION_CHANGE_NOT_ALLOWED = "CONFIGURATION_CHANGE_NOT_ALLOWED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    SECURITY_EVENT_ACCESS_DENIED = "SECURITY_EVENT_ACCESS_DENIED"
    AUDIT_ACCESS_DENIED = "AUDIT_ACCESS_DENIED"
    SUPPORT_LOOKUP_NOT_ALLOWED = "SUPPORT_LOOKUP_NOT_ALLOWED"
    RESOURCE_ACCESS_DENIED = "RESOURCE_ACCESS_DENIED"

    # Phase 28: API Analytics, Usage Governance & Operational Intelligence
    ANALYTICS_DISABLED = "ANALYTICS_DISABLED"
    ANALYTICS_NOT_FOUND = "ANALYTICS_NOT_FOUND"
    ANALYTICS_QUERY_RANGE_EXCEEDED = "ANALYTICS_QUERY_RANGE_EXCEEDED"
    ANALYTICS_UNAVAILABLE = "ANALYTICS_UNAVAILABLE"
    ANALYTICS_ACCESS_DENIED = "ANALYTICS_ACCESS_DENIED"
    ANOMALY_NOT_FOUND = "ANOMALY_NOT_FOUND"

    # Phase 29: Notification, Communication & Event Delivery System
    NOTIFICATION_DISABLED = "NOTIFICATION_DISABLED"
    NOTIFICATION_NOT_FOUND = "NOTIFICATION_NOT_FOUND"
    NOTIFICATION_ACCESS_DENIED = "NOTIFICATION_ACCESS_DENIED"
    NOTIFICATION_PREFERENCE_CONFLICT = "NOTIFICATION_PREFERENCE_CONFLICT"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    TEMPLATE_RESOLUTION_ERROR = "TEMPLATE_RESOLUTION_ERROR"
    CHANNEL_DISABLED = "CHANNEL_DISABLED"
    PROVIDER_DELIVERY_ERROR = "PROVIDER_DELIVERY_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    NOTIFICATION_RATE_LIMIT_EXCEEDED = "NOTIFICATION_RATE_LIMIT_EXCEEDED"
    DUPLICATE_NOTIFICATION = "DUPLICATE_NOTIFICATION"
    DELIVERY_NOT_FOUND = "DELIVERY_NOT_FOUND"
    UNAUTHORIZED_CLINICAL_CONTENT = "UNAUTHORIZED_CLINICAL_CONTENT"

    # Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval
    SEARCH_DISABLED = "SEARCH_DISABLED"
    INVALID_SEARCH_QUERY = "INVALID_SEARCH_QUERY"
    SEARCH_QUERY_TOO_LONG = "SEARCH_QUERY_TOO_LONG"
    SEARCH_QUERY_TOO_SHORT = "SEARCH_QUERY_TOO_SHORT"
    UNSUPPORTED_SEARCH_RESOURCE_TYPE = "UNSUPPORTED_SEARCH_RESOURCE_TYPE"
    UNSUPPORTED_SEARCH_FILTER = "UNSUPPORTED_SEARCH_FILTER"
    UNSUPPORTED_SORT_FIELD = "UNSUPPORTED_SORT_FIELD"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    INVALID_PAGINATION = "INVALID_PAGINATION"
    SEARCH_NOT_AUTHORIZED = "SEARCH_NOT_AUTHORIZED"
    PATIENT_SEARCH_NOT_AUTHORIZED = "PATIENT_SEARCH_NOT_AUTHORIZED"
    RESOURCE_SEARCH_NOT_AUTHORIZED = "RESOURCE_SEARCH_NOT_AUTHORIZED"
    SEARCH_PROVIDER_UNAVAILABLE = "SEARCH_PROVIDER_UNAVAILABLE"
    SEARCH_PROVIDER_TIMEOUT = "SEARCH_PROVIDER_TIMEOUT"
    SEARCH_INDEX_UNAVAILABLE = "SEARCH_INDEX_UNAVAILABLE"
    SEARCH_INDEX_STALE = "SEARCH_INDEX_STALE"
    SEARCH_TIMEOUT = "SEARCH_TIMEOUT"
    SEARCH_FAILED = "SEARCH_FAILED"
    SEARCH_RESULT_NOT_FOUND = "SEARCH_RESULT_NOT_FOUND"


class AppException(Exception):
    """Base application exception for all domain and operational errors."""

    def __init__(
        self,
        code: ErrorCode | str = ErrorCode.INTERNAL_ERROR,
        message: str = "An unexpected error occurred.",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code if isinstance(code, str) else code.value
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundException(AppException):
    """Resource not found exception (HTTP 404)."""

    def __init__(self, message: str = "Resource not found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class UnauthorizedException(AppException):
    """Authentication required or failed exception (HTTP 401)."""

    def __init__(self, message: str = "Authentication required.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenException(AppException):
    """Action forbidden exception (HTTP 403)."""

    def __init__(self, message: str = "Access forbidden.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ConflictException(AppException):
    """Conflict with current state exception (HTTP 409)."""

    def __init__(self, message: str = "Resource conflict.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationException(AppException):
    """Input validation exception (HTTP 422)."""

    def __init__(self, message: str = "Validation failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


class ServiceUnavailableException(AppException):
    """Service unavailable exception (HTTP 503)."""

    def __init__(self, message: str = "Service temporarily unavailable.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


# Phase 11: Hospital & Organization Network Exceptions
class OrganizationNotFoundException(AppException):
    """Organization not found exception (HTTP 404)."""

    def __init__(self, message: str = "The requested organization could not be found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.ORGANIZATION_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class OrganizationAccessDeniedException(AppException):
    """Organization access denied exception (HTTP 403)."""

    def __init__(self, message: str = "Access to the requested organization is denied.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.ORGANIZATION_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class OrganizationInactiveException(AppException):
    """Organization inactive or suspended exception (HTTP 400)."""

    def __init__(self, message: str = "The organization is inactive or suspended and cannot be accessed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.ORGANIZATION_INACTIVE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class FacilityNotFoundException(AppException):
    """Facility not found exception (HTTP 404)."""

    def __init__(self, message: str = "The requested facility could not be found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.FACILITY_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class FacilityAccessDeniedException(AppException):
    """Facility access denied exception (HTTP 403)."""

    def __init__(self, message: str = "Access to the requested facility is denied.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.FACILITY_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class FacilityInactiveException(AppException):
    """Facility inactive or suspended exception (HTTP 400)."""

    def __init__(self, message: str = "The facility is inactive or suspended and cannot be accessed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.FACILITY_INACTIVE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class FacilityOrganizationMismatchException(AppException):
    """Facility does not belong to the specified organization exception (HTTP 400)."""

    def __init__(self, message: str = "The facility does not belong to the specified organization.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.FACILITY_ORGANIZATION_MISMATCH,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class DepartmentNotFoundException(AppException):
    """Department not found exception (HTTP 404)."""

    def __init__(self, message: str = "The requested department could not be found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.DEPARTMENT_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ClinicianOrganizationAccessDeniedException(AppException):
    """Clinician organization access denied exception (HTTP 403)."""

    def __init__(self, message: str = "Clinician does not have authorized access to this organization.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.CLINICIAN_ORGANIZATION_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ClinicianFacilityAccessDeniedException(AppException):
    """Clinician facility access denied exception (HTTP 403)."""

    def __init__(self, message: str = "Clinician does not have authorized access to this facility.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.CLINICIAN_FACILITY_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class InvalidOrganizationFilterException(AppException):
    """Invalid organization filter exception (HTTP 400)."""

    def __init__(self, message: str = "Invalid organization filter parameters provided.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_ORGANIZATION_FILTER,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InvalidFacilityFilterException(AppException):
    """Invalid facility filter exception (HTTP 400)."""

    def __init__(self, message: str = "Invalid facility filter parameters provided.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_FACILITY_FILTER,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


# Phase 12: Facility Discovery & Transfer Exceptions
class FacilityDiscoveryDisabledException(AppException):
    """Facility discovery feature disabled exception (HTTP 400)."""

    def __init__(self, message: str = "Facility discovery service is currently disabled.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.FACILITY_DISCOVERY_DISABLED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class FacilityCapabilityNotSupportedException(AppException):
    """Facility capability requirement not supported (HTTP 400)."""

    def __init__(self, message: str = "The requested facility capability is not supported.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.FACILITY_CAPABILITY_NOT_SUPPORTED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InvalidLatitudeException(AppException):
    """Latitude out of range [-90, 90] (HTTP 400)."""

    def __init__(self, message: str = "Latitude must be between -90 and 90 degrees.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_LATITUDE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InvalidLongitudeException(AppException):
    """Longitude out of range [-180, 180] (HTTP 400)."""

    def __init__(self, message: str = "Longitude must be between -180 and 180 degrees.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_LONGITUDE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InvalidRadiusException(AppException):
    """Radius invalid or exceeds maximum configured boundary (HTTP 400)."""

    def __init__(self, message: str = "Radius must be a positive number within allowable limit.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_RADIUS,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class IncompleteLocationException(AppException):
    """Latitude and Longitude must both be provided (HTTP 400)."""

    def __init__(self, message: str = "Both latitude and longitude coordinates must be provided together.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INCOMPLETE_LOCATION,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class PatientAccessDeniedException(AppException):
    """Caller does not have permission to access patient clinical data (HTTP 403)."""

    def __init__(self, message: str = "Access to patient data is denied.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.PATIENT_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class EncounterAccessDeniedException(AppException):
    """Caller does not have permission to access encounter data (HTTP 403)."""

    def __init__(self, message: str = "Access to encounter is denied.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.ENCOUNTER_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class TransferNotFoundException(AppException):
    """Transfer request not found (HTTP 404)."""

    def __init__(self, message: str = "Transfer request not found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.TRANSFER_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class TransferAccessDeniedException(AppException):
    """Access to transfer request denied (HTTP 403)."""

    def __init__(self, message: str = "Access to transfer request is denied.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.TRANSFER_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class TransferInvalidStateException(AppException):
    """Invalid transfer status transition attempted (HTTP 400)."""

    def __init__(self, message: str = "Invalid transfer state transition.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.TRANSFER_INVALID_STATE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class TransferNotAllowedException(AppException):
    """Transfer not permitted under current conditions (HTTP 400)."""

    def __init__(self, message: str = "Transfer operation is not allowed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.TRANSFER_NOT_ALLOWED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class TransferConsentRequiredException(AppException):
    """Transfer requires patient consent to share clinical data (HTTP 403)."""

    def __init__(self, message: str = "Required patient consent has not been provided for this transfer.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.TRANSFER_CONSENT_REQUIRED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class SendingFacilityInvalidException(AppException):
    """Sending facility is invalid, inactive, or unauthorized (HTTP 400)."""

    def __init__(self, message: str = "The sending facility is invalid or not operational.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.SENDING_FACILITY_INVALID,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class ReceivingFacilityInvalidException(AppException):
    """Receiving facility is invalid, inactive, or identical to sending facility (HTTP 400)."""

    def __init__(self, message: str = "The receiving facility is invalid or not operational.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.RECEIVING_FACILITY_INVALID,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class SBARAccessDeniedException(AppException):
    """Caller not authorized to access SBAR report for transfer attachment (HTTP 403)."""

    def __init__(self, message: str = "Access to SBAR report for transfer is denied.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.SBAR_ACCESS_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ClinicalContextNotAvailableException(AppException):
    """Requested clinical context reference not found or unavailable (HTTP 404)."""

    def __init__(self, message: str = "Clinical context reference for transfer could not be found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.CLINICAL_CONTEXT_NOT_AVAILABLE,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


# ============================================================================
# Phase 13: Interoperability & Healthcare Data Exchange Exceptions
# ============================================================================

class InteroperabilityDisabledException(AppException):
    """Interoperability feature disabled by system configuration (HTTP 503)."""

    def __init__(self, message: str = "Interoperability data exchange is currently disabled by policy.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INTEROPERABILITY_DISABLED,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class UnsupportedInteroperabilityFormatException(AppException):
    """Interoperability data format not supported (HTTP 400)."""

    def __init__(self, message: str = "Unsupported interoperability data exchange format.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.UNSUPPORTED_INTEROPERABILITY_FORMAT,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class UnsupportedFHIRVersionException(AppException):
    """Requested FHIR version not supported (HTTP 400)."""

    def __init__(self, message: str = "Unsupported FHIR version.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.UNSUPPORTED_FHIR_VERSION,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class UnsupportedResourceTypeException(AppException):
    """Resource type not supported for interoperability exchange (HTTP 400)."""

    def __init__(self, message: str = "Unsupported resource type for interoperability exchange.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.UNSUPPORTED_RESOURCE_TYPE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InvalidExternalResourceException(AppException):
    """External resource malformed or invalid (HTTP 400)."""

    def __init__(self, message: str = "Invalid external healthcare resource payload.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_EXTERNAL_RESOURCE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InvalidFHIRResourceException(AppException):
    """FHIR resource does not conform to FHIR R4 schema invariants (HTTP 400)."""

    def __init__(self, message: str = "Invalid FHIR resource representation.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_FHIR_RESOURCE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class InvalidHL7MessageException(AppException):
    """HL7 message malformed or unsupported (HTTP 400)."""

    def __init__(self, message: str = "Invalid or malformed HL7 message.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_HL7_MESSAGE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class ExternalIdentityUnresolvedException(AppException):
    """External patient identity cannot be resolved to a HealthSetu patient (HTTP 422)."""

    def __init__(self, message: str = "External patient identity could not be resolved.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_IDENTITY_UNRESOLVED,
            message=message,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


class AmbiguousPatientMatchException(AppException):
    """Multiple candidate patients found without deterministic resolution (HTTP 409)."""

    def __init__(self, message: str = "Ambiguous patient match. Multiple candidates match external identifiers.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AMBIGUOUS_PATIENT_MATCH,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class InteroperabilityConsentRequiredException(AppException):
    """Explicit patient consent required for external data exchange (HTTP 403)."""

    def __init__(self, message: str = "Patient consent is required for interoperability data exchange.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INTEROPERABILITY_CONSENT_REQUIRED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ImportNotFoundException(AppException):
    """Import record not found (HTTP 404)."""

    def __init__(self, message: str = "Interoperability import record not found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.IMPORT_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ImportFailedException(AppException):
    """Interoperability import processing failure (HTTP 500)."""

    def __init__(self, message: str = "Interoperability import operation failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.IMPORT_FAILED,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ImportRejectedException(AppException):
    """Import rejected due to validation or safety constraints (HTTP 422)."""

    def __init__(self, message: str = "Interoperability import rejected.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.IMPORT_REJECTED,
            message=message,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


class ExportNotFoundException(AppException):
    """Export record not found (HTTP 404)."""

    def __init__(self, message: str = "Interoperability export record not found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EXPORT_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ExportFailedException(AppException):
    """Interoperability export processing failure (HTTP 500)."""

    def __init__(self, message: str = "Interoperability export operation failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EXPORT_FAILED,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ExportNotAuthorizedException(AppException):
    """Caller not authorized for requested export scope (HTTP 403)."""

    def __init__(self, message: str = "Interoperability export not authorized for requested scope.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EXPORT_NOT_AUTHORIZED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ExternalProviderUnavailableException(AppException):
    """External interoperability service/endpoint unavailable (HTTP 503)."""

    def __init__(self, message: str = "External healthcare interoperability provider is currently unavailable.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_PROVIDER_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class ExternalProviderTimeoutException(AppException):
    """External provider request timed out (HTTP 504)."""

    def __init__(self, message: str = "External healthcare interoperability provider request timed out.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_PROVIDER_TIMEOUT,
            message=message,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=details,
        )


class ExternalProviderAuthenticationFailedException(AppException):
    """Authentication with external provider failed (HTTP 502)."""

    def __init__(self, message: str = "External interoperability provider authentication failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_PROVIDER_AUTHENTICATION_FAILED,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class ResourceMappingFailedException(AppException):
    """Resource mapping to HealthSetu domain representation failed (HTTP 422)."""

    def __init__(self, message: str = "Failed to map external healthcare resource to internal model.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.RESOURCE_MAPPING_FAILED,
            message=message,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


class ResourceValidationFailedException(AppException):
    """Resource failed validation rules (HTTP 422)."""

    def __init__(self, message: str = "Healthcare resource failed validation.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.RESOURCE_VALIDATION_FAILED,
            message=message,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


# Phase 14: AI & Intelligence Layer Exceptions
class AIDisabledException(AppException):
    """AI orchestration layer is disabled (HTTP 503)."""

    def __init__(self, message: str = "AI capabilities are currently disabled by configuration.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_DISABLED,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class AITaskNotSupportedException(AppException):
    """Requested AI task type is not approved or supported (HTTP 400)."""

    def __init__(self, message: str = "The specified AI task type is not supported.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_TASK_NOT_SUPPORTED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AITaskNotFoundException(AppException):
    """AI task could not be found (HTTP 404)."""

    def __init__(self, message: str = "The requested AI task was not found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_TASK_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class AITaskUnauthorizedException(AppException):
    """User is not authorized for this AI task or clinical resource (HTTP 403)."""

    def __init__(self, message: str = "You are not authorized to execute this AI task.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_TASK_UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class AIProviderNotConfiguredException(AppException):
    """Configured AI provider is missing required keys or parameters (HTTP 500)."""

    def __init__(self, message: str = "AI provider is not configured properly.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_PROVIDER_NOT_CONFIGURED,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class AIProviderUnavailableException(AppException):
    """Underlying AI provider returned 5xx or is unreachable (HTTP 503)."""

    def __init__(self, message: str = "AI provider service is currently unavailable.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_PROVIDER_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class AIProviderTimeoutException(AppException):
    """Underlying AI provider request timed out (HTTP 504)."""

    def __init__(self, message: str = "AI provider request timed out.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_PROVIDER_TIMEOUT,
            message=message,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=details,
        )


class AIProviderAuthenticationException(AppException):
    """AI provider rejected authentication credentials (HTTP 502)."""

    def __init__(self, message: str = "AI provider authentication failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_PROVIDER_AUTHENTICATION_FAILED,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


AIProviderAuthenticationFailedException = AIProviderAuthenticationException



class AIProviderRateLimitedException(AppException):
    """Provider rate limit or quota exceeded (HTTP 429)."""

    def __init__(self, message: str = "AI provider rate limit reached. Please retry later.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_PROVIDER_RATE_LIMITED,
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class AIRequestInvalidException(AppException):
    """Invalid AI task parameters or malformed input payload (HTTP 400)."""

    def __init__(self, message: str = "Invalid AI request parameters.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_REQUEST_INVALID,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AIOutputInvalidException(AppException):
    """AI generated empty or structurally malformed response (HTTP 502)."""

    def __init__(self, message: str = "AI provider returned malformed output.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_OUTPUT_INVALID,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class AIOutputSchemaInvalidException(AppException):
    """AI output failed strict Pydantic task schema validation (HTTP 502)."""

    def __init__(self, message: str = "AI output failed schema validation requirements.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_OUTPUT_SCHEMA_INVALID,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class AIGroundingFailedException(AppException):
    """AI output contained ungrounded or fabricated clinical claims (HTTP 422)."""

    def __init__(self, message: str = "AI output failed source grounding validation.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_GROUNDING_FAILED,
            message=message,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


class AISourceNotFoundException(AppException):
    """The source document, encounter, or clinical record for AI processing was not found (HTTP 404)."""

    def __init__(self, message: str = "The source entity for AI processing was not found.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_SOURCE_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class AIContextInsufficientException(AppException):
    """Supplied context does not contain sufficient clinical information for task (HTTP 400)."""

    def __init__(self, message: str = "Provided source information is insufficient for AI task.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_CONTEXT_INSUFFICIENT,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AIVerificationRequiredException(AppException):
    """Attempted to use unverified AI output in active clinical operations without clinician review (HTTP 409)."""

    def __init__(self, message: str = "AI output requires clinical review before verification.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_VERIFICATION_REQUIRED,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class AITaskFailedException(AppException):
    """General AI task execution failure (HTTP 500)."""

    def __init__(self, message: str = "AI task execution failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_TASK_FAILED,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class AIConfigurationInvalidException(AppException):
    """Invalid AI configuration or unsafe parameter combination (HTTP 500)."""

    def __init__(self, message: str = "Invalid AI layer configuration.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.AI_CONFIGURATION_INVALID,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class PromptInjectionDetectedException(AppException):
    """Prompt injection or adversarial instruction pattern detected in untrusted content (HTTP 400)."""

    def __init__(self, message: str = "Potential prompt injection pattern detected in input text.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.PROMPT_INJECTION_DETECTED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )

class SSRFBlockedException(AppException):
    """Raised when an outbound request is blocked by SSRF defenses (HTTP 403)."""

    def __init__(
        self,
        message: str = "Request to this external address is blocked for security reasons.",
        details: Any = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.SSRF_BLOCKED,
            message=message,
            status_code=403,
            details=details,
        )


class PathTraversalDetectedException(AppException):
    """Raised when a directory or path traversal sequence is detected (HTTP 400)."""

    def __init__(
        self,
        message: str = "Path traversal sequence detected in request.",
        details: Any = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.PATH_TRAVERSAL_DETECTED,
            message=message,
            status_code=400,
            details=details,
        )


# Phase 22: Asynchronous Workflow & Job Exceptions
class JobNotFoundException(AppException):
    """Job record not found (HTTP 404)."""

    def __init__(self, job_id: str, message: str | None = None) -> None:
        super().__init__(
            code=ErrorCode.JOB_NOT_FOUND,
            message=message or f"Asynchronous job '{job_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"job_id": job_id},
        )


class JobNotAuthorizedException(AppException):
    """User not authorized to access or modify this job (HTTP 403)."""

    def __init__(self, message: str = "Access to requested job is forbidden.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.JOB_NOT_AUTHORIZED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class JobAlreadyCompletedException(AppException):
    """Attempted to cancel or mutate a job that is already completed (HTTP 409)."""

    def __init__(self, job_id: str, message: str | None = None) -> None:
        super().__init__(
            code=ErrorCode.JOB_ALREADY_COMPLETED,
            message=message or f"Job '{job_id}' has already completed and cannot be modified.",
            status_code=status.HTTP_409_CONFLICT,
            details={"job_id": job_id},
        )


class JobAlreadyCancelledException(AppException):
    """Attempted to cancel or run a job that is already cancelled (HTTP 409)."""

    def __init__(self, job_id: str, message: str | None = None) -> None:
        super().__init__(
            code=ErrorCode.JOB_ALREADY_CANCELLED,
            message=message or f"Job '{job_id}' is already cancelled.",
            status_code=status.HTTP_409_CONFLICT,
            details={"job_id": job_id},
        )


class JobExecutionException(AppException):
    """Unrecoverable failure during background job execution (HTTP 500)."""

    def __init__(self, job_id: str, message: str = "Background job execution failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.JOB_EXECUTION_FAILED,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details or {"job_id": job_id},
        )


class JobProcessingTimeoutException(AppException):
    """Job processing runtime exceeded configured timeout limit (HTTP 504)."""

    def __init__(self, job_id: str, timeout_seconds: float) -> None:
        super().__init__(
            code=ErrorCode.JOB_PROCESSING_TIMEOUT,
            message=f"Job '{job_id}' timed out after {timeout_seconds}s.",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details={"job_id": job_id, "timeout_seconds": timeout_seconds},
        )


class WorkflowNotFoundException(AppException):
    """Multi-step workflow not found (HTTP 404)."""

    def __init__(self, workflow_id: str, message: str | None = None) -> None:
        super().__init__(
            code=ErrorCode.WORKFLOW_NOT_FOUND,
            message=message or f"Workflow '{workflow_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"workflow_id": workflow_id},
        )


class WorkflowInvalidStateException(AppException):
    """Workflow state transition is illegal or invalid (HTTP 409)."""

    def __init__(self, workflow_id: str, current_state: str, attempted_action: str) -> None:
        super().__init__(
            code=ErrorCode.WORKFLOW_INVALID_STATE,
            message=f"Cannot perform '{attempted_action}' on workflow '{workflow_id}' in state '{current_state}'.",
            status_code=status.HTTP_409_CONFLICT,
            details={"workflow_id": workflow_id, "current_state": current_state},
        )


class EventValidationException(AppException):
    """Domain event contract or version schema violation (HTTP 422)."""

    def __init__(self, message: str = "Invalid domain event contract or unsupported event version.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.EVENT_INVALID,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class IdempotencyConflictException(AppException):
    """Duplicate concurrent operation detected under same idempotency key (HTTP 409)."""

    def __init__(self, idempotency_key: str, message: str | None = None) -> None:
        super().__init__(
            code=ErrorCode.IDEMPOTENCY_CONFLICT,
            message=message or f"Concurrent request already in progress for idempotency key '{idempotency_key}'.",
            status_code=status.HTTP_409_CONFLICT,
            details={"idempotency_key": idempotency_key},
        )


# ---------------------------------------------------------------------------
# Phase 24: Advanced Data Privacy, Retention & Governance Exceptions
# ---------------------------------------------------------------------------

class PrivacyPolicyDeniedException(AppException):
    """Access denied due to privacy policy, consent limitation, or classification boundary (HTTP 403)."""

    def __init__(self, message: str = "Access denied by privacy and data governance policy.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.PRIVACY_POLICY_DENIED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class PrivacyPurposeRequiredException(AppException):
    """Processing purpose missing or invalid for sensitive data access (HTTP 400)."""

    def __init__(self, message: str = "An authorized processing purpose is required for this operation.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.PRIVACY_PURPOSE_REQUIRED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class RetentionPolicyNotFoundException(AppException):
    """No active retention policy found for target resource or data classification (HTTP 404)."""

    def __init__(self, resource_type: str, message: str | None = None) -> None:
        super().__init__(
            code=ErrorCode.RETENTION_POLICY_NOT_FOUND,
            message=message or f"No retention policy configured for resource type '{resource_type}'.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type},
        )


class RetentionNotEligibleException(AppException):
    """Resource is not currently eligible for retention archival or deletion (HTTP 400)."""

    def __init__(self, resource_id: str, reason: str) -> None:
        super().__init__(
            code=ErrorCode.RETENTION_NOT_ELIGIBLE,
            message=f"Resource '{resource_id}' is not eligible for lifecycle transition: {reason}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"resource_id": resource_id, "reason": reason},
        )


class LegalHoldActiveException(AppException):
    """Deletion or modification blocked due to active legal, investigation, or audit hold (HTTP 409)."""

    def __init__(self, resource_id: str, hold_ids: list[str]) -> None:
        super().__init__(
            code=ErrorCode.DELETION_HELD_BY_LEGAL_HOLD,
            message=f"Resource '{resource_id}' cannot be deleted because one or more active holds exist.",
            status_code=status.HTTP_409_CONFLICT,
            details={"resource_id": resource_id, "active_holds": hold_ids},
        )


class DeletionDependencyConflictException(AppException):
    """Deletion cannot proceed due to unresolved child clinical dependencies (HTTP 409)."""

    def __init__(self, resource_id: str, dependent_types: list[str]) -> None:
        super().__init__(
            code=ErrorCode.DELETION_DEPENDENCY_CONFLICT,
            message=f"Resource '{resource_id}' has dependent records that must be resolved first: {', '.join(dependent_types)}",
            status_code=status.HTTP_409_CONFLICT,
            details={"resource_id": resource_id, "dependent_types": dependent_types},
        )


class DeletionUncertainPolicyException(AppException):
    """Deletion refused under fail-closed privacy invariant when policy is uncertain or missing (HTTP 400)."""

    def __init__(self, resource_id: str, message: str = "Deletion refused: privacy retention policy is uncertain or undefined.") -> None:
        super().__init__(
            code=ErrorCode.DELETION_UNCERTAIN_POLICY,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"resource_id": resource_id},
        )


class DataExportNotFoundException(AppException):
    """Patient data export job or artifact not found (HTTP 404)."""

    def __init__(self, export_id: str) -> None:
        super().__init__(
            code=ErrorCode.DATA_EXPORT_NOT_FOUND,
            message=f"Data export '{export_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"export_id": export_id},
        )


class DataExportExpiredException(AppException):
    """Patient data export download token or artifact has expired (HTTP 410)."""

    def __init__(self, export_id: str) -> None:
        super().__init__(
            code=ErrorCode.DATA_EXPORT_EXPIRED,
            message=f"Data export '{export_id}' has expired and is no longer available for download.",
            status_code=status.HTTP_410_GONE,
            details={"export_id": export_id},
        )


class DataExportUnauthorizedException(AppException):
    """Unauthorized attempt to access or initiate patient data export (HTTP 403)."""

    def __init__(self, message: str = "Not authorized to export data for this patient.") -> None:
        super().__init__(
            code=ErrorCode.DATA_EXPORT_SCOPE_UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class DeidentificationFailedException(AppException):
    """De-identification transformation failed (HTTP 500)."""

    def __init__(self, message: str = "De-identification operation failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.DEIDENTIFICATION_FAILED,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class FeatureDisabledException(AppException):
    """Requested feature or clinical workflow is currently disabled (HTTP 403 or 503)."""

    def __init__(
        self,
        feature_name: str,
        message: str | None = None,
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
        details: Any = None,
    ) -> None:
        msg = message or f"Feature '{feature_name}' is currently disabled or unavailable."
        detail_payload = {"feature": feature_name}
        if details and isinstance(details, dict):
            detail_payload.update(details)
        super().__init__(
            code=ErrorCode.FEATURE_DISABLED,
            message=msg,
            status_code=status_code,
            details=detail_payload,
        )


class KillSwitchActiveException(AppException):
    """Operational safety kill switch is actively preventing processing (HTTP 503)."""

    def __init__(
        self,
        kill_switch: str,
        message: str | None = None,
        reason: str | None = None,
    ) -> None:
        msg = message or f"Operational kill switch '{kill_switch}' is active. Processing is temporarily halted."
        super().__init__(
            code=ErrorCode.KILL_SWITCH_ACTIVE,
            message=msg,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"kill_switch": kill_switch, "reason": reason or "Emergency operational halt"},
        )


class ConfigurationInvalidException(AppException):
    """Configuration fails schema, environment or conditional dependency validation (HTTP 422)."""

    def __init__(self, message: str = "Configuration validation failed.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.CONFIGURATION_INVALID,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ConfigurationNotFoundException(AppException):
    """Configuration key or feature flag not found (HTTP 404)."""

    def __init__(self, key: str) -> None:
        super().__init__(
            code=ErrorCode.CONFIGURATION_NOT_FOUND,
            message=f"Configuration key or feature flag '{key}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"key": key},
        )


class ConfigurationDriftException(AppException):
    """Detected configuration drift between runtime settings and approved baseline (HTTP 409)."""

    def __init__(self, message: str = "Configuration drift detected.", details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.CONFIGURATION_DRIFT_DETECTED,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class DataQualityFindingNotFoundException(AppException):
    """Data quality finding was not found (HTTP 404)."""

    def __init__(self, finding_id: str) -> None:
        super().__init__(
            code=ErrorCode.DATA_QUALITY_FINDING_NOT_FOUND,
            message=f"Data quality finding '{finding_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"finding_id": finding_id},
        )


class ReconciliationNotFoundException(AppException):
    """Reconciliation record was not found (HTTP 404)."""

    def __init__(self, reconciliation_id: str) -> None:
        super().__init__(
            code=ErrorCode.RECONCILIATION_NOT_FOUND,
            message=f"Reconciliation record '{reconciliation_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"reconciliation_id": reconciliation_id},
        )


class ResourceVersionConflictException(AppException):
    """Optimistic concurrency version conflict during review/resolution (HTTP 409)."""

    def __init__(
        self,
        resource_type: str = "resource",
        resource_id: str = "unknown",
        expected_version: Any = None,
        current_version: Any = None,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = f"Underlying clinical resource '{resource_type}:{resource_id}' was modified concurrently."
        super().__init__(
            code=ErrorCode.RESOURCE_VERSION_CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "expected_version": expected_version,
                "current_version": current_version,
            },
        )



class InvalidResolutionException(AppException):
    """Provided resolution decision is invalid for current finding state (HTTP 422)."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_RESOLUTION,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class InsufficientProvenanceException(AppException):
    """Clinical record lacks mandatory provenance metadata (HTTP 422)."""

    def __init__(self, resource_type: str, resource_id: str, reason: str = "Missing source or verification metadata.") -> None:
        super().__init__(
            code=ErrorCode.INSUFFICIENT_PROVENANCE,
            message=f"Clinical resource '{resource_type}:{resource_id}' lacks sufficient provenance: {reason}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"resource_type": resource_type, "resource_id": resource_id, "reason": reason},
        )


# ---------------------------------------------------------------------------
# Phase 27: Administration, Support Operations & Controlled Backoffice Exceptions
# ---------------------------------------------------------------------------

class AdminAccessDeniedException(ForbiddenException):
    """Administrative access denied (HTTP 403)."""

    def __init__(self, message: str = "Administrative access denied. Caller lacks operator authorization.", details: Any = None) -> None:
        super().__init__(message=message, details=details)
        self.code = ErrorCode.ADMIN_ACCESS_DENIED.value


class AdminPermissionRequiredException(ForbiddenException):
    """Required administrative capability permission missing (HTTP 403)."""

    def __init__(self, permission: str, details: Any = None) -> None:
        super().__init__(
            message=f"Administrative capability '{permission}' required for this operational action.",
            details=details or {"required_permission": permission},
        )
        self.code = ErrorCode.ADMIN_PERMISSION_REQUIRED.value


class AdminResourceNotFoundException(NotFoundException):
    """Administrative resource not found (HTTP 404)."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(
            message=f"Administrative resource '{resource_type}' with ID '{resource_id}' was not found.",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )
        self.code = ErrorCode.ADMIN_RESOURCE_NOT_FOUND.value


class AdminActionNotAllowedException(AppException):
    """Operational action not permitted under system safety invariants (HTTP 400)."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.ADMIN_ACTION_NOT_ALLOWED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class JobRetryNotAllowedException(AppException):
    """Job cannot be safely retried under idempotency / state rules (HTTP 400)."""

    def __init__(self, job_id: str, reason: str) -> None:
        super().__init__(
            code=ErrorCode.JOB_RETRY_NOT_ALLOWED,
            message=f"Job '{job_id}' cannot be retried: {reason}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"job_id": job_id, "reason": reason},
        )


class JobCancelNotAllowedException(AppException):
    """Job cannot be cancelled in its current state (HTTP 400)."""

    def __init__(self, job_id: str, reason: str) -> None:
        super().__init__(
            code=ErrorCode.JOB_CANCEL_NOT_ALLOWED,
            message=f"Job '{job_id}' cannot be cancelled: {reason}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"job_id": job_id, "reason": reason},
        )


class IntegrationNotFoundException(NotFoundException):
    """Integration provider not found (HTTP 404)."""

    def __init__(self, integration_name: str) -> None:
        super().__init__(
            message=f"External integration provider '{integration_name}' was not found in registry.",
            details={"integration_name": integration_name},
        )
        self.code = ErrorCode.INTEGRATION_NOT_FOUND.value


class IntegrationTestNotAllowedException(AppException):
    """Integration provider testing not permitted or disabled (HTTP 403)."""

    def __init__(self, message: str = "Integration provider testing is disabled by configuration.") -> None:
        super().__init__(
            code=ErrorCode.INTEGRATION_TEST_NOT_ALLOWED,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class IntegrationUnavailableException(AppException):
    """Integration provider is currently degraded or unavailable (HTTP 503)."""

    def __init__(self, integration_name: str, reason: str) -> None:
        super().__init__(
            code=ErrorCode.INTEGRATION_UNAVAILABLE,
            message=f"Integration provider '{integration_name}' is unavailable: {reason}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"integration_name": integration_name, "reason": reason},
        )


class IncidentNotFoundException(NotFoundException):
    """Operational incident not found (HTTP 404)."""

    def __init__(self, incident_id: str) -> None:
        super().__init__(
            message=f"Operational incident '{incident_id}' was not found.",
            details={"incident_id": incident_id},
        )
        self.code = ErrorCode.INCIDENT_NOT_FOUND.value


class IncidentInvalidStateException(AppException):
    """Invalid incident lifecycle transition requested (HTTP 400)."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.INCIDENT_INVALID_STATE,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class SupportLookupNotAllowedException(ForbiddenException):
    """Support search not authorized or violates privacy boundary (HTTP 403)."""

    def __init__(self, message: str = "Support lookup query violates privacy boundary.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.SUPPORT_LOOKUP_NOT_ALLOWED.value


class AdminActionFailedException(AppException):
    """Administrative or operational action failed during execution (HTTP 500)."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(
            code=ErrorCode.ADMIN_ACTION_FAILED,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ConfigurationChangeNotAllowedException(ForbiddenException):
    """Configuration modification not permitted for this actor (HTTP 403)."""

    def __init__(self, message: str = "Administrative configuration modification not permitted.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.CONFIGURATION_CHANGE_NOT_ALLOWED.value


class SecurityEventAccessDeniedException(ForbiddenException):
    """Security audit event inspection denied (HTTP 403)."""

    def __init__(self, message: str = "Security audit event inspection requires SECURITY_OPERATOR or SYSTEM_ADMIN authorization.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.SECURITY_EVENT_ACCESS_DENIED.value


class AuditAccessDeniedException(ForbiddenException):
    """Administrative audit log inspection denied (HTTP 403)."""

    def __init__(self, message: str = "Administrative audit inspection requires AUDIT_OPERATOR or SYSTEM_ADMIN authorization.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.AUDIT_ACCESS_DENIED.value


class AnalyticsDisabledException(AppException):
    """Analytics layer is disabled by operational configuration (HTTP 503)."""

    def __init__(self, message: str = "Analytics layer is currently disabled by configuration.") -> None:
        super().__init__(
            code=ErrorCode.ANALYTICS_DISABLED,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class AnalyticsUnavailableException(AppException):
    """Analytics service temporarily unavailable (HTTP 503)."""

    def __init__(self, message: str = "Analytics service is temporarily unavailable.") -> None:
        super().__init__(
            code=ErrorCode.ANALYTICS_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class AnalyticsNotFoundException(NotFoundException):
    """Requested analytics resource not found (HTTP 404)."""

    def __init__(self, message: str = "Analytics record or metrics not found.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.ANALYTICS_NOT_FOUND.value


class AnalyticsQueryRangeExceededException(AppException):
    """Analytics query range exceeds allowed historical window (HTTP 400)."""

    def __init__(self, message: str = "Analytics query date range exceeds maximum allowed range.") -> None:
        super().__init__(
            code=ErrorCode.ANALYTICS_QUERY_RANGE_EXCEEDED,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AnalyticsAccessDeniedException(ForbiddenException):
    """Access to analytics data denied (HTTP 403)."""

    def __init__(self, message: str = "Access to analytics data denied.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.ANALYTICS_ACCESS_DENIED.value


class AnomalyNotFoundException(NotFoundException):
    """Usage anomaly record not found (HTTP 404)."""

    def __init__(self, anomaly_id: str) -> None:
        super().__init__(
            message=f"Usage anomaly '{anomaly_id}' was not found.",
            details={"anomaly_id": anomaly_id},
        )
        self.code = ErrorCode.ANOMALY_NOT_FOUND.value


# ---------------------------------------------------------------------------
# Phase 29: Notification, Communication & Event Delivery System Exceptions
# ---------------------------------------------------------------------------


class NotificationDisabledException(AppException):
    """Notification service or channel is globally disabled (HTTP 503)."""

    def __init__(self, message: str = "Notification service is currently disabled.") -> None:
        super().__init__(
            code=ErrorCode.NOTIFICATION_DISABLED,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class NotificationNotFoundException(NotFoundException):
    """Notification record not found (HTTP 404)."""

    def __init__(self, notification_id: str) -> None:
        super().__init__(
            message=f"Notification '{notification_id}' was not found.",
            details={"notification_id": notification_id},
        )
        self.code = ErrorCode.NOTIFICATION_NOT_FOUND.value


class NotificationAccessDeniedException(ForbiddenException):
    """Access to notification denied (HTTP 403)."""

    def __init__(self, message: str = "Access to notification denied.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.NOTIFICATION_ACCESS_DENIED.value


class NotificationPreferenceConflictException(AppException):
    """Notification delivery conflicts with recipient communication preferences (HTTP 422)."""

    def __init__(self, message: str = "Notification cannot be delivered due to recipient communication preferences.") -> None:
        super().__init__(
            code=ErrorCode.NOTIFICATION_PREFERENCE_CONFLICT,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class InvalidRecipientException(AppException):
    """Recipient identifier or contact target is invalid or unverified (HTTP 400)."""

    def __init__(self, message: str = "Recipient contact information is invalid or unverified.") -> None:
        super().__init__(
            code=ErrorCode.INVALID_RECIPIENT,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TemplateResolutionException(AppException):
    """Notification template resolution or variable validation failed (HTTP 422)."""

    def __init__(self, message: str = "Failed to resolve or validate notification template.") -> None:
        super().__init__(
            code=ErrorCode.TEMPLATE_RESOLUTION_ERROR,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class ChannelDisabledException(AppException):
    """Requested delivery channel is disabled or unsupported (HTTP 400)."""

    def __init__(self, channel: str) -> None:
        super().__init__(
            code=ErrorCode.CHANNEL_DISABLED,
            message=f"Delivery channel '{channel}' is disabled or unsupported.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"channel": channel},
        )


class ProviderDeliveryException(AppException):
    """External notification provider delivery failure (HTTP 502)."""

    def __init__(self, provider: str, message: str = "External provider failed to deliver notification.") -> None:
        super().__init__(
            code=ErrorCode.PROVIDER_DELIVERY_ERROR,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"provider": provider},
        )


class ProviderUnavailableException(AppException):
    """Notification provider temporarily unavailable (HTTP 503)."""

    def __init__(self, provider: str, message: str = "Notification provider is unavailable.") -> None:
        super().__init__(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": provider},
        )


class NotificationRateLimitExceededException(AppException):
    """Recipient or sender notification rate limit exceeded (HTTP 429)."""

    def __init__(self, message: str = "Notification rate limit exceeded. Please retry later.") -> None:
        super().__init__(
            code=ErrorCode.NOTIFICATION_RATE_LIMIT_EXCEEDED,
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class DuplicateNotificationException(AppException):
    """Idempotency violation or duplicate notification event (HTTP 409)."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            code=ErrorCode.DUPLICATE_NOTIFICATION,
            message=f"Duplicate notification event detected with idempotency key '{idempotency_key}'.",
            status_code=status.HTTP_409_CONFLICT,
            details={"idempotency_key": idempotency_key},
        )


class UnauthorizedClinicalContentException(AppException):
    """Notification attempts to transmit autonomous clinical diagnosis or medical advice (HTTP 422)."""

    def __init__(self, message: str = "Notification violates clinical safety boundary by containing autonomous clinical advice.") -> None:
        super().__init__(
            code=ErrorCode.UNAUTHORIZED_CLINICAL_CONTENT,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class DeliveryNotFoundException(NotFoundException):
    """Notification delivery record not found (HTTP 404)."""

    def __init__(self, delivery_id: str) -> None:
        super().__init__(
            message=f"Delivery record '{delivery_id}' was not found.",
            details={"delivery_id": delivery_id},
        )
        self.code = ErrorCode.DELIVERY_NOT_FOUND.value


# ---------------------------------------------------------------------------
# Phase 30: Authorized Search, Indexing & Retrieval Exceptions
# ---------------------------------------------------------------------------


class SearchDisabledException(AppException):
    """Search functionality is globally disabled (HTTP 503)."""

    def __init__(self, message: str = "Search service is currently disabled.") -> None:
        super().__init__(
            code=ErrorCode.SEARCH_DISABLED,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class InvalidSearchQueryException(AppException):
    """Search query contains disallowed operators, injection patterns, or malformed syntax (HTTP 400)."""

    def __init__(self, message: str = "Invalid search query syntax.") -> None:
        super().__init__(
            code=ErrorCode.INVALID_SEARCH_QUERY,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class SearchQueryTooLongException(AppException):
    """Search query exceeds configured maximum length (HTTP 400)."""

    def __init__(self, max_length: int) -> None:
        super().__init__(
            code=ErrorCode.SEARCH_QUERY_TOO_LONG,
            message=f"Search query exceeds maximum length of {max_length} characters.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"max_length": max_length},
        )


class SearchQueryTooShortException(AppException):
    """Search query is shorter than required minimum length (HTTP 400)."""

    def __init__(self, min_length: int) -> None:
        super().__init__(
            code=ErrorCode.SEARCH_QUERY_TOO_SHORT,
            message=f"Search query must be at least {min_length} characters.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"min_length": min_length},
        )


class UnsupportedResourceTypeException(AppException):
    """Requested search resource type is not supported (HTTP 400)."""

    def __init__(self, resource_type: str) -> None:
        super().__init__(
            code=ErrorCode.UNSUPPORTED_RESOURCE_TYPE,
            message=f"Resource type '{resource_type}' is not supported for search.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"resource_type": resource_type},
        )


class UnsupportedSearchFilterException(AppException):
    """Filter field is unsupported or not allowlisted (HTTP 400)."""

    def __init__(self, filter_name: str) -> None:
        super().__init__(
            code=ErrorCode.UNSUPPORTED_SEARCH_FILTER,
            message=f"Filter field '{filter_name}' is not supported.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"filter_name": filter_name},
        )


class UnsupportedSortFieldException(AppException):
    """Sort field is not allowlisted (HTTP 400)."""

    def __init__(self, sort_field: str) -> None:
        super().__init__(
            code=ErrorCode.UNSUPPORTED_SORT_FIELD,
            message=f"Sort field '{sort_field}' is not supported.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"sort_field": sort_field},
        )


class SearchNotAuthorizedException(ForbiddenException):
    """Caller lacks required permission or scope to execute search (HTTP 403)."""

    def __init__(self, message: str = "Search not authorized for this caller.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.SEARCH_NOT_AUTHORIZED.value


class PatientSearchNotAuthorizedException(ForbiddenException):
    """Caller lacks patient search authority or facility scope (HTTP 403)."""

    def __init__(self, message: str = "Patient search is not authorized.") -> None:
        super().__init__(message=message)
        self.code = ErrorCode.PATIENT_SEARCH_NOT_AUTHORIZED.value


class SearchProviderUnavailableException(AppException):
    """Search database or backend provider is unavailable (HTTP 503)."""

    def __init__(self, message: str = "Search provider is temporarily unavailable.") -> None:
        super().__init__(
            code=ErrorCode.SEARCH_PROVIDER_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class SearchProviderTimeoutException(AppException):
    """Search provider query exceeded execution ceiling (HTTP 504)."""

    def __init__(self, message: str = "Search execution timed out.") -> None:
        super().__init__(
            code=ErrorCode.SEARCH_PROVIDER_TIMEOUT,
            message=message,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )


class SearchIndexUnavailableException(AppException):
    """Search index structure is currently unavailable or rebuilding (HTTP 503)."""

    def __init__(self, message: str = "Search index is temporarily unavailable.") -> None:
        super().__init__(
            code=ErrorCode.SEARCH_INDEX_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class SearchIndexStaleException(AppException):
    """Search index lag exceeds threshold and fresh querying is mandatory (HTTP 409)."""

    def __init__(self, message: str = "Search index is stale and pending synchronization.") -> None:
        super().__init__(
            code=ErrorCode.SEARCH_INDEX_STALE,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class AmbiguousPatientMatchException(AppException):
    """Patient search returned ambiguous identity matches that cannot be resolved safely (HTTP 422)."""

    def __init__(self, message: str = "Search returned ambiguous patient records. Exact identifier required.") -> None:
        super().__init__(
            code=ErrorCode.AMBIGUOUS_PATIENT_MATCH,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


# Phase 30 Error aliases
SearchDisabledError = SearchDisabledException
InvalidSearchQueryError = InvalidSearchQueryException
SearchQueryTooLongError = SearchQueryTooLongException
SearchQueryTooShortError = SearchQueryTooShortException
UnsupportedSearchResourceTypeError = UnsupportedResourceTypeException
UnsupportedSearchFilterError = UnsupportedSearchFilterException
UnsupportedSortFieldError = UnsupportedSortFieldException
SearchNotAuthorizedError = SearchNotAuthorizedException
PatientSearchNotAuthorizedError = PatientSearchNotAuthorizedException
SearchProviderUnavailableError = SearchProviderUnavailableException
SearchProviderTimeoutError = SearchProviderTimeoutException
SearchIndexUnavailableError = SearchIndexUnavailableException
SearchIndexStaleError = SearchIndexStaleException
AmbiguousPatientMatchError = AmbiguousPatientMatchException


def _get_request_id(request: Request) -> str:
    """Retrieve request ID from request state or context variable."""
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


def build_error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: Any = None,
) -> JSONResponse:
    """Construct a standardized JSON error response."""
    error_payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if details is not None:
        error_payload["details"] = details

    return JSONResponse(
        status_code=status_code,
        content={
            "success": false if False else False,
            "error": error_payload,
        },
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    req_id = _get_request_id(request)
    logger.warning(
        f"Application exception: code={exc.code}, message={exc.message}",
        extra={"request_id": req_id, "status_code": exc.status_code},
    )
    return build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=req_id,
        details=exc.details,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI / Pydantic request validation errors."""
    req_id = _get_request_id(request)
    # Simplify error details without leaking system internals
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(item) for item in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append({"field": loc, "message": msg})

    logger.info(
        f"Validation error: {errors}",
        extra={"request_id": req_id, "status_code": 422},
    )
    return build_error_response(
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR.value,
        message="Request validation failed.",
        request_id=req_id,
        details=errors,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette / FastAPI HTTPExceptions (such as 404, 405)."""
    req_id = _get_request_id(request)
    
    code_map: dict[int, str] = {
        status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND.value,
        status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED.value,
        status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN.value,
        status.HTTP_409_CONFLICT: ErrorCode.CONFLICT.value,
        status.HTTP_503_SERVICE_UNAVAILABLE: ErrorCode.SERVICE_UNAVAILABLE.value,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR.value)

    return build_error_response(
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail) if exc.detail else "An error occurred.",
        request_id=req_id,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions to prevent stack trace leakage."""
    req_id = _get_request_id(request)
    # Log internal stack trace securely with request_id
    logger.exception(
        f"Unhandled internal server error: {exc}",
        extra={"request_id": req_id, "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR},
    )
    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=ErrorCode.INTERNAL_ERROR.value,
        message="An unexpected error occurred.",
        request_id=req_id,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers to the FastAPI app."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

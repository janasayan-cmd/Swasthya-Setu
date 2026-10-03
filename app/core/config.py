"""Application configuration module using Pydantic Settings."""

import json
from functools import lru_cache
from typing import Annotated, Any, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(v: Any) -> list[str]:
    """Parse CORS allowed origins from comma-separated string, JSON list, or array."""
    if isinstance(v, str):
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(origin).strip().rstrip("/") for origin in parsed if str(origin).strip()]
            except Exception:
                pass
        return [origin.strip().rstrip("/") for origin in v.split(",") if origin.strip()]
    if isinstance(v, list):
        return [str(origin).strip().rstrip("/") for origin in v if str(origin).strip()]
    return []


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General Application Info
    APP_NAME: str = Field(default="HealthSetu", description="Name of the application")
    APP_ENV: Literal["development", "testing", "production"] = Field(
        default="development",
        description="Application environment (development, testing, production)",
    )
    APP_VERSION: str = Field(default="1.0.0", description="Semantic version of application")
    DEBUG: bool = Field(default=False, description="Debug mode flag")
    HOST: str = Field(default="0.0.0.0", description="Host to bind server")
    PORT: int = Field(default=8000, description="Port to bind server")
    ENABLE_DOCS: bool | None = Field(
        default=None,
        description="Explicitly enable/disable Swagger & ReDoc interactive docs (defaults to non-production only)",
    )

    # Database Configuration (PostgreSQL Async Engine Layer)
    DATABASE_URL: str | None = Field(
        default=None,
        description="Async PostgreSQL connection URL (e.g., postgresql+asyncpg://user:pass@host:5432/db)",
    )

    # Database Connection Pooling Configuration (Phase 17)
    DB_POOL_SIZE: int = Field(
        default=10,
        description="SQLAlchemy asyncpg connection pool size",
    )
    DB_MAX_OVERFLOW: int = Field(
        default=20,
        description="Maximum connection pool overflow allowed above pool_size",
    )
    DB_POOL_TIMEOUT: float = Field(
        default=30.0,
        description="Connection pool timeout in seconds waiting for an available connection",
    )
    DB_POOL_RECYCLE: int = Field(
        default=1800,
        description="Recycle stale pool connections after seconds (30 mins recommended for cloud DB)",
    )
    DB_POOL_PRE_PING: bool = Field(
        default=True,
        description="Issue health check probe on checkout to detect stale/dropped connections",
    )

    # CORS Configuration (accepts comma-separated string, JSON array, or list)
    CORS_ALLOWED_ORIGINS: Any = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://healthsetu.com",
            "https://www.healthsetu.com",
            "https://health-setu-giaa.vercel.app",
        ],
        description="Allowed CORS origins (comma-separated, single string, or list)",
    )

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: Any) -> list[str]:
        return parse_cors_origins(v)

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")

    # API Routing & Prefixes
    API_PREFIX: str = Field(default="/api/v1", description="Default API prefix")

    # Request Correlation
    REQUEST_ID_HEADER: str = Field(default="X-Request-ID", description="HTTP header key for request correlation ID")

    # Security & Request Limits
    MAX_REQUEST_SIZE_BYTES: int = Field(
        default=10 * 1024 * 1024,
        description="Maximum request payload size in bytes (default 10MB)",
    )

    # Authentication & JWT Configuration (Phase 2)
    JWT_SECRET_KEY: str = Field(
        default="insecure_dev_jwt_secret_key_change_in_production_32bytes_min",
        description="Cryptographic secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT cryptographic algorithm (e.g. HS256, RS256)",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15,
        description="Access token lifespan in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30,
        description="Refresh token lifespan in days",
    )
    PASSWORD_HASHING_SCHEME: str = Field(
        default="argon2id",
        description="Primary password hashing scheme",
    )
    AUTH_RATE_LIMIT_ENABLED: bool = Field(
        default=False,
        description="Flag enabling local/development authentication rate limiting hook",
    )

    # Document Processing Configuration (Phase 5)
    MAX_DOCUMENT_SIZE_MB: int = Field(
        default=20,
        description="Maximum allowed document upload size in megabytes",
    )
    MAX_DOCUMENT_PAGES: int = Field(
        default=50,
        description="Maximum allowed document page count for processing",
    )
    DOCUMENT_STORAGE_PROVIDER: str = Field(
        default="local",
        description="Object storage provider (local, s3, etc.)",
    )
    DOCUMENT_STORAGE_PATH: str = Field(
        default="data/documents",
        description="Filesystem root path for local document storage provider",
    )
    OCR_PROVIDER: str = Field(
        default="local",
        description="OCR provider implementation (local, cloud, mock)",
    )
    DOCUMENT_PROCESSING_ENABLED: bool = Field(
        default=True,
        description="Flag enabling background document processing pipeline",
    )
    MAX_PROCESSING_RETRIES: int = Field(
        default=3,
        description="Maximum automatic retry attempts for transient processing failures",
    )
    MALWARE_SCAN_ENABLED: bool = Field(
        default=False,
        description="Flag enabling malware security scanning hook",
    )
    OCR_TIMEOUT_SECONDS: int = Field(
        default=120,
        description="Maximum execution timeout for OCR extraction operations",
    )
    OCR_ENABLED: bool = Field(
        default=True,
        description="Enable OCR extraction pipeline",
    )

    # Medication & Prescription Configuration (Phase 6)
    MEDICATION_TERMINOLOGY_ENABLED: bool = Field(
        default=True,
        description="Enable medication terminology provider integration",
    )
    MEDICATION_TERMINOLOGY_PROVIDER: str = Field(
        default="local",
        description="Medication terminology provider ('local', 'rxnorm', 'licensed_provider')",
    )
    MEDICATION_TERMINOLOGY_BASE_URL: str = Field(
        default="",
        description="Base URL for external terminology provider API",
    )
    MEDICATION_TERMINOLOGY_API_KEY: str = Field(
        default="",
        description="Optional API key for external terminology provider",
    )
    MEDICATION_TERMINOLOGY_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="Maximum execution timeout for terminology normalization calls",
    )
    MEDICATION_NORMALIZATION_ENABLED: bool = Field(
        default=True,
        description="Flag enabling medication normalization pipeline",
    )
    MEDICATION_NORMALIZATION_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retries for transient terminology provider failures",
    )

    # Medication Safety Configuration (Phase 7)
    MEDICATION_SAFETY_ENABLED: bool = Field(
        default=True,
        description="Flag enabling medication safety evaluation pipeline",
    )
    MEDICATION_SAFETY_PROVIDER: str = Field(
        default="mock",
        description="Medication safety provider ('mock', 'licensed_provider')",
    )
    MEDICATION_SAFETY_BASE_URL: str = Field(
        default="",
        description="Base URL for external licensed medication safety provider API",
    )
    MEDICATION_SAFETY_API_KEY: str = Field(
        default="",
        description="API key or token for external medication safety provider",
    )
    MEDICATION_SAFETY_TIMEOUT_SECONDS: int = Field(
        default=15,
        description="Maximum execution timeout in seconds for safety checks",
    )
    MEDICATION_SAFETY_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retry attempts for transient provider failures",
    )
    MEDICATION_SAFETY_RESULT_TTL_SECONDS: int = Field(
        default=3600,
        description="Maximum time-to-live for cached safety evaluations",
    )

    # Triage & SBAR Configuration (Phase 8)
    TRIAGE_ENABLED: bool = Field(
        default=True,
        description="Flag enabling clinical triage assessment pipeline",
    )
    TRIAGE_RULE_SET: str = Field(
        default="healthsetu_emergency_triage_v1",
        description="Active clinical triage protocol identifier",
    )
    TRIAGE_RULE_SET_VERSION: str = Field(
        default="1.0.0",
        description="Version string of the active triage protocol",
    )
    TRIAGE_RULE_ENGINE_TIMEOUT_SECONDS: int = Field(
        default=5,
        description="Maximum execution timeout in seconds for triage rule evaluation",
    )
    SBAR_ENABLED: bool = Field(
        default=True,
        description="Flag enabling SBAR clinical summary generation",
    )
    SBAR_GENERATION_MODE: str = Field(
        default="template",
        description="SBAR generation method: 'template' (deterministic) or 'ai'",
    )
    AI_PROVIDER: str = Field(
        default="mock",
        description="Clinical text generator provider ('mock', 'openai', 'anthropic', 'local')",
    )
    AI_BASE_URL: str = Field(
        default="",
        description="Base URL for external AI text generation provider",
    )
    AI_API_KEY: str = Field(
        default="",
        description="API key or token for external AI provider",
    )
    AI_TIMEOUT_SECONDS: int = Field(
        default=15,
        description="Timeout in seconds for AI text generation calls",
    )
    AI_MAX_OUTPUT_TOKENS: int = Field(
        default=1000,
        description="Maximum allowed output tokens for AI text generation",
    )

    # Care Plan & Discharge Configuration (Phase 9)
    CARE_PLAN_ENABLED: bool = Field(
        default=True,
        description="Flag enabling Care Plan and Discharge processing pipeline",
    )
    CARE_PLAN_DEFAULT_HORIZON_DAYS: int = Field(
        default=30,
        description="Default duration horizon in days for personalized care plans",
    )
    DISCHARGE_EXTRACTION_PROVIDER: str = Field(
        default="local",
        description="Provider for discharge instruction extraction ('local', 'mock', 'licensed')",
    )

    # Phase 11: Organization & Facility Network Configuration
    ORGANIZATION_NETWORK_ENABLED: bool = Field(
        default=True,
        description="Flag enabling healthcare organization network operations",
    )
    FACILITY_NETWORK_ENABLED: bool = Field(
        default=True,
        description="Flag enabling healthcare facility network operations",
    )
    ORGANIZATION_SEARCH_ENABLED: bool = Field(
        default=True,
        description="Flag enabling internal organization search",
    )
    FACILITY_SEARCH_ENABLED: bool = Field(
        default=True,
        description="Flag enabling internal facility search",
    )
    HEALTHCARE_DIRECTORY_PROVIDER: str = Field(
        default="none",
        description="External healthcare directory adapter provider ('none', 'mock', 'external')",
    )
    HEALTHCARE_DIRECTORY_BASE_URL: str = Field(
        default="",
        description="Base URL for external healthcare directory provider",
    )
    HEALTHCARE_DIRECTORY_API_KEY: str = Field(
        default="",
        description="API key for external healthcare directory provider",
    )
    HEALTHCARE_DIRECTORY_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="Request timeout in seconds for external healthcare directory",
    )

    # Phase 12: Facility Discovery & Transfer Configuration
    FACILITY_DISCOVERY_ENABLED: bool = Field(
        default=True,
        description="Flag enabling patient-facing facility discovery",
    )
    FACILITY_DISCOVERY_MAX_RADIUS_KM: float = Field(
        default=100.0,
        description="Maximum allowed search radius in kilometers for facility discovery",
    )
    TRANSFER_ENABLED: bool = Field(
        default=True,
        description="Flag enabling patient transfer/referral workflow",
    )
    TRANSFER_REQUIRE_CONSENT: bool = Field(
        default=True,
        description="Flag requiring explicit patient consent before sharing clinical context during transfer",
    )
    TRANSFER_CLINICAL_CONTEXT_ENABLED: bool = Field(
        default=True,
        description="Flag allowing authorized minimal clinical context attachment to transfers",
    )
    GEOLOCATION_ENABLED: bool = Field(
        default=True,
        description="Flag enabling geolocation distance calculation and provider routing",
    )
    GEOGRAPHIC_DISTANCE_PROVIDER: str = Field(
        default="local",
        description="Provider for geographic distance calculation ('local', 'mock', 'external')",
    )
    GEOGRAPHIC_PROVIDER_BASE_URL: str = Field(
        default="",
        description="Base URL for external geographic routing/distance provider",
    )
    GEOGRAPHIC_PROVIDER_API_KEY: str = Field(
        default="",
        description="API key for external geographic provider",
    )
    GEOGRAPHIC_PROVIDER_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="Request timeout in seconds for external geographic provider",
    )

    # Interoperability & Data Exchange Configuration (Phase 13)
    INTEROPERABILITY_ENABLED: bool = Field(
        default=True,
        description="Flag enabling interoperability and external healthcare data exchange",
    )
    INTEROPERABILITY_PROVIDER: str = Field(
        default="none",
        description="Active interoperability provider adapter ('none', 'mock', 'fhir_server')",
    )
    FHIR_ENABLED: bool = Field(
        default=True,
        description="Flag enabling FHIR standard data exchange",
    )
    FHIR_VERSION: str = Field(
        default="R4",
        description="Supported FHIR specification version ('R4')",
    )
    HL7_ENABLED: bool = Field(
        default=False,
        description="Flag enabling HL7 v2/v3 message exchange",
    )
    HL7_VERSION: str = Field(
        default="",
        description="Supported HL7 version (e.g. '2.5.1')",
    )
    INTEROPERABILITY_BASE_URL: str = Field(
        default="",
        description="Base URL for external healthcare interoperability provider endpoint",
    )
    INTEROPERABILITY_CLIENT_ID: str = Field(
        default="",
        description="OAuth2/API client identifier for external interoperability provider",
    )
    INTEROPERABILITY_CLIENT_SECRET: str = Field(
        default="",
        description="OAuth2/API client secret for external interoperability provider",
    )
    INTEROPERABILITY_API_KEY: str = Field(
        default="",
        description="API key for external interoperability provider",
    )
    INTEROPERABILITY_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Request timeout in seconds for interoperability operations",
    )
    INTEROPERABILITY_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retry attempts for transient external provider errors",
    )

    # AI & Intelligence Layer Configuration (Phase 14)
    AI_ENABLED: bool = Field(
        default=True,
        description="Master toggle enabling/disabling the AI orchestration layer",
    )
    AI_PROVIDER: str = Field(
        default="mock",
        description="Active AI provider adapter ('mock', 'openai', 'azure_openai')",
    )
    AI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Model name/deployment identifier for production AI tasks",
    )
    AI_BASE_URL: str = Field(
        default="",
        description="Custom base URL for AI provider endpoint (SSRF-validated)",
    )
    AI_API_KEY: str = Field(
        default="",
        description="Secret API key for external AI provider",
    )
    AI_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Timeout in seconds for external AI model calls",
    )
    AI_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retry attempts for transient provider failures",
    )
    AI_MAX_OUTPUT_TOKENS: int = Field(
        default=2000,
        description="Maximum allowed completion tokens for AI output",
    )
    AI_TEMPERATURE: float = Field(
        default=0.0,
        description="Sampling temperature for deterministic clinical assistance",
    )
    AI_REQUEST_RATE_LIMIT: int = Field(
        default=60,
        description="Maximum AI requests per minute per user/organization",
    )
    AI_MAX_CONCURRENT_REQUESTS: int = Field(
        default=5,
        description="Maximum concurrent AI model requests",
    )
    AI_DATA_RETENTION_MODE: str = Field(
        default="disabled",
        description="Provider-side data retention mode ('disabled', 'stateless')",
    )
    AI_TRAINING_OPT_IN: bool = Field(
        default=False,
        description="Opt-in flag for provider model training (strictly False by default)",
    )
    AI_STRUCTURED_OUTPUT_ENABLED: bool = Field(
        default=True,
        description="Enforce structured output schemas on AI generation",
    )
    AI_GROUNDING_VALIDATION_ENABLED: bool = Field(
        default=True,
        description="Enforce source grounding check on generated clinical facts",
    )
    AI_PROMPT_VERSION: str = Field(
        default="1.0.0",
        description="Active prompt template bundle version",
    )

    # Security & Compliance Hardening (Phase 15)
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Flag enabling request rate limiting middleware and guards",
    )
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = Field(
        default=60,
        description="Default sliding-window rate limit per minute for standard API endpoints",
    )
    RATE_LIMIT_AUTH_PER_MINUTE: int = Field(
        default=10,
        description="Strict sliding-window rate limit per minute for authentication endpoints",
    )
    AUDIT_ENABLED: bool = Field(
        default=True,
        description="Flag enabling centralized audit logging for compliance and tracking",
    )
    PHI_SAFE_LOGGING_ENABLED: bool = Field(
        default=True,
        description="Flag enforcing strict PHI redaction and sanitization in all application logs",
    )
    AI_SECURITY_ENABLED: bool = Field(
        default=True,
        description="Flag enabling prompt injection checks and AI request/response security guards",
    )
    DOCUMENT_PRIVATE_STORAGE: bool = Field(
        default=False,
        description="Flag enforcing private non-public document storage backend in production",
    )
    SECURITY_HEADERS_ENABLED: bool = Field(
        default=True,
        description="Flag enabling defensive HTTP response security headers",
    )
    STRICT_TRANSPORT_SECURITY_ENABLED: bool = Field(
        default=True,
        description="Flag enabling HSTS (Strict-Transport-Security) header in production",
    )

    # Phase 18: Observability, Monitoring & Incident Telemetry
    OBSERVABILITY_ENABLED: bool = Field(
        default=True,
        description="Master toggle for application observability layer",
    )
    METRICS_ENABLED: bool = Field(
        default=True,
        description="Enable in-memory metrics collection and telemetry exporter",
    )
    TRACING_ENABLED: bool = Field(
        default=False,
        description="Enable distributed tracing integration",
    )
    TRACING_SAMPLE_RATE: float = Field(
        default=0.05,
        description="Trace sampling probability for production requests",
    )
    ERROR_TRACKING_ENABLED: bool = Field(
        default=True,
        description="Enable centralized error telemetry tracking",
    )
    SLOW_REQUEST_THRESHOLD_MS: int = Field(
        default=2000,
        description="Execution latency threshold in milliseconds to flag a request as slow",
    )
    HEALTH_MONITORING_ENABLED: bool = Field(
        default=True,
        description="Enable operational health and dependency readiness probing",
    )
    PROVIDER_MONITORING_ENABLED: bool = Field(
        default=True,
        description="Enable individual telemetry tracking for external service providers",
    )
    PHI_LOG_REDACTION_ENABLED: bool = Field(
        default=True,
        description="Enforce strict centralized PHI and credential masking on log output",
    )

    # Phase 21: Scalability, Performance & High-Availability Engineering
    DEFAULT_PAGE_SIZE: int = Field(default=25, description="Default pagination page size")
    MAX_PAGE_SIZE: int = Field(default=100, description="Strict maximum allowed pagination limit")
    CIRCUIT_BREAKER_ENABLED: bool = Field(default=True, description="Enable circuit breaker for external providers")
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=5, description="Consecutive failure threshold before opening circuit")
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS: float = Field(default=30.0, description="Cooldown seconds before attempting half-open probe")
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: int = Field(default=2, description="Trial calls permitted during half-open recovery")
    AI_MAX_CONCURRENCY: int = Field(default=4, description="Bounded concurrency limit for external AI inference requests")
    OCR_MAX_CONCURRENCY: int = Field(default=3, description="Bounded concurrency limit for CPU/memory-heavy OCR extraction")
    MED_SAFETY_MAX_CONCURRENCY: int = Field(default=10, description="Bounded concurrency limit for medication safety provider calls")
    BACKGROUND_WORKER_CONCURRENCY: int = Field(default=5, description="Maximum concurrent workers for background task processing")
    BACKGROUND_QUEUE_MAX_DEPTH: int = Field(default=500, description="Maximum background queue depth before rejecting non-critical jobs")
    BACKGROUND_JOB_TIMEOUT_SECONDS: float = Field(default=60.0, description="Maximum runtime allowed for a background job")
    CACHE_ENABLED: bool = Field(default=True, description="Enable bounded in-memory caching for reference & terminology data")
    CACHE_TTL_REFERENCE_SECONDS: int = Field(default=3600, description="TTL in seconds for static organization/facility metadata")
    CACHE_TTL_TERMINOLOGY_SECONDS: int = Field(default=86400, description="TTL in seconds for validated RxNorm terminology matches")
    CACHE_TTL_SAFETY_SECONDS: int = Field(default=300, description="TTL in seconds for context-sensitive medication safety evaluations")
    LOAD_SHEDDING_ENABLED: bool = Field(default=True, description="Enable automatic load shedding during resource saturation")
    LOAD_SHEDDING_MAX_CONCURRENT_REQUESTS: int = Field(default=100, description="Concurrent request threshold triggering load shedding")

    # Phase 22: Asynchronous Workflow Orchestration & Event-Driven Backend
    ASYNC_PROCESSING_ENABLED: bool = Field(default=True, description="Enable asynchronous job and workflow processing")
    JOB_QUEUE_PROVIDER: str = Field(default="memory", description="Active queue provider ('memory', 'redis', 'sqs')")
    JOB_QUEUE_URL: str = Field(default="", description="Connection URL for external queue broker")
    JOB_MAX_RETRIES: int = Field(default=3, description="Maximum automated retries for transient job failures")
    JOB_RETRY_BASE_DELAY_SECONDS: float = Field(default=5.0, description="Base exponential retry delay in seconds")
    JOB_RETRY_MAX_DELAY_SECONDS: float = Field(default=300.0, description="Maximum ceiling for exponential retry delay in seconds")
    JOB_RETRY_JITTER_ENABLED: bool = Field(default=True, description="Add randomized jitter to retry intervals")
    JOB_DEFAULT_TIMEOUT_SECONDS: float = Field(default=300.0, description="Default timeout in seconds for background jobs")
    EVENT_PROCESSING_ENABLED: bool = Field(default=True, description="Enable event-driven publishing and consumption")
    EVENT_PROVIDER: str = Field(default="memory", description="Event transport provider ('memory', 'kafka', 'sns')")
    EVENT_PROVIDER_URL: str = Field(default="", description="Connection URL for event bus")
    EVENT_MAX_RETRIES: int = Field(default=3, description="Maximum retries for failed event consumers")
    OUTBOX_ENABLED: bool = Field(default=True, description="Enable transactional outbox for reliable event publishing")
    WORKER_ENABLED: bool = Field(default=True, description="Enable background worker execution pool")
    WORKER_CONCURRENCY: int = Field(default=5, description="Concurrent task execution limit for async worker pool")
    WORKER_MAX_TASKS: int = Field(default=100, description="Maximum in-memory pending tasks before queuing backpressure")
    WORKER_SHUTDOWN_TIMEOUT_SECONDS: float = Field(default=30.0, description="Graceful shutdown drain timeout for in-flight tasks")
    DEAD_LETTER_ENABLED: bool = Field(default=True, description="Persist permanently failed jobs to dead-letter queue")

    # Phase 24: Advanced Data Privacy, PHI Lifecycle & Data Governance
    PRIVACY_CONTROLS_ENABLED: bool = Field(default=True, description="Enforce centralized data privacy and classification controls")
    DATA_EXPORT_ENABLED: bool = Field(default=True, description="Enable controlled patient data export workflows")
    RETENTION_PROCESSING_ENABLED: bool = Field(default=True, description="Enable retention evaluation and lifecycle processing")
    DEIDENTIFICATION_ENABLED: bool = Field(default=True, description="Enable de-identification transformations for non-production use")
    PSEUDONYMIZATION_ENABLED: bool = Field(default=True, description="Enable cryptographic pseudonymization services")
    TEMPORARY_DATA_CLEANUP_ENABLED: bool = Field(default=True, description="Enable automated purging of temporary files and expired exports")
    PRIVACY_JOB_MAX_RETRIES: int = Field(default=3, description="Maximum retries for privacy background jobs (destructive jobs fail closed)")
    EXPORT_EXPIRATION_SECONDS: int = Field(default=86400, description="Expiration TTL in seconds for generated patient export artifacts (24h)")
    TEMPORARY_DATA_TTL_SECONDS: int = Field(default=3600, description="Maximum lifespan in seconds for temporary files")
    RETENTION_EVALUATION_INTERVAL_SECONDS: int = Field(default=86400, description="Periodic interval for retention policy evaluations")
    PSEUDONYMIZATION_SALT: str = Field(default="healthsetu-governance-salt-v1", description="Cryptographic salt for pseudonymization")
    EXPORT_MAX_FILE_SIZE_MB: int = Field(default=50, description="Maximum export payload size limit in MB")

    # Phase 25: Feature Flags, Configuration Governance & Controlled Rollout
    FEATURE_FLAGS_ENABLED: bool = Field(default=True, description="Enable runtime feature-flag evaluation")
    CONFIG_CACHE_TTL_SECONDS: int = Field(default=60, description="In-memory feature flag cache TTL in seconds")
    CONFIG_GOVERNANCE_STRICT_MODE: bool = Field(default=False, description="Fail fast on missing conditional dependencies during startup")
    CONFIG_DRIFT_DETECTION_ENABLED: bool = Field(default=True, description="Enable configuration drift analysis across environments")

    # Feature availability flags (TRD Sec 17)
    DOCUMENT_PROCESSING_ENABLED: bool = Field(default=True, description="Feature flag for document OCR and extraction")
    MEDICATION_NORMALIZATION_ENABLED: bool = Field(default=True, description="Feature flag for RxNorm / drug normalization")
    MEDICATION_SAFETY_ENABLED: bool = Field(default=True, description="Feature flag for medication interaction and allergy checks")
    TRIAGE_ENABLED: bool = Field(default=True, description="Feature flag for emergency triage assessment engine")
    SBAR_ENABLED: bool = Field(default=True, description="Feature flag for SBAR clinical handoff note generation")
    CARE_PLAN_GENERATION_ENABLED: bool = Field(default=True, description="Feature flag for discharge care plan generation")
    CLINICAL_WORKSPACE_ENABLED: bool = Field(default=True, description="Feature flag for doctor clinical workspace & note signing")
    FACILITY_DISCOVERY_ENABLED: bool = Field(default=True, description="Feature flag for inter-facility discovery and transfers")
    TRANSFER_ENABLED: bool = Field(default=True, description="Feature flag for patient transfer workflows")
    AI_PROCESSING_ENABLED: bool = Field(default=True, description="Feature flag for generative AI clinical assistance")
    CLINICAL_AI_ASSISTANCE_ENABLED: bool = Field(default=True, description="Feature flag for clinician copilot features")
    ASYNC_PROCESSING_ENABLED: bool = Field(default=True, description="Feature flag for background task execution engine")

    # Operational safety kill switches (TRD Sec 23)
    AI_PROCESSING_KILL_SWITCH: bool = Field(default=False, description="Emergency operational kill switch halting AI processing")
    MEDICATION_SAFETY_PROVIDER_KILL_SWITCH: bool = Field(default=False, description="Emergency operational kill switch halting medication safety provider calls")
    DOCUMENT_PROCESSING_KILL_SWITCH: bool = Field(default=False, description="Emergency operational kill switch halting document extraction")
    INTEROPERABILITY_KILL_SWITCH: bool = Field(default=False, description="Emergency operational kill switch halting FHIR/HL7 interop")

    # Provider configurations (TRD Sec 12)
    MEDICATION_SAFETY_PROVIDER: str = Field(default="mock", description="Active medication safety engine ('mock', 'licensed_provider')")
    MEDICATION_SAFETY_API_KEY: str = Field(default="", description="API key for licensed medication safety provider")
    AI_PROVIDER: str = Field(default="mock", description="Active AI provider ('mock', 'openai', 'gemini')")
    AI_API_KEY: str = Field(default="", description="API key for external AI provider")
    AI_BASE_URL: str = Field(default="", description="Base URL for external AI provider API")
    OCR_PROVIDER: str = Field(default="mock", description="Document OCR engine ('mock', 'tesseract', 'google_vision')")
    TRIAGE_RULE_SET_VERSION: str = Field(default="v1.0.0", description="Validated clinical triage protocol rule set version")

    # Phase 26: Data Quality, Clinical Record Integrity & Reconciliation
    DATA_QUALITY_ENABLED: bool = Field(default=True, description="Enable automated data-quality and completeness analysis")
    RECONCILIATION_ENABLED: bool = Field(default=True, description="Enable multi-source clinical record reconciliation")
    DATA_QUALITY_ASYNC_ENABLED: bool = Field(default=True, description="Enable asynchronous batch data-quality and reconciliation jobs")
    DATA_QUALITY_MAX_RETRIES: int = Field(default=3, description="Maximum retries for failed data quality background tasks")
    DATA_QUALITY_TIMEOUT_SECONDS: float = Field(default=60.0, description="Execution timeout for quality evaluation checks")
    DUPLICATE_DETECTION_ENABLED: bool = Field(default=True, description="Enable deterministic duplicate clinical record detection")
    CONFLICT_DETECTION_ENABLED: bool = Field(default=True, description="Enable cross-source clinical conflict identification")
    STALE_DATA_DETECTION_ENABLED: bool = Field(default=True, description="Enable stale clinical observation and contact flags")
    PROVENANCE_VALIDATION_ENABLED: bool = Field(default=True, description="Enforce provenance verification and metadata integrity checks")
    MEDICATION_RECONCILIATION_ENABLED: bool = Field(default=True, description="Enable cross-source medication discrepancy analysis")
    EXTERNAL_DATA_RECONCILIATION_ENABLED: bool = Field(default=True, description="Enable reconciliation for external FHIR/HL7 imports")
    STALE_DATA_THRESHOLD_DAYS: int = Field(default=365, description="Days after which un-reassessed observations are flagged as stale")

    # Phase 27: Administration, Support Operations & Controlled Backoffice
    ADMIN_OPERATIONS_ENABLED: bool = Field(default=True, description="Enable administrative operations API layer")
    ADMIN_SUPPORT_ENABLED: bool = Field(default=True, description="Enable support operator troubleshooting workflows")
    ADMIN_JOB_MANAGEMENT_ENABLED: bool = Field(default=True, description="Enable background job inspection and retry/cancel")
    ADMIN_INCIDENT_MANAGEMENT_ENABLED: bool = Field(default=True, description="Enable operational incident management")
    ADMIN_INTEGRATION_MONITORING_ENABLED: bool = Field(default=True, description="Enable integration and provider health monitoring")
    ADMIN_AUDIT_ACCESS_ENABLED: bool = Field(default=True, description="Enable administrative audit query access")
    ADMIN_SECURITY_EVENT_ACCESS_ENABLED: bool = Field(default=True, description="Enable security event log inspection")
    ADMIN_SUPPORT_LOOKUP_ENABLED: bool = Field(default=True, description="Enable privacy-safe patient support lookup")
    ADMIN_PROVIDER_TESTING_ENABLED: bool = Field(default=False, description="Enable controlled external provider connectivity testing")
    ADMIN_OPERATION_MAX_RETRIES: int = Field(default=3, description="Maximum retries for admin operational actions")
    ADMIN_OPERATION_TIMEOUT_SECONDS: float = Field(default=30.0, description="Timeout in seconds for admin operational actions")

    # Phase 28: API Analytics, Usage Governance & Operational Intelligence
    ANALYTICS_ENABLED: bool = Field(default=True, description="Enable operational analytics and usage telemetry layer")
    API_ANALYTICS_ENABLED: bool = Field(default=True, description="Enable API usage tracking and latency measurement")
    FEATURE_ANALYTICS_ENABLED: bool = Field(default=True, description="Enable feature invocation measurement")
    JOB_ANALYTICS_ENABLED: bool = Field(default=True, description="Enable background job analytics")
    PROVIDER_ANALYTICS_ENABLED: bool = Field(default=True, description="Enable external provider telemetry and cost tracking")
    COST_ANALYTICS_ENABLED: bool = Field(default=True, description="Enable cost and resource consumption tracking")
    ANOMALY_DETECTION_ENABLED: bool = Field(default=True, description="Enable usage anomaly detection")
    ORGANIZATION_ANALYTICS_ENABLED: bool = Field(default=True, description="Enable organization and facility level analytics")
    ANALYTICS_RETENTION_DAYS: int = Field(default=90, description="Retention window for raw analytics events in days")
    ANALYTICS_AGGREGATION_INTERVAL_SECONDS: int = Field(default=300, description="Aggregation window interval in seconds")
    ANALYTICS_MAX_QUERY_RANGE_DAYS: int = Field(default=90, description="Maximum permitted date range for analytical queries")
    ANALYTICS_EVENT_BATCH_SIZE: int = Field(default=100, description="Batch size for event flushing")
    ANALYTICS_PROCESSING_ENABLED: bool = Field(default=True, description="Enable background analytics processing")

    # Phase 29: Notification, Communication & Event Delivery System
    NOTIFICATIONS_ENABLED: bool = Field(default=True, description="Enable notification delivery system")
    EMAIL_NOTIFICATIONS_ENABLED: bool = Field(default=True, description="Enable email delivery channel")
    SMS_NOTIFICATIONS_ENABLED: bool = Field(default=True, description="Enable SMS delivery channel")
    PUSH_NOTIFICATIONS_ENABLED: bool = Field(default=False, description="Enable push delivery channel")
    IN_APP_NOTIFICATIONS_ENABLED: bool = Field(default=True, description="Enable in-app delivery channel")

    EMAIL_PROVIDER: str = Field(default="mock_email", description="Active email provider adapter")
    EMAIL_PROVIDER_BASE_URL: str = Field(default="https://api.emailprovider.example.com", description="Email provider API base URL")
    EMAIL_PROVIDER_API_KEY: str = Field(default="test_email_key_sec_123", description="Email provider API key")
    EMAIL_PROVIDER_TIMEOUT_SECONDS: float = Field(default=15.0, description="Email provider timeout in seconds")

    SMS_PROVIDER: str = Field(default="mock_sms", description="Active SMS provider adapter")
    SMS_PROVIDER_BASE_URL: str = Field(default="https://api.smsprovider.example.com", description="SMS provider API base URL")
    SMS_PROVIDER_API_KEY: str = Field(default="test_sms_key_sec_123", description="SMS provider API key")
    SMS_PROVIDER_TIMEOUT_SECONDS: float = Field(default=15.0, description="SMS provider timeout in seconds")

    PUSH_PROVIDER: str = Field(default="mock_push", description="Active push provider adapter")
    PUSH_PROVIDER_BASE_URL: str = Field(default="https://api.pushprovider.example.com", description="Push provider API base URL")
    PUSH_PROVIDER_API_KEY: str = Field(default="test_push_key_sec_123", description="Push provider API key")
    PUSH_PROVIDER_TIMEOUT_SECONDS: float = Field(default=15.0, description="Push provider timeout in seconds")

    NOTIFICATION_MAX_RETRIES: int = Field(default=3, description="Maximum retries for transient delivery failures")
    NOTIFICATION_RETRY_BASE_DELAY_SECONDS: float = Field(default=5.0, description="Initial retry delay in seconds")
    NOTIFICATION_RETRY_MAX_DELAY_SECONDS: float = Field(default=300.0, description="Maximum retry delay backoff ceiling")
    NOTIFICATION_RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable notification rate limiting")
    NOTIFICATION_DEDUPLICATION_ENABLED: bool = Field(default=True, description="Enable event deduplication")
    NOTIFICATION_PROVIDER_FAILOVER_ENABLED: bool = Field(default=False, description="Enable automatic provider failover")
    NOTIFICATION_DEFAULT_LANGUAGE: str = Field(default="en", description="Default localization language code")
    NOTIFICATION_RATE_LIMIT_PER_MINUTE: int = Field(default=30, description="Per-recipient rate limit per minute")
    NOTIFICATION_RETENTION_DAYS: int = Field(default=90, description="Notification history retention in days")

    # Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval
    SEARCH_ENABLED: bool = Field(default=True, description="Enable global search service")
    SEARCH_PROVIDER: str = Field(default="postgres", description="Active search provider adapter (postgres/mock/external)")
    SEARCH_DEFAULT_PAGE_SIZE: int = Field(default=20, ge=1, le=100, description="Default pagination size for search queries")
    SEARCH_MAX_PAGE_SIZE: int = Field(default=100, ge=1, le=200, description="Maximum allowable page size for search queries")
    SEARCH_MIN_QUERY_LENGTH: int = Field(default=2, ge=1, description="Minimum search query character length")
    SEARCH_MAX_QUERY_LENGTH: int = Field(default=200, le=1000, description="Maximum search query character length")
    SEARCH_TIMEOUT_SECONDS: float = Field(default=5.0, description="Search execution timeout ceiling in seconds")
    SEARCH_RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable dedicated search rate limiting")
    SEARCH_RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Search requests limit per minute per user")
    SEARCH_INDEXING_ENABLED: bool = Field(default=True, description="Enable background search index synchronization")
    SEARCH_INDEX_ASYNC_ENABLED: bool = Field(default=True, description="Enable asynchronous index synchronization jobs")
    SEARCH_INDEX_MAX_RETRIES: int = Field(default=3, description="Maximum retry count for indexing tasks")
    SEARCH_CACHE_ENABLED: bool = Field(default=False, description="Enable low-risk query result caching")
    SEARCH_CACHE_TTL_SECONDS: int = Field(default=300, description="Cache TTL for low-risk non-sensitive search results")
    SEARCH_EXTERNAL_PROVIDER_BASE_URL: str = Field(default="", description="External search engine base URL")
    SEARCH_EXTERNAL_PROVIDER_API_KEY: str = Field(default="", description="External search engine API key")
    SEARCH_EXTERNAL_PROVIDER_TIMEOUT_SECONDS: float = Field(default=5.0, description="External search engine timeout")

    # Scheduling, Appointment & Clinical Access Management Configuration (Phase 31)
    APPOINTMENTS_ENABLED: bool = Field(default=True, description="Enable appointment management subsystem")
    AVAILABILITY_ENABLED: bool = Field(default=True, description="Enable availability and slot discovery")
    APPOINTMENT_BOOKING_ENABLED: bool = Field(default=True, description="Enable new appointment booking")
    APPOINTMENT_RESCHEDULING_ENABLED: bool = Field(default=True, description="Enable appointment rescheduling")
    APPOINTMENT_CANCELLATION_ENABLED: bool = Field(default=True, description="Enable appointment cancellation")
    APPOINTMENT_REMINDERS_ENABLED: bool = Field(default=True, description="Enable automated appointment reminders")
    SCHEDULING_PROVIDER: str = Field(default="local", description="Authoritative scheduling provider ('local', 'external')")
    SCHEDULING_PROVIDER_BASE_URL: str = Field(default="", description="Base URL for external scheduling provider API")
    SCHEDULING_PROVIDER_API_KEY: str = Field(default="", description="API key or token for external scheduling provider")
    SCHEDULING_PROVIDER_TIMEOUT_SECONDS: int = Field(default=15, description="Timeout ceiling for scheduling provider calls")
    SCHEDULING_PROVIDER_MAX_RETRIES: int = Field(default=2, description="Max retries for transient provider communication failures")
    APPOINTMENT_DEFAULT_DURATION_MINUTES: int = Field(default=30, description="Default slot duration in minutes")
    APPOINTMENT_MAX_LOOKAHEAD_DAYS: int = Field(default=90, description="Maximum forward lookahead for slot discovery")
    APPOINTMENT_MAX_PAGE_SIZE: int = Field(default=100, description="Maximum appointment pagination page size")
    APPOINTMENT_RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable appointment rate limiting")
    APPOINTMENT_BOOKING_IDEMPOTENCY_ENABLED: bool = Field(default=True, description="Enforce idempotency key handling on booking")
    APPOINTMENT_REMINDER_ENABLED: bool = Field(default=True, description="Enable background reminder dispatch")

    # Phase 32: Billing, Payments & Financial Transaction Management Configuration
    BILLING_ENABLED: bool = Field(default=True, description="Master switch for billing subsystem")
    INVOICING_ENABLED: bool = Field(default=True, description="Enable invoice generation and lifecycle")
    PAYMENTS_ENABLED: bool = Field(default=True, description="Enable payment processing and capture")
    REFUNDS_ENABLED: bool = Field(default=True, description="Enable refund processing and limits")
    PAYMENT_WEBHOOKS_ENABLED: bool = Field(default=True, description="Enable payment provider webhook consumption")
    PAYMENT_RECONCILIATION_ENABLED: bool = Field(default=True, description="Enable automated transaction reconciliation")
    PAYMENT_PROVIDER: str = Field(default="mock", description="Configured payment provider adapter ('mock', 'stripe', 'razorpay', etc.)")
    PAYMENT_PROVIDER_BASE_URL: str = Field(default="", description="Base URL for payment provider API")
    PAYMENT_PROVIDER_API_KEY: str = Field(default="", description="API Key for payment provider")
    PAYMENT_PROVIDER_SECRET: str = Field(default="", description="Secret Key for payment provider")
    PAYMENT_WEBHOOK_SECRET: str = Field(default="whsec_test_secret_9981", description="Webhook signing secret")
    PAYMENT_PROVIDER_TIMEOUT_SECONDS: int = Field(default=15, description="Timeout in seconds for payment gateway requests")
    PAYMENT_PROVIDER_MAX_RETRIES: int = Field(default=2, description="Max retries for transient provider communication failures")
    PAYMENT_DEFAULT_CURRENCY: str = Field(default="INR", description="Default currency code (ISO 4217)")
    PAYMENT_IDEMPOTENCY_ENABLED: bool = Field(default=True, description="Enforce idempotency keys on payment creation and refunds")
    PAYMENT_RECONCILIATION_INTERVAL_SECONDS: int = Field(default=300, description="Interval in seconds between reconciliation runs")
    PAYMENT_RETRY_BASE_DELAY_SECONDS: float = Field(default=5.0, description="Base backoff delay in seconds for payment retries")
    PAYMENT_RETRY_MAX_DELAY_SECONDS: float = Field(default=300.0, description="Max backoff ceiling for payment retries")
    PAYMENT_RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting on payment endpoints")
    BILLING_ANALYTICS_ENABLED: bool = Field(default=True, description="Record operational financial telemetry in analytics")
    BILLING_NOTIFICATIONS_ENABLED: bool = Field(default=True, description="Emit customer financial event notifications")

    @property
    def max_document_size_bytes(self) -> int:
        """Maximum allowed document upload size in bytes."""
        return self.MAX_DOCUMENT_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """Check if environment is production."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if environment is development."""
        return self.APP_ENV == "development"

    @property
    def is_testing(self) -> bool:
        """Check if environment is testing."""
        return self.APP_ENV == "testing"

    @property
    def docs_url(self) -> str | None:
        """OpenAPI Swagger UI documentation URL."""
        if self.ENABLE_DOCS is not None:
            return "/docs" if self.ENABLE_DOCS else None
        return "/docs" if not self.is_production else None

    @property
    def redoc_url(self) -> str | None:
        """ReDoc documentation URL."""
        if self.ENABLE_DOCS is not None:
            return "/redoc" if self.ENABLE_DOCS else None
        return "/redoc" if not self.is_production else None

    @property
    def openapi_url(self) -> str | None:
        """OpenAPI schema JSON URL."""
        if self.ENABLE_DOCS is not None:
            return "/openapi.json" if self.ENABLE_DOCS else None
        return "/openapi.json" if not self.is_production else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()


settings = get_settings()


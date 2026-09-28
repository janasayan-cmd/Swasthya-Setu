"""HealthSetu Backend Application Entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.database import close_database_engine, get_engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.load_shedding import LoadSheddingMiddleware
from app.core.middleware import (
    RequestIdMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security_config import enforce_security_config

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    settings = get_settings()

    # 1. Startup phase
    setup_logging(log_level=settings.LOG_LEVEL, is_production=settings.is_production)
    logger.info(
        f"Starting {settings.APP_NAME} [env={settings.APP_ENV}, version={settings.APP_VERSION}]"
    )

    # Validate production security constraints & configuration (fail-closed in production)
    enforce_security_config(settings)

    # Establish database engine boundary (resilient to unavailable DB)
    if not settings.is_testing and settings.DATABASE_URL:
        from app.core.database import check_database_health
        is_ready = await check_database_health(timeout_seconds=15.0)
        if is_ready:
            logger.info("Database connection established and verified on startup.")
        else:
            logger.warning("Database connection could not be verified on startup (will retry on probe).")
    else:
        get_engine()

    # Seed demo data for rapid local development & frontend integration
    if not settings.is_production:
        from app.core.demo_seed import seed_demo_data
        seed_demo_data()

    worker_pool = None
    if settings.ASYNC_PROCESSING_ENABLED and not settings.is_testing:
        from app.api.deps import (
            _global_audit_repo,
            _global_event_repo,
            _global_idempotency_repo,
            _global_job_repo,
        )
        from app.integrations.events.provider import get_event_transport
        from app.integrations.queue.provider import get_job_queue_provider
        from app.services.audit_service import AuditService
        from app.services.event_service import EventService
        from app.services.idempotency_service import IdempotencyService
        from app.services.job_service import JobService
        from app.workers.worker import AsyncWorkerPool

        job_svc = JobService(
            repository=_global_job_repo,
            queue_provider=get_job_queue_provider(settings),
            idempotency_service=IdempotencyService(repository=_global_idempotency_repo),
            audit_service=AuditService(audit_repository=_global_audit_repo),
            settings=settings,
        )
        evt_svc = EventService(
            repository=_global_event_repo,
            transport=get_event_transport(settings),
            audit_service=AuditService(audit_repository=_global_audit_repo),
        )
        worker_pool = AsyncWorkerPool(
            job_service=job_svc,
            queue_provider=get_job_queue_provider(settings),
            event_service=evt_svc,
            settings=settings,
        )
        await worker_pool.start()

    yield

    # 2. Shutdown phase (Sections 74, 75 Graceful Shutdown & Resource Cleanup)
    logger.info(f"Shutting down {settings.APP_NAME}...")
    if worker_pool:
        await worker_pool.stop()
    await close_database_engine()
    from app.core.cache import reference_cache, terminology_cache, safety_cache
    reference_cache.clear()
    terminology_cache.clear()
    safety_cache.clear()
    logger.info("Shutdown lifecycle complete: workers drained, database closed, caches released.")


OPENAPI_TAGS_METADATA = [
    {"name": "Health", "description": "Liveness, readiness, and service diagnostic probes."},
    {"name": "Authentication", "description": "User login, refresh token, credential verification, and session control."},
    {"name": "Consents", "description": "Granular patient consent management and verification."},
    {"name": "Patients", "description": "Patient identity, demographic, and core profile management."},
    {"name": "Clinical Records", "description": "Patient clinical history, allergies, vitals, and encounter timeline."},
    {"name": "Documents", "description": "Medical document upload, storage, OCR text extraction, and processing."},
    {"name": "Prescriptions", "description": "Prescription extraction, entry, and provenance-tracked management."},
    {"name": "Medications", "description": "Medication normalization, RxNorm terminology, and active patient medications."},
    {"name": "Medication Safety", "description": "Drug-drug interaction, allergy contraindication, and dosage safety checks."},
    {"name": "Triage", "description": "Patient symptom intake, rule-based clinical triage, and SBAR generation."},
    {"name": "Care Plans", "description": "Personalized care plans and discharge summary extraction and tracking."},
    {"name": "Clinical Workflow", "description": "Clinician workspace, encounters, versioned clinical notes, assessments, and orders."},
    {"name": "Organizations", "description": "Healthcare organization network, facilities, and departments."},
    {"name": "Facilities", "description": "Facility capability discovery, departmental capacity, and availability."},
    {"name": "Transfers", "description": "Inter-facility patient transfer requests, clinical coordination, and bed acceptance."},
    {"name": "Interoperability", "description": "ABDM / FHIR R4 interoperability, clinical artifact import/export with provenance."},
    {"name": "AI Intelligence", "description": "Non-authoritative clinical AI assistance, summarization, and safe-failure boundaries."},
    {"name": "Observability", "description": "Prometheus metrics, health summaries, and operational observability."},
    {"name": "Asynchronous Jobs", "description": "Long-running async job queuing, execution status, and retry management."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory."""
    if settings is None:
        settings = get_settings()

    application = FastAPI(
        title=f"{settings.APP_NAME} API",
        description=(
            "HealthSetu is a unified healthcare interoperability, clinical coordination, "
            "and patient safety backend platform."
        ),
        version=settings.APP_VERSION,
        openapi_tags=OPENAPI_TAGS_METADATA,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    # Configure Middlewares (Order of execution: outer to inner)
    # 1. Security Headers
    application.add_middleware(SecurityHeadersMiddleware)

    # 2. Request payload size limiting
    application.add_middleware(RequestSizeLimitMiddleware)

    # 3. Load Shedding Middleware (protects clinical core during severe saturation)
    if settings.LOAD_SHEDDING_ENABLED:
        application.add_middleware(LoadSheddingMiddleware)

    # 4. CORS configuration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[settings.REQUEST_ID_HEADER],
    )

    # 4. Rate limiting middleware
    if settings.RATE_LIMIT_ENABLED:
        application.add_middleware(RateLimitMiddleware)

    # 5. Request ID / Correlation middleware (outermost to track end-to-end timing & ID)
    application.add_middleware(RequestIdMiddleware)

    # Centralized exception handlers
    register_exception_handlers(application)

    # Register API Versioning Routers
    # Mounts /api/v1/... (and future /api/v2/...)
    application.include_router(api_router, prefix="/api")

    # Root-level liveness & readiness aliases
    @application.get("/health", include_in_schema=False)
    async def root_health():
        return {
            "status": "ok",
            "service": "healthsetu-backend",
            "version": settings.APP_VERSION,
        }

    @application.get("/ready", include_in_schema=False)
    async def root_ready(response: Response):
        from app.core.database import check_database_health
        is_ok = await check_database_health()
        if not is_ok:
            response.status_code = 503
            return {"status": "not_ready", "checks": {"database": "unavailable"}}
        return {"status": "ready", "checks": {"database": "available"}}

    @application.get("/metrics", include_in_schema=False)
    async def root_metrics():
        from fastapi.responses import PlainTextResponse
        from app.core.metrics import metrics
        return PlainTextResponse(
            content=metrics.to_prometheus_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return application


app = create_app()

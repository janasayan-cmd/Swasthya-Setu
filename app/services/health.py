"""Health and readiness service."""

from app.core.config import get_settings
from app.core.database import check_database_health
from app.schemas.response import HealthResponse, ReadinessChecks, ReadinessResponse
from app.services.base import BaseService


class HealthService(BaseService[None]):
    """Service handling process health and readiness evaluations."""

    def get_health(self) -> HealthResponse:
        """Produce basic liveness status without exposing internals."""
        settings = get_settings()
        return HealthResponse(
            status="ok",
            service="healthsetu-backend",
            version=settings.APP_VERSION,
        )

    async def get_readiness(self) -> tuple[bool, ReadinessResponse]:
        """Evaluate database connectivity and overall operational readiness.

        Returns:
            Tuple of (is_ready: bool, response_payload: ReadinessResponse)
        """
        settings = get_settings()
        db_ok = await check_database_health()
        if db_ok:
            return True, ReadinessResponse(
                status="ready",
                checks=ReadinessChecks(database="available"),
            )

        if not settings.is_testing and not settings.DATABASE_URL:
            # Operational with in-memory stores in local development environment
            return True, ReadinessResponse(
                status="ready",
                checks=ReadinessChecks(database="dormant_in_memory"),
            )

        return False, ReadinessResponse(
            status="not_ready",
            checks=ReadinessChecks(database="unavailable"),
        )

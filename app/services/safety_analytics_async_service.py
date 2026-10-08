"""Phase 61: Safety Analytics Async Service.

Simulates and orchestrates Phase 22 asynchronous processing for longitudinal
surveillance analytics without PHI leakage into task queues.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.schemas.safety_analytics import AnalysisType, SafetyAnalysisRecord
from app.services.safety_analytics_service import (
    SafetyAnalyticsService,
    get_safety_analytics_service,
)

logger = logging.getLogger(__name__)


class SafetyAnalyticsAsyncService:
    """Orchestrates asynchronous execution for large analytical workloads."""

    def __init__(self, analytics_service: Optional[SafetyAnalyticsService] = None) -> None:
        self.analytics_svc = analytics_service or get_safety_analytics_service()

    async def enqueue_analysis_run(
        self,
        analysis_id: str,
        actor_id: str,
        actor_role: str,
        analysis_types: Optional[List[AnalysisType]] = None,
    ) -> Dict[str, Any]:
        """Enqueue asynchronous analysis execution simulating Phase 22 workflow."""
        logger.info(
            "Enqueuing asynchronous safety surveillance analysis for %s by %s",
            analysis_id,
            actor_id,
        )

        # Execute in async task context
        try:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                self.analytics_svc.execute_analysis,
                analysis_id,
                actor_id,
                actor_role,
                analysis_types,
            )
        except RuntimeError:
            # Fallback to direct synchronous execution if no event loop running
            self.analytics_svc.execute_analysis(
                analysis_id=analysis_id,
                actor_id=actor_id,
                actor_role=actor_role,
                analysis_types=analysis_types,
            )

        return {
            "analysis_id": analysis_id,
            "status": "QUEUED",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "worker_lane": "SURVEILLANCE_ANALYTICS_V1",
        }


_async_service: Optional[SafetyAnalyticsAsyncService] = None


def get_safety_analytics_async_service() -> SafetyAnalyticsAsyncService:
    global _async_service
    if _async_service is None:
        _async_service = SafetyAnalyticsAsyncService()
    return _async_service

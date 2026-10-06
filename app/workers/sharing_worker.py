"""Asynchronous Sharing Worker (Phase 44).

Processes queued sharing dispatches with MANDATORY JIT CONSENT RE-EVALUATION.
Ensures that if patient consent was withdrawn or expired between queueing and execution,
the job halts immediately and fails closed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.exceptions import (
    SharingConsentExpiredException,
    SharingConsentRevokedException,
    SharingNotAuthorizedException,
)
from app.core.logging import get_logger
from app.repositories.sharing_repository import SharingRepository
from app.schemas.sharing import SharingStatus
from app.services.sharing_service import SharingService

logger = get_logger("app.sharing_worker")


class SharingWorker:
    """Background worker for asynchronous sharing execution with JIT consent check."""

    def __init__(
        self,
        sharing_service: SharingService,
        sharing_repository: SharingRepository,
    ) -> None:
        self.sharing_service = sharing_service
        self.sharing_repo = sharing_repository

    async def process_sharing_job(
        self,
        sharing_id: str,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        """Execute a queued sharing task ensuring JIT authorization verification."""
        logger.info(f"Worker picking up sharing job: {sharing_id}")

        record = await self.sharing_repo.get_by_id(sharing_id)
        if not record:
            logger.error(f"Sharing job failed: record {sharing_id} not found")
            return {"status": "FAILED", "reason": "RECORD_NOT_FOUND"}

        if record.status in (SharingStatus.REVOKED, SharingStatus.CANCELLED, SharingStatus.DENIED):
            logger.warning(f"Sharing job halted: request is in terminal non-executable state {record.status.value}")
            return {"status": record.status.value, "reason": "TERMINAL_STATE"}

        try:
            # execute_sharing internally re-checks Phase 43 consent right now!
            result = await self.sharing_service.execute_sharing(
                sharing_id=sharing_id,
                actor_id=actor_id,
                actor_role=actor_role,
            )
            return {"status": "SUCCESS", "sharing_id": result.id, "delivery_status": result.delivery_status}

        except (SharingConsentRevokedException, SharingConsentExpiredException, SharingNotAuthorizedException) as exc:
            logger.warning(f"Sharing job halted by JIT consent revocation: {exc}")
            return {"status": "REVOKED", "reason": str(exc)}

        except Exception as exc:
            logger.error(f"Sharing job failed with exception: {exc}")
            return {"status": "FAILED", "reason": str(exc)}

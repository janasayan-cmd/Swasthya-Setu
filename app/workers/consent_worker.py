"""Consent Background Worker.

Handles:
1. Automated periodic consent expiration processing.
2. JIT (Just-in-Time) consent re-evaluation for queued asynchronous exports and sharing.
   - Rule: CONSENT GRANTED AT QUEUE TIME ≠ CONSENT GRANTED AT EXECUTION TIME.
   - Prevents stale queued jobs from disclosing data after withdrawal or expiration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.consent_repository import ConsentRepository
from app.schemas.authorization import ConsentStatus
from app.services.audit_service import AuditService
from app.services.consent_access_service import ConsentAccessService
from app.schemas.access_decision import AccessEvaluationRequest

logger = get_logger("app.consent_worker")


class ConsentWorker:
    """Worker managing consent expiration sweeps and asynchronous re-evaluation."""

    def __init__(
        self,
        consent_repository: ConsentRepository,
        access_service: ConsentAccessService,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.consent_repo = consent_repository
        self.access_service = access_service
        self.audit_service = audit_service

    async def process_expirations(self) -> int:
        """Identify expired consent records and transition them from ACTIVE to EXPIRED.

        SAFETY INVARIANT:
        CONSENT EXPIRATION ≠ DATA DELETION.
        Historical consent evidence and underlying clinical records are preserved.
        """
        if not settings.CONSENT_EXPIRATION_PROCESSING_ENABLED:
            logger.info("Consent expiration processing is disabled by configuration.")
            return 0

        expired_records = await self.consent_repo.get_expired_active_consents()
        count = 0
        now = datetime.now(timezone.utc)

        for record in expired_records:
            await self.consent_repo.update_consent_status(
                consent_id=record.id,
                new_status=ConsentStatus.EXPIRED,
                reason="Automatic expiration processing by system worker",
            )
            count += 1
            logger.info(
                f"Consent {record.id} transitioned to EXPIRED",
                extra={
                    "event_type": "CONSENT_EXPIRED",
                    "consent_id": record.id,
                    "patient_id": record.patient_id,
                },
            )

        return count

    async def recheck_consent_for_async_job(
        self,
        patient_id: str,
        recipient_id: str | None = None,
        resource_type: str = "",
        action: str = "EXPORT",
        purpose: str = "CARE",
        actor_id: str | None = None,
    ) -> bool:
        """Re-evaluate consent at job execution time before sharing or exporting data.

        Guarantees that if a patient withdrew consent while a background export
        was waiting in the queue, the export fails closed and shares nothing.
        """
        rec_id = recipient_id or actor_id or ""
        eval_req = AccessEvaluationRequest(
            actor_id=rec_id,
            patient_id=patient_id,
            resource_type=resource_type,
            action=action,
            purpose=purpose,
        )
        decision = await self.access_service.evaluate_access(eval_req)

        if not decision.allowed:
            logger.warning(
                f"Async job blocked by JIT consent re-evaluation: recipient={recipient_id}, patient={patient_id}, reason={decision.reason_code}",
                extra={
                    "event_type": "RESOURCE_EXPORT_DENIED",
                    "actor_id": recipient_id,
                    "patient_id": patient_id,
                    "resource_type": resource_type,
                    "reason_code": decision.reason_code,
                },
            )
            return False

        logger.info(
            f"Async job authorized by JIT consent re-evaluation: recipient={recipient_id}, patient={patient_id}",
            extra={
                "event_type": "RESOURCE_EXPORT_AUTHORIZED",
                "actor_id": recipient_id,
                "patient_id": patient_id,
                "resource_type": resource_type,
                "consent_id": decision.consent_id,
            },
        )
        return True

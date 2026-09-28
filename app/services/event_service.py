"""Event Service (Phase 22).

Manages:
- Versioned domain event creation and contract enforcement.
- Transactional outbox persistence for reliable post-commit publication.
- Consumer-side deduplication (at-least-once delivery protection).
- Audit trail and metrics integration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from app.core.exceptions import EventValidationException
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.integrations.events.base import EventTransport
from app.repositories.event_repository import EventRepository
from app.schemas.audit import AuditEventType
from app.schemas.event import DomainEvent, DomainEventType, OutboxEventRecord, OutboxStatus
from app.services.audit_service import AuditService
from app.services.base import BaseService

logger = get_logger("app.services.event")


class EventService(BaseService[EventRepository]):
    """Service governing reliable event publishing, outbox dispatch, and idempotent consumption."""

    def __init__(
        self,
        repository: EventRepository,
        transport: EventTransport,
        audit_service: AuditService,
    ) -> None:
        super().__init__(repository=repository)
        self.event_repo = repository
        self.transport = transport
        self.audit_service = audit_service

    async def publish(
        self,
        event: DomainEvent,
        use_outbox: bool = True,
    ) -> DomainEvent:
        """Publish a versioned domain event, optionally staging in outbox first."""
        # 1. Enforce Contract / Version Validation
        if not event.event_version or not event.event_type:
            raise EventValidationException("Event must specify valid event_type and event_version.")

        # 2. Stage in Transactional Outbox if required
        outbox_rec: Optional[OutboxEventRecord] = None
        if use_outbox:
            outbox_rec = OutboxEventRecord(
                event=event,
                status=OutboxStatus.PENDING,
            )
            outbox_rec = await self.event_repo.create_outbox_event(outbox_rec)

        # 3. Publish to transport
        published = await self.transport.publish(event)

        # 4. Update outbox record
        if outbox_rec:
            if published:
                outbox_rec.status = OutboxStatus.PUBLISHED
                outbox_rec.published_at = datetime.now(timezone.utc)
            else:
                outbox_rec.status = OutboxStatus.FAILED
                outbox_rec.attempts += 1
                outbox_rec.last_error = "Transport dispatch failed."
            await self.event_repo.update_outbox_event(outbox_rec)

        # 5. Audit
        await self.audit_service.record(
            event_type=AuditEventType.EVENT_PUBLISHED,
            outcome="ALLOW" if published else "DENY",
            action=f"event:publish:{event.event_type.value}",
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            metadata={"event_id": event.event_id, "version": event.event_version},
        )

        return event

    async def flush_outbox(self, limit: int = 50) -> int:
        """Process pending outbox records to guarantee at-least-once delivery."""
        pending = await self.event_repo.get_pending_outbox_events(limit=limit)
        flushed_count = 0

        for rec in pending:
            rec.attempts += 1
            success = await self.transport.publish(rec.event)
            if success:
                rec.status = OutboxStatus.PUBLISHED
                rec.published_at = datetime.now(timezone.utc)
                flushed_count += 1
            else:
                rec.last_error = "Retry transport publication failed."
                if rec.attempts >= rec.max_attempts:
                    rec.status = OutboxStatus.FAILED
            await self.event_repo.update_outbox_event(rec)

        return flushed_count

    def register_consumer(
        self,
        event_type: DomainEventType,
        consumer_name: str,
        handler: Callable[[DomainEvent], Coroutine[Any, Any, None]],
    ) -> None:
        """Register an idempotent event consumer with at-least-once deduplication."""

        async def _idempotent_wrapper(event: DomainEvent) -> None:
            # 1. Check if already consumed by this specific consumer
            first_time = await self.event_repo.mark_event_consumed(
                event_id=event.event_id,
                consumer_name=consumer_name,
            )
            if not first_time:
                logger.info(
                    f"Consumer '{consumer_name}' detected duplicate event {event.event_id} ({event.event_type.value}). Ignoring safely."
                )
                await self.audit_service.record(
                    event_type=AuditEventType.EVENT_DUPLICATE_IGNORED,
                    outcome="ALLOW",
                    action=f"event:duplicate_ignored:{consumer_name}",
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    metadata={"event_id": event.event_id, "consumer": consumer_name},
                )
                return

            # 2. Execute domain handler
            try:
                await handler(event)
                await self.audit_service.record(
                    event_type=AuditEventType.EVENT_CONSUMED,
                    outcome="ALLOW",
                    action=f"event:consumed:{consumer_name}",
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    metadata={"event_id": event.event_id, "consumer": consumer_name},
                )
            except Exception as exc:
                logger.error(f"Consumer '{consumer_name}' failed processing event {event.event_id}: {exc}")
                raise

        self.transport.subscribe(event_type, _idempotent_wrapper)

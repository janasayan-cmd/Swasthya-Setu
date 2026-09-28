"""In-memory event bus transport and factory implementation (Phase 22)."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.integrations.events.base import EventHandler, EventTransport
from app.schemas.event import DomainEvent, DomainEventType

logger = get_logger("app.integrations.events")


class InMemoryEventTransport(EventTransport):
    """In-memory event bus with asynchronous dispatch to registered subscribers."""

    def __init__(self) -> None:
        self._subscribers: Dict[DomainEventType, List[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    async def publish(self, event: DomainEvent) -> bool:
        """Publish event and invoke matching handlers asynchronously."""
        if self._closed:
            logger.warning(f"Discarding event {event.event_id}: transport closed.")
            return False

        handlers = list(self._subscribers.get(event.event_type, []))
        metrics.increment("events_published_total")

        for handler in handlers:
            # Dispatch each subscriber concurrently without blocking publisher
            asyncio.create_task(self._safe_dispatch(handler, event))

        return True

    async def _safe_dispatch(self, handler: EventHandler, event: DomainEvent) -> None:
        """Execute subscriber with error containment."""
        try:
            await handler(event)
            metrics.increment("events_consumed_total")
        except Exception as exc:
            logger.error(f"Event handler failed for {event.event_type} ({event.event_id}): {exc}")

    def subscribe(self, event_type: DomainEventType, handler: EventHandler) -> None:
        """Register subscriber."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def close(self) -> None:
        """Close transport."""
        self._closed = True
        self._subscribers.clear()


_event_transport_instance: Optional[EventTransport] = None


def get_event_transport(settings: Settings | None = None) -> EventTransport:
    """Singleton factory for event transport."""
    global _event_transport_instance
    if _event_transport_instance is None:
        _event_transport_instance = InMemoryEventTransport()
    return _event_transport_instance


def reset_event_transport() -> None:
    """Reset event transport singleton (for testing)."""
    global _event_transport_instance
    _event_transport_instance = None

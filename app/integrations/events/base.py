"""Abstract base class for event bus transport (Phase 22).

Decouples domain event publishing and consumption from physical brokers (Memory, Kafka, SNS/SQS).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

from app.schemas.event import DomainEvent, DomainEventType

EventHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class EventTransport(ABC):
    """Abstract interface for publishing and subscribing to versioned domain events."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> bool:
        """Publish a domain event to the transport."""
        pass

    @abstractmethod
    def subscribe(self, event_type: DomainEventType, handler: EventHandler) -> None:
        """Register an asynchronous subscriber for a specific event type."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close transport and release consumer resources."""
        pass

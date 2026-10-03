"""Abstract Base Class for External / Local Alert Provider Integrations (Phase 35).

CORE SAFETY PRINCIPLES:
- External provider failure must never be interpreted as ALERT RESOLVED or ALERT DELIVERED
  unless authoritative confirmation exists.
- Provider state UNKNOWN must not be reported as safe.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict
from app.schemas.alert import AlertRecord


class AlertProvider(ABC):
    """Abstract interface for dispatching alerts to external/local alert management systems."""

    @abstractmethod
    async def create_alert(self, alert: AlertRecord) -> Dict[str, Any]:
        """Dispatch alert creation to external system.
        
        Returns provider-specific delivery/dispatch metadata.
        """
        raise NotImplementedError

    @abstractmethod
    async def acknowledge_alert(self, alert: AlertRecord, user_id: str, note: str | None = None) -> Dict[str, Any]:
        """Notify external system of explicit alert acknowledgement."""
        raise NotImplementedError

    @abstractmethod
    async def resolve_alert(self, alert: AlertRecord, user_id: str, reason: str) -> Dict[str, Any]:
        """Notify external system of alert resolution."""
        raise NotImplementedError

    @abstractmethod
    async def escalate_alert(self, alert: AlertRecord, target_recipient_id: str, new_level: int) -> Dict[str, Any]:
        """Notify external system that alert has escalated to the next operational tier."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verify provider availability and operational health."""
        raise NotImplementedError

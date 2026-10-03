"""Local / Mock Alert Provider for HealthSetu (Phase 35).

Handles in-memory / local provider dispatch for testing and standalone operation.
Upholds the principle that failure or simulated errors never falsely report safety.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from app.integrations.alerts.base import AlertProvider
from app.schemas.alert import AlertRecord

logger = logging.getLogger(__name__)


class LocalAlertProvider(AlertProvider):
    """Local synchronous/in-memory provider implementation."""

    def __init__(self, simulate_failure: bool = False) -> None:
        self.simulate_failure = simulate_failure
        self.created_alerts: list[dict[str, Any]] = []
        self.acknowledgements: list[dict[str, Any]] = []
        self.resolutions: list[dict[str, Any]] = []
        self.escalations: list[dict[str, Any]] = []

    async def create_alert(self, alert: AlertRecord) -> Dict[str, Any]:
        """Record dispatched alert."""
        if self.simulate_failure:
            logger.error("LocalAlertProvider simulated delivery failure for alert %s", alert.id)
            return {
                "success": False,
                "provider": "local",
                "error": "Simulated provider failure",
                "delivered": False,
            }
        payload = {
            "success": True,
            "provider": "local",
            "alert_id": alert.id,
            "delivered": True,
            "recipient_count": len(alert.recipients),
        }
        self.created_alerts.append(payload)
        return payload

    async def acknowledge_alert(self, alert: AlertRecord, user_id: str, note: str | None = None) -> Dict[str, Any]:
        """Record provider acknowledgement."""
        if self.simulate_failure:
            return {"success": False, "provider": "local", "error": "Simulated provider acknowledgement failure"}
        payload = {
            "success": True,
            "provider": "local",
            "alert_id": alert.id,
            "acknowledged_by": user_id,
            "note": note,
        }
        self.acknowledgements.append(payload)
        return payload

    async def resolve_alert(self, alert: AlertRecord, user_id: str, reason: str) -> Dict[str, Any]:
        """Record provider resolution."""
        if self.simulate_failure:
            return {"success": False, "provider": "local", "error": "Simulated provider resolution failure"}
        payload = {
            "success": True,
            "provider": "local",
            "alert_id": alert.id,
            "resolved_by": user_id,
            "reason": reason,
        }
        self.resolutions.append(payload)
        return payload

    async def escalate_alert(self, alert: AlertRecord, target_recipient_id: str, new_level: int) -> Dict[str, Any]:
        """Record provider escalation notification."""
        if self.simulate_failure:
            return {"success": False, "provider": "local", "error": "Simulated provider escalation failure"}
        payload = {
            "success": True,
            "provider": "local",
            "alert_id": alert.id,
            "target_recipient_id": target_recipient_id,
            "new_level": new_level,
        }
        self.escalations.append(payload)
        return payload

    async def health_check(self) -> Dict[str, Any]:
        """Return operational health status."""
        return {
            "status": "HEALTHY" if not self.simulate_failure else "DEGRADED",
            "provider": "local",
            "supported_channels": ["IN_APP"],
        }

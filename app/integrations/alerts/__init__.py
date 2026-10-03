"""Alert integrations package (Phase 35)."""

from app.integrations.alerts.base import AlertProvider
from app.integrations.alerts.providers.local import LocalAlertProvider

__all__ = ["AlertProvider", "LocalAlertProvider"]

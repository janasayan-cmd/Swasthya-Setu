"""Notification Preferences Repository (Phase 29).

Persists user-configured communication channels, language preferences,
and quiet hours. Thread-safe in-memory store adhering to DB contracts.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from app.schemas.notification_preferences import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
)

logger = logging.getLogger(__name__)


class NotificationPreferenceRepository:
    """Thread-safe repository for recipient communication preferences."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._preferences: Dict[str, NotificationPreferences] = {}

    def get_preferences(self, user_id: str) -> NotificationPreferences:
        """Fetch communication preferences for user_id.

        If not explicitly set, returns default preferences.
        """
        with self._lock:
            prefs = self._preferences.get(user_id)
            if prefs:
                return prefs

            default_prefs = NotificationPreferences(user_id=user_id)
            self._preferences[user_id] = default_prefs
            return default_prefs

    def update_preferences(
        self,
        user_id: str,
        update: NotificationPreferencesUpdate,
    ) -> NotificationPreferences:
        """Update existing communication preferences for user_id."""
        with self._lock:
            current = self.get_preferences(user_id)
            update_data = update.model_dump(exclude_unset=True)
            update_data["updated_at"] = datetime.now(timezone.utc)
            updated = current.model_copy(update=update_data)
            self._preferences[user_id] = updated
            return updated

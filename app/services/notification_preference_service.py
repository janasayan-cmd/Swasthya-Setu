"""Notification Preferences Service (Phase 29).

Enforces:
- MANDATORY SECURITY BYPASS:
  Security-critical alerts bypass user channel opt-outs per organizational policy.
- Quiet hours suppression for non-critical alerts.
- Channel eligibility resolution based on user preferences and category permissions.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
import logging
from typing import List, Optional

from app.core.exceptions import NotificationPreferenceConflictException
from app.repositories.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from app.schemas.notification import (
    NotificationCategory,
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    get_notification_category,
)
from app.schemas.notification_preferences import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
)

logger = logging.getLogger(__name__)


class NotificationPreferenceService:
    """Service governing recipient notification preferences and delivery eligibility."""

    def __init__(self, repository: NotificationPreferenceRepository) -> None:
        self.repository = repository

    def get_preferences(self, user_id: str) -> NotificationPreferences:
        """Fetch communication preferences for user_id."""
        return self.repository.get_preferences(user_id=user_id)

    def update_preferences(
        self,
        user_id: str,
        update: NotificationPreferencesUpdate,
    ) -> NotificationPreferences:
        """Update communication preferences for user_id."""
        return self.repository.update_preferences(user_id=user_id, update=update)

    def is_in_quiet_hours(self, preferences: NotificationPreferences, now_utc: Optional[datetime] = None) -> bool:
        """Check if the current UTC time falls within the user's quiet hours."""
        if not preferences.quiet_hours_enabled:
            return False
        if not preferences.quiet_hours_start_utc or not preferences.quiet_hours_end_utc:
            return False

        current = (now_utc or datetime.now(timezone.utc)).time()
        try:
            start_parts = [int(p) for p in preferences.quiet_hours_start_utc.split(":")]
            end_parts = [int(p) for p in preferences.quiet_hours_end_utc.split(":")]
            start_time = time(start_parts[0], start_parts[1])
            end_time = time(end_parts[0], end_parts[1])
        except Exception as e:
            logger.warning("Error parsing quiet hours '%s' - '%s': %s", preferences.quiet_hours_start_utc, preferences.quiet_hours_end_utc, e)
            return False

        if start_time < end_time:
            return start_time <= current <= end_time
        else:
            # Over midnight window (e.g., 22:00 to 07:00)
            return current >= start_time or current <= end_time

    def resolve_eligible_channels(
        self,
        user_id: str,
        notification_type: NotificationType,
        priority: NotificationPriority,
        requested_channels: Optional[List[NotificationChannel]] = None,
        now_utc: Optional[datetime] = None,
    ) -> List[NotificationChannel]:
        """Determine eligible delivery channels for a notification.

        CRITICAL SECURITY INVARIANT:
        Security notifications bypass user opt-outs and quiet hours.
        """
        category = get_notification_category(notification_type)
        prefs = self.repository.get_preferences(user_id=user_id)

        # 1. Security Critical Notifications bypass user opt-outs
        if category == NotificationCategory.SECURITY:
            if requested_channels:
                return requested_channels
            # Default security delivery: Email + In-App (and SMS if mobile registered)
            eligible = [NotificationChannel.IN_APP]
            if prefs.email_enabled or True:  # security always enables email
                eligible.append(NotificationChannel.EMAIL)
            if prefs.sms_enabled:
                eligible.append(NotificationChannel.SMS)
            return eligible

        # 2. Category Opt-out Checks
        if category == NotificationCategory.CLINICAL_WORKFLOW and not prefs.clinical_notifications_enabled:
            raise NotificationPreferenceConflictException("Recipient has opted out of clinical workflow notifications.")
        if category == NotificationCategory.OPERATIONAL and not prefs.operational_notifications_enabled:
            raise NotificationPreferenceConflictException("Recipient has opted out of operational notifications.")

        # 3. Quiet Hours Suppression for non-critical alerts
        if priority not in (NotificationPriority.CRITICAL, NotificationPriority.HIGH):
            if self.is_in_quiet_hours(prefs, now_utc=now_utc):
                # During quiet hours, suppress external interruptions (SMS/Push); deliver only IN_APP
                logger.info("Recipient %s is in quiet hours. External channels suppressed.", user_id)
                if requested_channels and NotificationChannel.IN_APP not in requested_channels:
                    raise NotificationPreferenceConflictException(
                        "Notification cannot be delivered during active recipient quiet hours."
                    )
                return [NotificationChannel.IN_APP]

        # 4. Filter requested or default channels against user channel toggles
        candidate_channels = requested_channels or [
            NotificationChannel.IN_APP,
            NotificationChannel.EMAIL,
        ]

        eligible: List[NotificationChannel] = []
        for ch in candidate_channels:
            if ch == NotificationChannel.IN_APP and prefs.in_app_enabled:
                eligible.append(ch)
            elif ch == NotificationChannel.EMAIL and prefs.email_enabled:
                eligible.append(ch)
            elif ch == NotificationChannel.SMS and prefs.sms_enabled:
                eligible.append(ch)
            elif ch == NotificationChannel.PUSH and prefs.push_enabled:
                eligible.append(ch)

        if not eligible:
            raise NotificationPreferenceConflictException(
                "No eligible delivery channels available matching recipient communication preferences."
            )

        return eligible

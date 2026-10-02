"""Pydantic schemas for Notification & Communication Preferences (Phase 29).

CRITICAL INVARIANT:
- User preferences must NEVER disable mandatory security notifications.
- Security-critical alerts (password changes, suspicious logins, MFA changes)
  bypass user channel opt-outs per organizational policy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferences(BaseModel):
    """Complete recipient communication preferences record."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="Target user identifier")
    email_enabled: bool = Field(default=True, description="Allow notifications via email")
    sms_enabled: bool = Field(default=True, description="Allow notifications via SMS")
    push_enabled: bool = Field(default=False, description="Allow notifications via Push")
    in_app_enabled: bool = Field(default=True, description="Allow notifications via in-app inbox")
    language: str = Field(default="en", max_length=10, description="Preferred language (en, hi, bn)")
    clinical_notifications_enabled: bool = Field(default=True, description="Receive clinical workflow notifications")
    operational_notifications_enabled: bool = Field(default=True, description="Receive document and transfer updates")
    reminders_enabled: bool = Field(default=True, description="Receive schedule/care-plan reminders")
    quiet_hours_enabled: bool = Field(default=False, description="Enable quiet hours suppression for non-critical alerts")
    quiet_hours_start_utc: Optional[str] = Field(default="22:00", description="Quiet hours start time (HH:MM UTC)")
    quiet_hours_end_utc: Optional[str] = Field(default="07:00", description="Quiet hours end time (HH:MM UTC)")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last preference modification",
    )


class NotificationPreferencesUpdate(BaseModel):
    """Payload to update recipient communication preferences."""

    model_config = ConfigDict(extra="forbid")

    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    language: Optional[str] = Field(None, max_length=10)
    clinical_notifications_enabled: Optional[bool] = None
    operational_notifications_enabled: Optional[bool] = None
    reminders_enabled: Optional[bool] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start_utc: Optional[str] = None
    quiet_hours_end_utc: Optional[str] = None

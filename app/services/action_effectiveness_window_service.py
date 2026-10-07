"""Phase 55: Action Effectiveness Observation Window Service.

Manages observation windows (immediate, fixed duration, event count, rolling).
Enforces the principle that action completion does not mean effectiveness is immediately known.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    ObservationWindow,
    ObservationWindowType,
)


class ActionEffectivenessWindowService:
    """Service for configuring, validating, and monitoring observation windows."""

    def initialize_window(
        self,
        window_type: Optional[ObservationWindowType] = None,
        duration_hours: Optional[int] = 24,
        min_event_count: Optional[int] = None,
    ) -> ObservationWindow:
        """Create and calibrate an observation window."""
        window_type = window_type or ObservationWindowType.FIXED_DURATION

        if duration_hours is not None and duration_hours < 0:
            raise AppException(
                code=ErrorCode.INVALID_OBSERVATION_WINDOW,
                message="Observation window duration_hours cannot be negative.",
                status_code=400,
            )

        if min_event_count is not None and min_event_count < 1:
            raise AppException(
                code=ErrorCode.INVALID_OBSERVATION_WINDOW,
                message="Observation window min_event_count must be at least 1.",
                status_code=400,
            )

        start = datetime.now(timezone.utc)
        end: Optional[datetime] = None

        if window_type == ObservationWindowType.IMMEDIATE:
            end = start
        elif window_type in (ObservationWindowType.FIXED_DURATION, ObservationWindowType.ROLLING):
            hrs = duration_hours if duration_hours is not None else 24
            end = start + timedelta(hours=hrs)

        return ObservationWindow(
            window_type=window_type,
            duration_hours=duration_hours,
            min_event_count=min_event_count,
            start_time=start,
            end_time=end,
            is_closed=(window_type == ObservationWindowType.IMMEDIATE),
        )

    def is_window_mature(
        self,
        window: ObservationWindow,
        observed_events_count: int = 0,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """Check whether the observation window has gathered sufficient duration or events."""
        now = current_time or datetime.now(timezone.utc)

        if window.is_closed:
            return True

        if window.window_type == ObservationWindowType.IMMEDIATE:
            return True

        # Event-count window
        if window.window_type == ObservationWindowType.EVENT_COUNT:
            if window.min_event_count and observed_events_count >= window.min_event_count:
                return True
            return False

        # Duration-based windows
        if window.end_time and now >= window.end_time:
            return True

        # If both duration and event count apply, check if events reached
        if window.min_event_count and observed_events_count >= window.min_event_count:
            return True

        return False

    def close_window(self, window: ObservationWindow) -> ObservationWindow:
        """Mark an observation window as formally closed."""
        window.is_closed = True
        if not window.end_time:
            window.end_time = datetime.now(timezone.utc)
        return window

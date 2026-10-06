"""Concurrency Control Service (Phase 46).

Enforces optimistic concurrency checks, detects stale writes, prevents race conditions,
and guarantees deterministic conflict reporting when concurrent modifications collide.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.exceptions import (
    InvalidVersionException,
    StaleResourceException,
    VersionConflictException,
)

logger = logging.getLogger(__name__)


class ConcurrencyService:
    """Centralized concurrency validation service for clinical record operations."""

    @staticmethod
    def validate_expected_version(
        current_version: int,
        expected_version: int,
        resource_type: str = "resource",
        resource_id: str = "unknown",
    ) -> None:
        """Validate that the caller's expected version strictly matches the current resource version.
        
        Raises:
            StaleResourceException: If expected_version < current_version (caller is updating from stale read)
            InvalidVersionException: If expected_version > current_version (caller provided a future or invalid version)
            VersionConflictException: General conflict if numbers do not align
        """
        if expected_version < 1:
            raise InvalidVersionException(f"Expected version must be >= 1, received {expected_version}.")

        if expected_version < current_version:
            logger.warning(
                "Stale write detected on %s:%s. Expected: %d, Current: %d",
                resource_type,
                resource_id,
                expected_version,
                current_version,
            )
            raise StaleResourceException(
                f"Resource {resource_type}:{resource_id} has changed since it was retrieved. "
                f"You submitted version {expected_version}, but the current version is {current_version}. "
                "Please reload the latest state and retry."
            )

        if expected_version > current_version:
            logger.warning(
                "Invalid future version requested on %s:%s. Expected: %d, Current: %d",
                resource_type,
                resource_id,
                expected_version,
                current_version,
            )
            raise InvalidVersionException(
                f"Invalid expected version {expected_version} for {resource_type}:{resource_id}. "
                f"Current version is only {current_version}."
            )

        logger.debug(
            "Concurrency check passed for %s:%s at version %d",
            resource_type,
            resource_id,
            current_version,
        )


concurrency_service = ConcurrencyService()

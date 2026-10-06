"""Decision Context & Staleness Service (Phase 47).

Responsible for:
- Assembling decision input references with minimum-necessary PHI footprint
- Integrating with Phase 46 clinical record versioning to capture version pointers
- Detecting stale decision contexts when underlying clinical record versions change
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.core.exceptions import DecisionContextStaleException
from app.repositories.versioning_repository import (
    VersioningRepository,
    versioning_repository,
)
from app.schemas.decisions import DecisionInputReference, DecisionRecord

logger = logging.getLogger(__name__)


class DecisionContextService:
    """Manages version-aware context assembly and staleness validation."""

    def __init__(self, versioning_repo: Optional[VersioningRepository] = None) -> None:
        self.versioning_repo = versioning_repo or versioning_repository

    def capture_current_resource_version(
        self, resource_type: str, resource_id: str
    ) -> Optional[int]:
        """Fetch active version index of the target resource from Phase 46."""
        current = self.versioning_repo.get_current_version(resource_type, resource_id)
        return current.version_number if current else None

    def is_context_stale(self, decision: DecisionRecord) -> bool:
        """Evaluate if underlying clinical record versions have progressed past decision input state."""
        # 1. Check primary resource
        if decision.resource_type and decision.resource_id and decision.resource_version:
            current = self.versioning_repo.get_current_version(
                decision.resource_type, decision.resource_id
            )
            if current and current.version_number > decision.resource_version:
                logger.warning(
                    "Stale decision context: %s:%s at v%d, but decision %s was based on v%d",
                    decision.resource_type,
                    decision.resource_id,
                    current.version_number,
                    decision.id,
                    decision.resource_version,
                )
                return True

        # 2. Check each input dependency reference
        for ref in decision.inputs:
            if ref.version_number is not None:
                current_input = self.versioning_repo.get_current_version(
                    ref.resource_type, ref.resource_id
                )
                if current_input and current_input.version_number > ref.version_number:
                    logger.warning(
                        "Stale input reference %s:%s in decision %s: current v%d > input v%d",
                        ref.resource_type,
                        ref.resource_id,
                        decision.id,
                        current_input.version_number,
                        ref.version_number,
                    )
                    return True

        return False

    def validate_not_stale(self, decision: DecisionRecord) -> None:
        """Raise DecisionContextStaleException if decision inputs or targets are stale."""
        if self.is_context_stale(decision):
            raise DecisionContextStaleException(
                f"Decision {decision.id} is stale because underlying clinical record versions have changed. "
                "Re-evaluation against current clinical records is required."
            )


decision_context_service = DecisionContextService()

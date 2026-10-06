"""Phase 50: Safety Pattern & Recurrence Detection Service.

Groups related safety signals, identifies candidate recurring incident patterns,
and associates historical evidence references while strictly preserving uncertainty.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.repositories.safety_learning_repository import (
    SafetyLearningRepository,
    safety_learning_repository,
)
from app.schemas.incidents import IncidentRecord, IncidentType
from app.schemas.safety_pattern import PatternState, SafetyPatternCandidate

logger = logging.getLogger("app.safety_pattern_service")


class SafetyPatternService:
    """Service governing safety pattern detection and recurrence candidate identification."""

    def __init__(
        self,
        learning_repo: Optional[SafetyLearningRepository] = None,
        incident_repo: Optional[SafetyIncidentRepository] = None,
    ) -> None:
        self.learning_repo = learning_repo or safety_learning_repository
        self.incident_repo = incident_repo or safety_incident_repository

    def detect_patterns(
        self,
        start_time: datetime,
        end_time: datetime,
        incident_type: Optional[IncidentType] = None,
    ) -> List[SafetyPatternCandidate]:
        """Analyze historical incidents within window to identify candidate recurring patterns."""
        incidents = self.incident_repo.list_incidents(incident_type=incident_type)
        # Filter within window
        window_incidents = [
            i for i in incidents
            if start_time <= i.occurred_at <= end_time
        ]

        # Group by incident_type
        type_groups: Dict[str, List[IncidentRecord]] = {}
        for inc in window_incidents:
            type_groups.setdefault(inc.incident_type.value, []).append(inc)

        candidates: List[SafetyPatternCandidate] = []
        for itype, group in type_groups.items():
            if len(group) >= settings.SAFETY_LEARNING_MIN_SAMPLE_SIZE:
                # Discovered recurrence candidate
                evidence_refs = [
                    {"incident_id": inc.id, "severity": inc.severity.value, "occurred_at": inc.occurred_at.isoformat()}
                    for inc in group
                ]
                pat = SafetyPatternCandidate(
                    title=f"Recurring Pattern: {itype}",
                    description=f"Observed {len(group)} incidents of type {itype} within observation window.",
                    pattern_type=f"RECURRING_{itype}",
                    state=PatternState.CANDIDATE,
                    occurrence_count=len(group),
                    evidence_references=evidence_refs,
                    affected_subsystem=itype,
                    correlation_signature=f"sig:{itype}:{len(group)}",
                    observation_window_start=start_time,
                    observation_window_end=end_time,
                )
                self.learning_repo.save_pattern(pat)
                candidates.append(pat)

        return candidates

    def get_pattern(self, pattern_id: str) -> Optional[SafetyPatternCandidate]:
        """Retrieve pattern candidate by ID."""
        return self.learning_repo.get_pattern(pattern_id)

    def list_patterns(self) -> List[SafetyPatternCandidate]:
        """List all pattern candidates."""
        return self.learning_repo.list_patterns()


# Global singleton
safety_pattern_service = SafetyPatternService()

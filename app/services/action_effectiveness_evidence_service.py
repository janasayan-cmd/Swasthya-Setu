"""Phase 55: Action Effectiveness Evidence Collection & Validation Service.

Normalizes evidence from authoritative subsystems (Phase 18, 26, 36, 37, 48, 49, 51, 52, 54).
Strictly enforces:
- MISSING != PASS
- MISSING != FAILURE
- INSUFFICIENT != INEFFECTIVE
- STALE != CURRENT
- UNVERIFIED != VALIDATED
- CONFLICTED != RESOLVED
- Strips any raw PHI before processing.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    EffectivenessScope,
    EvidenceQualityState,
    PostActionEvidenceItem,
)


_DISALLOWED_PHI_KEYS = {
    "patient_name", "patient_id", "mrn", "ssn", "dob",
    "phone", "email", "address", "clinical_notes_raw"
}


class ActionEffectivenessEvidenceService:
    """Service for collecting, sanitizing, and validating post-action evidence."""

    def sanitize_payload(self, payload: Dict) -> Dict:
        """Strip raw PHI keys to preserve minimum necessary privacy boundary."""
        cleaned = {}
        for k, v in payload.items():
            if k.lower() in _DISALLOWED_PHI_KEYS:
                continue
            if isinstance(v, dict):
                cleaned[k] = self.sanitize_payload(v)
            else:
                cleaned[k] = v
        return cleaned

    def validate_and_classify_evidence(
        self,
        item: PostActionEvidenceItem,
        target_scope: EffectivenessScope,
        window_start: Optional[datetime] = None,
        max_age_days: int = 30,
    ) -> PostActionEvidenceItem:
        """Validate quality state and scope alignment of an evidence item."""
        # 1. Sanitize payload
        item.data_payload = self.sanitize_payload(item.data_payload)

        # 2. Scope check
        if item.scope.organization_id != target_scope.organization_id:
            item.quality_state = EvidenceQualityState.OUT_OF_SCOPE
            return item
        if target_scope.facility_id and item.scope.facility_id and item.scope.facility_id != target_scope.facility_id:
            item.quality_state = EvidenceQualityState.OUT_OF_SCOPE
            return item

        # 3. Payload validity
        if not item.data_payload:
            item.quality_state = EvidenceQualityState.INSUFFICIENT
            return item

        # 4. Freshness check
        now = datetime.now(timezone.utc)
        if item.timestamp > now + timedelta(minutes=5):
            item.quality_state = EvidenceQualityState.INVALID
            return item

        if window_start and item.timestamp < (window_start - timedelta(minutes=15)):
            # Evidence predates the observation window
            item.quality_state = EvidenceQualityState.STALE
            return item

        if (now - item.timestamp).days > max_age_days:
            item.quality_state = EvidenceQualityState.STALE
            return item

        # 5. Provenance check
        if not item.provenance or not item.source_id:
            item.quality_state = EvidenceQualityState.UNVERIFIED
            return item

        item.quality_state = EvidenceQualityState.COMPLETE
        return item

    def detect_evidence_conflicts(
        self,
        evidence_items: List[PostActionEvidenceItem],
    ) -> List[str]:
        """Detect conflicting evidence observations from different subsystems."""
        conflicts: List[str] = []
        metrics_seen: Dict[str, Tuple[str, Any]] = {}

        for item in evidence_items:
            if item.quality_state not in (EvidenceQualityState.COMPLETE, EvidenceQualityState.PARTIAL):
                continue
            for metric, val in item.data_payload.items():
                if metric in metrics_seen:
                    prev_source, prev_val = metrics_seen[metric]
                    # If same metric reports drastically different state
                    if prev_val != val:
                        conflicts.append(
                            f"Metric '{metric}' conflict: {prev_source} reported '{prev_val}' "
                            f"while {item.source_system} reported '{val}'"
                        )
                else:
                    metrics_seen[metric] = (item.source_system, val)

        return conflicts

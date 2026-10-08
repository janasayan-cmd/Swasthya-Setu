"""Phase 62: Safety Risk Input Eligibility Service.

Validates input source findings from Phase 60 signals, Phase 61 analytical findings,
and upstream safety phases against scope, version, temporal bounds, and privacy rules.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.safety_risk_assessment import (
    ConsolidatedSourceFindingReference,
    FindingEligibilityStatus,
    RiskAssessmentScope,
)


class SafetyRiskInputService:
    """Service to evaluate source finding eligibility and construct valid assessment input sets."""

    def filter_and_validate_findings(
        self,
        raw_findings: List[Dict[str, Any]],
        scope: RiskAssessmentScope,
    ) -> Tuple[List[ConsolidatedSourceFindingReference], List[ConsolidatedSourceFindingReference]]:
        """Validate source findings against scope, version alignment, and privacy constraints."""
        eligible: List[ConsolidatedSourceFindingReference] = []
        excluded: List[ConsolidatedSourceFindingReference] = []
        seen_finding_ids: Set[str] = set()

        now = datetime.now(timezone.utc)

        for item in raw_findings:
            f_id = str(item.get("finding_id") or item.get("indicator_id") or item.get("pattern_id") or item.get("signal_id") or f"fnd-{len(seen_finding_ids)}")
            f_org = item.get("organization_id") or item.get("scope", {}).get("organization_id")
            f_fac = item.get("facility_id") or item.get("scope", {}).get("facility_id")
            f_ver = item.get("version") or item.get("scope", {}).get("version")
            source_phase = str(item.get("source_phase") or "PHASE_61")
            f_type = str(item.get("finding_type") or item.get("pattern_class") or item.get("indicator_type") or "ANALYTICAL_FINDING")
            title = str(item.get("title") or item.get("notes") or f"Finding {f_id}")
            description = str(item.get("description") or item.get("concern_summary") or "")
            metadata = item.get("metadata") or {}
            provenance = item.get("provenance") or {"source_phase": source_phase}

            # Extract timestamp
            raw_ts = item.get("observed_at") or item.get("timestamp") or item.get("created_at")
            if isinstance(raw_ts, datetime):
                observed_at = raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
            elif isinstance(raw_ts, str):
                try:
                    observed_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except Exception:
                    observed_at = now
            else:
                observed_at = now

            # Deduplication
            if f_id in seen_finding_ids:
                ref = ConsolidatedSourceFindingReference(
                    finding_id=f_id,
                    source_phase=source_phase,
                    finding_type=f_type,
                    title=title,
                    description=description,
                    observed_at=observed_at,
                    version=str(f_ver or "unknown"),
                    eligibility_status=FindingEligibilityStatus.DUPLICATE,
                    eligibility_reason="Duplicate finding ID detected in assessment input set",
                    provenance=provenance,
                    metadata=metadata,
                )
                excluded.append(ref)
                continue
            seen_finding_ids.add(f_id)

            # Organization scope check
            if f_org and f_org != scope.organization_id:
                ref = ConsolidatedSourceFindingReference(
                    finding_id=f_id,
                    source_phase=source_phase,
                    finding_type=f_type,
                    title=title,
                    description=description,
                    observed_at=observed_at,
                    version=str(f_ver or "unknown"),
                    eligibility_status=FindingEligibilityStatus.SCOPE_MISMATCH,
                    eligibility_reason=f"Organization mismatch: {f_org} != {scope.organization_id}",
                    provenance=provenance,
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Facility scope check
            if scope.facility_id and f_fac and f_fac != scope.facility_id:
                ref = ConsolidatedSourceFindingReference(
                    finding_id=f_id,
                    source_phase=source_phase,
                    finding_type=f_type,
                    title=title,
                    description=description,
                    observed_at=observed_at,
                    version=str(f_ver or "unknown"),
                    eligibility_status=FindingEligibilityStatus.SCOPE_MISMATCH,
                    eligibility_reason=f"Facility mismatch: {f_fac} != {scope.facility_id}",
                    provenance=provenance,
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Version alignment check
            if scope.version and f_ver and f_ver != scope.version:
                ref = ConsolidatedSourceFindingReference(
                    finding_id=f_id,
                    source_phase=source_phase,
                    finding_type=f_type,
                    title=title,
                    description=description,
                    observed_at=observed_at,
                    version=str(f_ver),
                    eligibility_status=FindingEligibilityStatus.VERSION_MISMATCH,
                    eligibility_reason=f"Version mismatch: {f_ver} != {scope.version}",
                    provenance=provenance,
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Privacy restriction check (PHI minimization)
            if any(k in metadata for k in ("ssn", "patient_name", "raw_clinical_notes")):
                ref = ConsolidatedSourceFindingReference(
                    finding_id=f_id,
                    source_phase=source_phase,
                    finding_type=f_type,
                    title=title,
                    description="[REDACTED_PHI]",
                    observed_at=observed_at,
                    version=str(f_ver or "unknown"),
                    eligibility_status=FindingEligibilityStatus.PRIVACY_RESTRICTED,
                    eligibility_reason="Finding contains unminimized PHI attributes",
                    provenance=provenance,
                    metadata={"redacted": True},
                )
                excluded.append(ref)
                continue

            # Conflicted evidence tag check
            if item.get("is_conflicted") or item.get("conflicted"):
                ref = ConsolidatedSourceFindingReference(
                    finding_id=f_id,
                    source_phase=source_phase,
                    finding_type=f_type,
                    title=title,
                    description=description,
                    observed_at=observed_at,
                    version=str(f_ver or "unknown"),
                    eligibility_status=FindingEligibilityStatus.CONFLICTED,
                    eligibility_reason="Contradictory source evidence flags detected",
                    provenance=provenance,
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Eligible finding
            ref = ConsolidatedSourceFindingReference(
                finding_id=f_id,
                source_phase=source_phase,
                finding_type=f_type,
                title=title,
                description=description,
                observed_at=observed_at,
                version=str(f_ver or scope.version or "v1.0.0"),
                eligibility_status=FindingEligibilityStatus.ELIGIBLE,
                eligibility_reason="Valid and aligned with assessment scope",
                provenance=provenance,
                metadata=metadata,
            )
            eligible.append(ref)

        return eligible, excluded


_risk_input_service: Optional[SafetyRiskInputService] = None


def get_safety_risk_input_service() -> SafetyRiskInputService:
    global _risk_input_service
    if _risk_input_service is None:
        _risk_input_service = SafetyRiskInputService()
    return _risk_input_service

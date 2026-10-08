"""Phase 61: Safety Analytics Input Eligibility Service.

Validates input signal eligibility, provenance, temporal window alignment,
version alignment, scope boundaries, and privacy restrictions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.safety_analytics import (
    AnalysisScope,
    EligibleSignalReference,
    ObservationWindow,
    SignalEligibilityStatus,
)


class SafetyAnalyticsInputService:
    """Service to evaluate signal eligibility and prepare analytical datasets."""

    def filter_and_validate_signals(
        self,
        raw_signals: List[Dict[str, Any]],
        scope: AnalysisScope,
        window: ObservationWindow,
    ) -> Tuple[List[EligibleSignalReference], List[EligibleSignalReference]]:
        """Validate raw or Phase 60 signals against scope, window, and privacy rules."""
        eligible: List[EligibleSignalReference] = []
        excluded: List[EligibleSignalReference] = []
        seen_signal_ids: Set[str] = set()

        now = datetime.now(timezone.utc)
        start_time = window.start_time
        end_time = window.end_time or now

        # Calculate start_time from duration_hours if not explicitly provided
        if not start_time and window.duration_hours:
            from datetime import timedelta
            start_time = end_time - timedelta(hours=window.duration_hours)

        for sig in raw_signals:
            signal_id = str(sig.get("signal_id") or sig.get("primary_signal_id") or f"sig-{len(seen_signal_ids)}")
            sig_org = sig.get("organization_id") or sig.get("scope", {}).get("organization_id")
            sig_fac = sig.get("facility_id") or sig.get("scope", {}).get("facility_id")
            sig_ver = sig.get("version") or sig.get("scope", {}).get("version")
            source = sig.get("source", "Phase 60")
            classification = sig.get("classification") or sig.get("signal_type", "UNKNOWN")
            severity = sig.get("governed_severity") or sig.get("severity", "UNKNOWN")
            uncertainty = sig.get("uncertainty", "LOW_UNCERTAINTY")
            metadata = sig.get("metadata") or sig.get("signal_data", {}).get("metadata", {})

            # Extract timestamp
            raw_ts = sig.get("observed_at") or sig.get("timestamp") or sig.get("created_at")
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
            if signal_id in seen_signal_ids:
                ref = EligibleSignalReference(
                    signal_id=signal_id,
                    triage_id=sig.get("triage_id"),
                    source=source,
                    provenance={"original": sig},
                    classification=str(classification),
                    governed_severity=str(severity),
                    uncertainty=str(uncertainty),
                    observed_at=observed_at,
                    version=str(sig_ver or "unknown"),
                    eligibility_status=SignalEligibilityStatus.DUPLICATE,
                    eligibility_reason="Duplicate signal ID detected in input set",
                    metadata=metadata,
                )
                excluded.append(ref)
                continue
            seen_signal_ids.add(signal_id)

            # Organization scope
            if sig_org and sig_org != scope.organization_id:
                ref = EligibleSignalReference(
                    signal_id=signal_id,
                    triage_id=sig.get("triage_id"),
                    source=source,
                    provenance={"original": sig},
                    classification=str(classification),
                    governed_severity=str(severity),
                    uncertainty=str(uncertainty),
                    observed_at=observed_at,
                    version=str(sig_ver or "unknown"),
                    eligibility_status=SignalEligibilityStatus.SCOPE_MISMATCH,
                    eligibility_reason=f"Organization mismatch: {sig_org} != {scope.organization_id}",
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Facility scope (if requested scope restricts to facility)
            if scope.facility_id and sig_fac and sig_fac != scope.facility_id:
                ref = EligibleSignalReference(
                    signal_id=signal_id,
                    triage_id=sig.get("triage_id"),
                    source=source,
                    provenance={"original": sig},
                    classification=str(classification),
                    governed_severity=str(severity),
                    uncertainty=str(uncertainty),
                    observed_at=observed_at,
                    version=str(sig_ver or "unknown"),
                    eligibility_status=SignalEligibilityStatus.SCOPE_MISMATCH,
                    eligibility_reason=f"Facility mismatch: {sig_fac} != {scope.facility_id}",
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Version alignment check
            if scope.version and sig_ver and sig_ver != scope.version:
                ref = EligibleSignalReference(
                    signal_id=signal_id,
                    triage_id=sig.get("triage_id"),
                    source=source,
                    provenance={"original": sig},
                    classification=str(classification),
                    governed_severity=str(severity),
                    uncertainty=str(uncertainty),
                    observed_at=observed_at,
                    version=str(sig_ver),
                    eligibility_status=SignalEligibilityStatus.VERSION_MISMATCH,
                    eligibility_reason=f"Version mismatch: {sig_ver} != {scope.version}",
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Temporal observation window check
            if start_time and observed_at < start_time:
                ref = EligibleSignalReference(
                    signal_id=signal_id,
                    triage_id=sig.get("triage_id"),
                    source=source,
                    provenance={"original": sig},
                    classification=str(classification),
                    governed_severity=str(severity),
                    uncertainty=str(uncertainty),
                    observed_at=observed_at,
                    version=str(sig_ver or "unknown"),
                    eligibility_status=SignalEligibilityStatus.STALE,
                    eligibility_reason="Observed timestamp precedes observation window start",
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Privacy restriction check (PHI minimization)
            if any(k in metadata for k in ("ssn", "patient_name", "mrn_raw", "raw_clinical_notes")):
                ref = EligibleSignalReference(
                    signal_id=signal_id,
                    triage_id=sig.get("triage_id"),
                    source=source,
                    provenance={"original": sig},
                    classification=str(classification),
                    governed_severity=str(severity),
                    uncertainty=str(uncertainty),
                    observed_at=observed_at,
                    version=str(sig_ver or "unknown"),
                    eligibility_status=SignalEligibilityStatus.PRIVACY_RESTRICTED,
                    eligibility_reason="Signal contains unminimized PHI attributes",
                    metadata={"redacted": True},
                )
                excluded.append(ref)
                continue

            # Conflicted evidence check
            if sig.get("is_conflicted") or sig.get("conflicted"):
                ref = EligibleSignalReference(
                    signal_id=signal_id,
                    triage_id=sig.get("triage_id"),
                    source=source,
                    provenance={"original": sig},
                    classification=str(classification),
                    governed_severity=str(severity),
                    uncertainty=str(uncertainty),
                    observed_at=observed_at,
                    version=str(sig_ver or "unknown"),
                    eligibility_status=SignalEligibilityStatus.CONFLICTED,
                    eligibility_reason="Contradictory evidence flags detected on signal",
                    metadata=metadata,
                )
                excluded.append(ref)
                continue

            # Eligible signal
            ref = EligibleSignalReference(
                signal_id=signal_id,
                triage_id=sig.get("triage_id"),
                source=source,
                provenance={
                    "source": source,
                    "organization_id": sig_org or scope.organization_id,
                    "facility_id": sig_fac or scope.facility_id,
                    "version": sig_ver or scope.version,
                },
                classification=str(classification),
                governed_severity=str(severity),
                uncertainty=str(uncertainty),
                observed_at=observed_at,
                version=str(sig_ver or scope.version or "v1.0.0"),
                eligibility_status=SignalEligibilityStatus.ELIGIBLE,
                eligibility_reason="Valid and aligned with analytical scope",
                metadata=metadata,
            )
            eligible.append(ref)

        return eligible, excluded


_input_service: Optional[SafetyAnalyticsInputService] = None


def get_safety_analytics_input_service() -> SafetyAnalyticsInputService:
    global _input_service
    if _input_service is None:
        _input_service = SafetyAnalyticsInputService()
    return _input_service

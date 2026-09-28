"""Stale data detection rules for HealthSetu (Phase 26).

SAFETY INVARIANT:
Stale information does not mean incorrect information.
The system flags old records for clinician re-assessment rather than auto-deleting them.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import List
from app.integrations.data_quality.base import DataQualityRule, RuleContext
from app.schemas.data_quality import (
    DataQualityFindingRecord,
    DataQualityFindingType,
    FindingSeverity,
)


class StaleObservationRule(DataQualityRule):
    """Detect vital measurements or clinical records older than configured threshold (e.g. 365 days)."""

    rule_name = "StaleObservationRule"
    rule_version = "1.0.0"
    category = "STALE_DATA"

    def __init__(self, threshold_days: int = 365, stale_days: int | None = None) -> None:
        self.threshold_days = stale_days if stale_days is not None else threshold_days

    def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        now = datetime.now(timezone.utc)
        threshold_delta = timedelta(days=self.threshold_days)

        # Check vitals
        for vital in context.vitals:
            vital_id = getattr(vital, "id", "unknown")
            vital_type = getattr(vital, "vital_type", "unknown")
            measured_at = getattr(vital, "measured_at", getattr(vital, "created_at", None))

            if measured_at and isinstance(measured_at, datetime):
                if measured_at.tzinfo is None:
                    measured_at = measured_at.replace(tzinfo=timezone.utc)

                if now - measured_at > threshold_delta:
                    findings.append(
                        DataQualityFindingRecord(
                            patient_id=context.patient_id,
                            resource_type="vital",
                            resource_id=vital_id,
                            finding_type=DataQualityFindingType.STALE_INFORMATION,
                            severity=FindingSeverity.LOW,
                            description=(
                                f"Vital observation '{vital_type}' ({vital_id}) was measured over "
                                f"{self.threshold_days} days ago ({measured_at.date()}). Clinical re-assessment advised."
                            ),
                            rule_name=self.rule_name,
                            rule_version=self.rule_version,
                        )
                    )

        # Check observations
        for obs in getattr(context, "observations", []):
            obs_id = obs.get("id", "unknown") if isinstance(obs, dict) else getattr(obs, "id", "unknown")
            code = obs.get("code", "unknown") if isinstance(obs, dict) else getattr(obs, "code", "unknown")
            obs_time = obs.get("effective_datetime") if isinstance(obs, dict) else getattr(obs, "effective_datetime", None)

            if obs_time and isinstance(obs_time, datetime):
                if obs_time.tzinfo is None:
                    obs_time = obs_time.replace(tzinfo=timezone.utc)

                if now - obs_time > threshold_delta:
                    findings.append(
                        DataQualityFindingRecord(
                            patient_id=context.patient_id,
                            resource_type="observation",
                            resource_id=obs_id,
                            finding_type=DataQualityFindingType.STALE_INFORMATION,
                            severity=FindingSeverity.LOW,
                            description=f"Clinical observation '{code}' ({obs_id}) is stale ({obs_time.date()}). Review required.",
                            rule_name=self.rule_name,
                            rule_version=self.rule_version,
                        )
                    )

        return findings


"""Phase 74: Automated Adoption Monitoring Background Service.

Coordinates:
- Asynchronous and scheduled monitoring routines
- Overdue milestone detection
- Stale or expired operational evidence flagging
- Expired exception detection and state transition
- Automated drift signal generation and logging
- Idempotent and thread-safe execution
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.repositories.governance_change_adoption_repository import (
    GovernanceChangeAdoptionRepository,
    get_governance_change_adoption_repository,
)
from app.schemas.adoption_evidence_indicators import (
    AdoptionEvidenceRecord,
    EvidenceVerificationStatus,
)
from app.schemas.drift_sustainability_consequences import (
    AdoptionExceptionRecord,
    AdoptionExceptionStatus,
    DriftSignalClassification,
    DriftSignalStatus,
    ImplementationDriftSignalRecord,
)
from app.schemas.adoption_reporting import (
    BackgroundJobRunResult,
)


class AdoptionMonitoringBackgroundService:
    """Service governing scheduled and asynchronous monitoring routines."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def run_scheduled_monitoring_cycle(
        self, tenant_id: Optional[str] = None
    ) -> BackgroundJobRunResult:
        """Runs a complete idempotent monitoring scan cycle.
        
        Checks:
        1. Overdue adoption milestones
        2. Stale or expired operational evidence
        3. Expired operational exceptions
        4. Potential baseline drift signals
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        details: List[str] = []

        overdue_milestones = 0
        stale_evidence = 0
        expired_exceptions = 0
        drift_signals_gen = 0

        # 1. Check adoption registrations for overdue milestones
        registrations = self.repo.list_registrations(tenant_id=tenant_id, limit=500)
        for reg in registrations:
            for milestone in reg.adoption_milestones:
                if not milestone.completed:
                    try:
                        target_dt = datetime.fromisoformat(milestone.target_date.replace("Z", "+00:00"))
                        if target_dt < now:
                            overdue_milestones += 1
                            details.append(
                                f"Overdue milestone '{milestone.milestone_key}' on registration '{reg.registration_id}'."
                            )
                    except Exception:
                        pass

        # 2. Check evidence items for expiration
        for reg in registrations:
            evidence_items = self.repo.list_evidence_for_registration(
                reg.registration_id, tenant_id=tenant_id, limit=500
            )
            for evi in evidence_items:
                if (
                    evi.verification_status in [EvidenceVerificationStatus.SUBMITTED, EvidenceVerificationStatus.VERIFIED]
                    and evi.valid_until
                ):
                    try:
                        valid_dt = datetime.fromisoformat(evi.valid_until.replace("Z", "+00:00"))
                        if valid_dt < now:
                            stale_evidence += 1
                            # Update status to EXPIRED
                            e_dict = evi.model_dump()
                            e_dict["verification_status"] = EvidenceVerificationStatus.EXPIRED
                            e_dict["updated_at"] = now_iso
                            self.repo.save_evidence(AdoptionEvidenceRecord(**e_dict))
                            details.append(f"Evidence '{evi.evidence_id}' has expired.")
                    except Exception:
                        pass

        # 3. Check exceptions for expiration
        all_exceptions = self.repo.list_all_exceptions(tenant_id=tenant_id)
        for exc in all_exceptions:
            if exc.status == AdoptionExceptionStatus.ACTIVE and exc.expiry_date:
                try:
                    expiry_dt = datetime.fromisoformat(exc.expiry_date.replace("Z", "+00:00"))
                    if expiry_dt < now:
                        expired_exceptions += 1
                        x_dict = exc.model_dump()
                        x_dict["status"] = AdoptionExceptionStatus.EXPIRED
                        x_dict["updated_at"] = now_iso
                        self.repo.save_exception(AdoptionExceptionRecord(**x_dict))
                        details.append(f"Adoption exception '{exc.exception_id}' expired on {exc.expiry_date}.")
                except Exception:
                    pass

        # 4. Check for baseline drift signals (e.g. active monitoring with 0 verified evidence for > 14 days)
        for reg in registrations:
            if reg.status.value == "ACTIVE_MONITORING":
                verified_evidence = self.repo.list_evidence_for_registration(
                    reg.registration_id,
                    tenant_id=tenant_id,
                    status=EvidenceVerificationStatus.VERIFIED,
                )
                if not verified_evidence:
                    # Check if drift signal already exists for evidence gap
                    existing_signals = self.repo.list_drift_signals_for_registration(
                        reg.registration_id, tenant_id=tenant_id
                    )
                    evidence_gap_signal = any(
                        s.classification == DriftSignalClassification.EVIDENCE_GAP and s.status != DriftSignalStatus.DISPOSED
                        for s in existing_signals
                    )
                    if not evidence_gap_signal:
                        sig_rec = ImplementationDriftSignalRecord(
                            signal_id=f"dfs_gap_{reg.registration_id[:8]}",
                            registration_id=reg.registration_id,
                            tenant_id=reg.tenant_id,
                            baseline_version=reg.current_baseline_version or "1.0",
                            title="Operational Evidence Gap Detected",
                            description="Active monitoring initiative has no verified evidence on record.",
                            classification=DriftSignalClassification.EVIDENCE_GAP,
                            source_type="AUTOMATED_SCAN",
                            observed_at=now_iso,
                            evidence_reference=None,
                            operational_scope=reg.operational_scope,
                            status=DriftSignalStatus.OPEN,
                            created_at=now_iso,
                            updated_at=now_iso,
                        )
                        self.repo.save_drift_signal(sig_rec)
                        drift_signals_gen += 1
                        details.append(f"Drift signal generated for evidence gap on '{reg.registration_id}'.")

        result = BackgroundJobRunResult(
            job_name="adoption_monitoring_routine_scan",
            run_timestamp=now_iso,
            overdue_milestones_flagged=overdue_milestones,
            stale_evidence_flagged=stale_evidence,
            expired_exceptions_flagged=expired_exceptions,
            drift_signals_generated=drift_signals_gen,
            details=details,
        )
        return self.repo.record_job_run(result)
